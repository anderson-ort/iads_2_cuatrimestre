"""Evaluación del RAG de la clase 07 con RAGAS.

Toma el pipeline "tecnico" de 07_clase/.muestra_clase/rag_inferencia.py
(retrieval -> rerank -> LLM) y lo mide con las 4 métricas core de RAGAS:

    Retriever  -> Context Precision, Context Recall
    Generación -> Faithfulness, Answer Relevancy

Flujo (el mismo diagrama de ragas.md):

    golden_set.json + pipeline (config.toml)
            -> se corre el RAG sobre cada pregunta
            -> question + answer + contexts + ground_truth
            -> RAGAS calcula métricas (Gemini hace de juez)
            -> comparación contra baseline.json (regresión)
            -> OK o FALLO (exit code 1, como en un CI)

Uso:

    uv sync
    cp .env.sample .env                          # completar GOOGLE_API_KEY
    uv run python ragas_eval.py                  # 1ra vez: crea baseline.json
    # ...cambiar una perilla en config.toml (ej. top_n = 1)...
    uv run python ragas_eval.py                  # compara contra el baseline
    uv run python ragas_eval.py --baseline       # acepta la corrida como nuevo baseline
    uv run python ragas_eval.py --resume         # retoma una corrida cortada (ej. por cuota)
"""

import json
import logging
import math
import os
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# RAGAS manda telemetría anónima por defecto; la apagamos antes de importarlo.
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
# instructor (lo usa RAGAS por dentro) loguea cada 429 completo; nosotros ya lo manejamos.
logging.getLogger("instructor").setLevel(logging.CRITICAL)

# Lo mismo que usabamos antes
import anydoc

from google import genai
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ragas.embeddings import GoogleEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)

# =============================================================================
# 0. Configuración
# =============================================================================
AQUI = Path(__file__).resolve().parent
load_dotenv(AQUI / ".env")


with open(AQUI / "config.toml", "rb") as f:
    cfg = tomllib.load(f)

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
cfg_eval = cfg["evaluacion"]
METRICAS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
PARCIAL = "en_curso.jsonl"  # casos ya medidos de la corrida actual (ver paso 5)

# Qué revisar cuando una métrica baja (resumen de la matriz de diagnóstico de ragas.md).
DIAGNOSTICO = {
    "faithfulness": "LLM inventa datos: reforzar 'solo usá el contexto', abstención, temperatura 0.",
    "answer_relevancy": "Respuesta vaga o desviada: pedir respuesta directa y concisa en el prompt.",
    "context_precision": "Ruido en los chunks: reranker, bajar top_n, filtros por metadatos.",
    "context_recall": "Falta evidencia: subir top_n/k, revisar chunk_size y overlap, búsqueda híbrida.",
}

# =============================================================================
# 1. Golden set: el "contrato" de evaluación
# =============================================================================
# Cada caso tiene la pregunta y la respuesta de referencia (ground_truth),
# escrita a mano a partir de los documentos. "answer" y "contexts" NO están:
# los produce el pipeline en cada corrida (paso 4).
# Las categorías siguen las recomendaciones de ragas.md: directa, multipaso,
# parafraseada, con restricciones, adversarial (premisa falsa) y fuera de dominio.
golden_set = json.loads((AQUI / cfg_eval["dataset"]).read_text(encoding="utf-8"))
print(f"Golden set: {len(golden_set)} casos")

# =============================================================================
# 2. Indexación (igual que rag_simple.py, pero solo HuggingFace para simplificar)
# =============================================================================
embeddings = HuggingFaceEmbeddings(
    model_name=cfg["embeddings"]["model_name"],
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

# El nombre de la colección incluye modelo y chunking: si cambiás alguno en
# config.toml se arma una colección nueva y podés comparar versiones del
# índice sin borrar nada.
size, overlap = cfg["chunking"]["size"], cfg["chunking"]["overlap"]
modelo_corto = cfg["embeddings"]["model_name"].split("/")[-1]

# Seteamos el VectorStore (en nuestro caso Chromadb)
vectorstore = Chroma(
    persist_directory=str(AQUI / cfg["ingesta"]["persist_dir"]),
    embedding_function=embeddings,
    collection_name=f"ortelana_{modelo_corto}_{size}_{overlap}",
)


if not vectorstore.get()["ids"]:
    print(f"Indexando documentos (chunk_size={size}, overlap={overlap})...")
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3"), ("####", "H4")]
    )
    rec_splitter = RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", " ", ""]
    )
    for ruta in cfg["ingesta"]["archivos"]:
        ruta = AQUI / ruta
        markdown = anydoc.to_markdown(str(ruta))
        secciones = md_splitter.split_text(markdown) or [Document(page_content=markdown)]
        for s in secciones:
            s.metadata["filename"] = ruta.name
        chunks = rec_splitter.split_documents(secciones)
        vectorstore.add_documents(chunks, ids=[f"{ruta.name}-{i}" for i in range(len(chunks))])
        print(f"  {ruta.name}: {len(chunks)} chunks")
print(f"Colección: {len(vectorstore.get()['ids'])} chunks")

# =============================================================================
# 3. Pipeline RAG a evaluar (rama "tecnico" de rag_inferencia.py)
# =============================================================================
# No evaluamos el router: RAGAS mide retrieval + generación. El router se
# evalúa aparte con accuracy de clasificación (es un problema distinto).

class RagAnswer(BaseModel):
    respuesta: str = Field(description="Respuesta directa y concisa a la pregunta")
    informacion_insuficiente: bool = Field(
        description="True si el contexto recuperado no contiene la respuesta"
    )

# El prompt incorpora las instrucciones que ragas.md sugiere para subir
# Faithfulness (solo contexto + abstención) y Answer Relevancy (directo, sin relleno).
RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Respondes preguntas usando SOLO el contexto entregado. No inventes datos.\n"
     "Responde directamente la pregunta e incluye todos los puntos necesarios.\n"
     "No agregues antecedentes ni detalles no solicitados.\n"
     "Si la pregunta parte de una premisa falsa segun el contexto, corrigela.\n"
     "Si el contexto no alcanza, marca informacion_insuficiente=true y dilo en 'respuesta'."),
    ("human", "Contexto:\n{contexto}\n\nPregunta: {pregunta}"),
])

rag_llm = ChatGoogleGenerativeAI(
    model=cfg["llm"]["rag_model"],
    google_api_key=GOOGLE_API_KEY,
    temperature=cfg["llm"]["rag_temperature"],
    # Es as que nada para que el coste sea el minimo posible pues estamos limitando el uso del razonamiento.
    # thinking_budget=0
)


rag_chain = RAG_PROMPT | rag_llm.with_structured_output(RagAnswer)

# Esto viene directamente de la configuracion del toml
k = cfg["retrieval"]["k_candidatos"]
top_n = cfg["retrieval"]["top_n"]

if cfg["retrieval"]["usar_reranker"]:
    from sentence_transformers import CrossEncoder
    cross_encoder = CrossEncoder(cfg["retrieval"]["crossencoder_model"])


def recuperar(pregunta):
    """Retrieval + rerank. Devuelve los top_n docs EN ORDEN (Context Precision mira el orden)."""
    docs = [d for d, _ in vectorstore.similarity_search_with_score(pregunta, k=k)]
    if cfg["retrieval"]["usar_reranker"]:
        scores = cross_encoder.predict([(pregunta, d.page_content) for d in docs])
        docs = [d for d, _ in sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)]
    return docs[:top_n]


def responder(pregunta):
    """Corre el RAG completo y devuelve lo que RAGAS necesita: respuesta + contextos."""
    docs = recuperar(pregunta)
    contexto = "\n\n---\n\n".join(f"[{d.metadata['filename']}]\n{d.page_content}" for d in docs)
    resp = rag_chain.invoke({"pregunta": pregunta, "contexto": contexto})
    return resp, [d.page_content for d in docs]


# =============================================================================
# 4. Juez: Gemini + métricas de RAGAS
# =============================================================================
# Las métricas de RAGAS son "LLM-as-a-judge": un LLM descompone la respuesta
# en afirmaciones, verifica cada una contra el contexto, etc.
#
# LLM juez: Gemini a través de su endpoint compatible con OpenAI. RAGAS 0.4
# (vía la librería instructor) tiene problemas con el cliente async de
# google-genai; la propia doc de RAGAS recomienda este endpoint como solución.
# Sigue siendo Gemini con la misma GOOGLE_API_KEY.
juez_llm = llm_factory(
    cfg_eval["judge_model"],
    client=AsyncOpenAI(
        api_key=GOOGLE_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
)
# Embeddings del juez (solo Answer Relevancy los usa): cliente google-genai.
juez_embeddings = GoogleEmbeddings(
    client=genai.Client(api_key=GOOGLE_API_KEY), model=cfg_eval["judge_embeddings"]
)

# Cómo calcula cada métrica (versión simplificada):
#   Faithfulness:      afirmaciones de la respuesta respaldadas por el contexto / total.
#   Answer Relevancy:  el juez genera preguntas a partir de la respuesta y mide qué tan
#                      parecidas (embeddings) son a la pregunta original.
#   Context Precision: para cada chunk, ¿sirve para llegar al ground_truth? Premia que
#                      los útiles estén arriba en el ranking (precision@k promediada).
#   Context Recall:    afirmaciones del ground_truth que aparecen en los contextos / total.
faithfulness = Faithfulness(llm=juez_llm)
# strictness = cuántas preguntas genera el juez (default 3). Con 1 gastamos menos cuota.
answer_relevancy = AnswerRelevancy(llm=juez_llm, embeddings=juez_embeddings, strictness=1)
context_precision = ContextPrecision(llm=juez_llm)
context_recall = ContextRecall(llm=juez_llm)


def con_reintentos(fn, intentos=4):
    """El free tier de Gemini corta con error 429 (cuota) o 503 (modelo saturado).
    Si es el límite por minuto o saturación, esperamos y reintentamos; si es el
    límite por día, no tiene sentido esperar."""
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            if "PerDay" in str(e):
                sys.exit("Cuota diaria de Gemini agotada. Los casos ya medidos quedaron en "
                         f"{cfg_eval['salida_dir']}/{PARCIAL}. Cambiá judge_model/rag_model "
                         "en config.toml o probá mañana, y seguí con --resume.")
            reintentable = any(c in str(e) for c in ("429", "RESOURCE_EXHAUSTED", "503"))
            if not reintentable or i == intentos - 1:
                raise
            print("    (Gemini pidió esperar: rate limit o saturación, espero 30s...)")
            time.sleep(30)


def medir(q, answer, contexts, ground_truth):
    """Las 4 métricas para un caso. Cada una pide solo las columnas que necesita."""
    return {
        # question + answer + contexts
        "faithfulness": con_reintentos(lambda: faithfulness.score(
            user_input=q, response=answer, retrieved_contexts=contexts)).value,
        # question + answer
        "answer_relevancy": con_reintentos(lambda: answer_relevancy.score(
            user_input=q, response=answer)).value,
        # question + contexts + ground_truth
        "context_precision": con_reintentos(lambda: context_precision.score(
            user_input=q, reference=ground_truth, retrieved_contexts=contexts)).value,
        # question + contexts + ground_truth
        "context_recall": con_reintentos(lambda: context_recall.score(
            user_input=q, reference=ground_truth, retrieved_contexts=contexts)).value,
    }


# =============================================================================
# 5. Ejecución: correr el RAG y medir cada caso
# =============================================================================
# Guardado incremental: cada caso medido se agrega a una línea de PARCIAL
# (JSONL). Si la corrida se corta (cuota, error de red), lo medido no se
# pierde y con --resume se retoma desde el primer caso pendiente.
# La primera línea guarda el pipeline: solo se retoma si config.toml no cambió.
salida = AQUI / cfg_eval["salida_dir"]
salida.mkdir(exist_ok=True)
ruta_parcial = salida / PARCIAL
pipeline = {s: cfg[s] for s in ("embeddings", "chunking", "retrieval", "llm")}

filas = []
if "--resume" in sys.argv and ruta_parcial.exists():
    cabecera, *lineas = ruta_parcial.read_text(encoding="utf-8").splitlines()
    if json.loads(cabecera)["pipeline"] != pipeline:
        sys.exit(f"{ruta_parcial.name} es de otro pipeline (config.toml cambió). "
                 "Corré sin --resume para empezar de cero.")
    filas = [json.loads(linea) for linea in lineas if linea.strip()]
    print(f"Retomando: {len(filas)} casos ya medidos en {ruta_parcial.name}")
else:
    ruta_parcial.write_text(json.dumps({"pipeline": pipeline}, ensure_ascii=False) + "\n",
                            encoding="utf-8")

hechos = {f["id"] for f in filas}
for caso in golden_set:
    if caso["id"] in hechos:
        continue
    print(f"\n[{caso['id']}] {caso['question']}")
    resp, contexts = con_reintentos(lambda: responder(caso["question"]))
    print(f"  answer: {resp.respuesta[:110]}")

    # Check determinista (no RAGAS): ¿se abstuvo cuando debía y solo cuando debía?
    abstencion_ok = resp.informacion_insuficiente == caso["debe_abstenerse"]

    if caso["debe_abstenerse"]:
        # Fuera de dominio: no hay ground_truth útil, las métricas no aplican (NaN).
        # Lo que importa acá es la abstención.
        scores = {m: float("nan") for m in METRICAS}
    else:
        scores = medir(caso["question"], resp.respuesta, contexts, caso["ground_truth"])

    print("  " + " | ".join(f"{m}={v:.2f}" for m, v in scores.items())
          + f" | abstencion_ok={abstencion_ok}")
    fila = {
        **caso,
        "answer": resp.respuesta,
        "contexts": contexts,
        "abstencion_ok": abstencion_ok,
        **scores,
    }
    filas.append(fila)
    with ruta_parcial.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    time.sleep(cfg_eval["pausa_segundos"])

# =============================================================================
# 6. Reporte: promedios, peores casos y diagnóstico
# =============================================================================
def promedio(valores):
    validos = [v for v in valores if not math.isnan(v)]  # NaN = métrica no aplica
    return sum(validos) / len(validos) if validos else float("nan")

promedios = {m: promedio([f[m] for f in filas]) for m in METRICAS}

print(f"\n{'=' * 70}\nRESULTADOS (promedio sobre casos con métrica aplicable)")
for m in METRICAS:
    # No alcanza con el promedio: mostramos el peor caso de cada métrica.
    peor = min((f for f in filas if not math.isnan(f[m])), key=lambda f: f[m])
    print(f"  {m:<18} {promedios[m]:.3f}   peor: {peor['id']} ({peor[m]:.2f})")

# Por categoría: un promedio global bueno puede esconder una categoría rota.
print("\nPor categoría:")
for cat in sorted({f["categoria"] for f in filas}):
    del_cat = [f for f in filas if f["categoria"] == cat]
    print(f"  {cat:<17}" + "  ".join(
        f"{m[:12]}={promedio([f[m] for f in del_cat]):.2f}" for m in METRICAS))

# Guardamos la corrida completa: sirve para inspeccionar casos (o cruzar con
# trazas de LangSmith) cuando una métrica cae.
corrida = {
    "fecha": datetime.now().isoformat(timespec="seconds"),
    "pipeline": pipeline,
    "promedios": promedios,
    "casos": filas,
}
archivo = salida / f"corrida_{datetime.now():%Y%m%d_%H%M%S}.json"
archivo.write_text(json.dumps(corrida, ensure_ascii=False, indent=2), encoding="utf-8")
ruta_parcial.unlink()  # la corrida terminó: el parcial ya no hace falta
print(f"\nDetalle guardado en {archivo.relative_to(AQUI)}")

# =============================================================================
# 7. Regresión: comparar contra el baseline y decidir (como un CI)
# =============================================================================

ruta_baseline = AQUI / cfg_eval["baseline"]

if "--baseline" in sys.argv or not ruta_baseline.exists():
    ruta_baseline.write_text(json.dumps(
        {"fecha": corrida["fecha"], "pipeline": corrida["pipeline"], "promedios": promedios},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline guardado en {ruta_baseline.name}. Cambiá config.toml y volvé a correr.")
    sys.exit(0)

baseline = json.loads(ruta_baseline.read_text(encoding="utf-8"))
print(f"\n{'=' * 70}\nREGRESIÓN vs baseline del {baseline['fecha']}")
fallos = []
for m in METRICAS:
    antes, ahora = baseline["promedios"][m], promedios[m]
    delta = ahora - antes
    estado = "ok"
    if delta < -cfg_eval["caida_maxima"][m]:
        estado = "CAYÓ"
        fallos.append(f"{m} bajó {abs(delta):.3f} (máximo permitido {cfg_eval['caida_maxima'][m]})")
    if ahora < cfg_eval["umbral_minimo"][m]:
        estado = "BAJO UMBRAL"
        fallos.append(f"{m} = {ahora:.3f} < umbral {cfg_eval['umbral_minimo'][m]}")
    print(f"  {m:<18} {antes:.3f} -> {ahora:.3f}  ({delta:+.3f})  {estado}")
    if estado != "ok":
        print(f"    revisar: {DIAGNOSTICO[m]}")

# Casos "must-pass": la abstención fuera de dominio es bloqueante aunque el
# promedio mejore (un RAG que inventa respuestas a todo es un riesgo real).
for f in filas:
    if not f["abstencion_ok"]:
        fallos.append(f"{f['id']}: abstención incorrecta (debe_abstenerse={f['debe_abstenerse']})")

if fallos:
    print("\nFALLO: no desplegar esta versión del pipeline.")
    for motivo in fallos:
        print(f"  - {motivo}")
    sys.exit(1)
print("\nOK: la versión candidata no empeora respecto del baseline.")
