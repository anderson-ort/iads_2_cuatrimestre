"""RAG de la clase 07 con observabilidad en LangSmith + evaluación RAGAS.

Es el mismo pipeline de ragas-ejemplo/ragas_eval.py (retrieval -> rerank -> LLM),
pero ahora cada ejecución queda registrada en LangSmith:

    RAGAS      -> "¿qué tan bueno fue el resultado?"  (números)
    LangSmith  -> "¿qué pasó adentro del pipeline?"  (traces navegables)

Dos modos:

  1. Observabilidad (un trace por pregunta, lo que pasaría en producción):

         uv run python langsmith_eval.py --pregunta "¿Qué descuento tiene la gabardina?"

     En la UI: Tracing Projects -> rag-ortelana-dev -> click en el trace.
     Se ve el árbol: rag_tecnico -> recuperar_chunks (chunks + scores) ->
     ChatPromptTemplate (prompt final) -> ChatGoogleGenerativeAI (tokens, latencia).

  2. Evaluación (el golden set como "experimento"):

         uv run python langsmith_eval.py

     a) Sube golden_set.json como Dataset de LangSmith (solo la primera vez).
     b) Corre el RAG sobre cada ejemplo del dataset (un trace por caso).
     c) Califica cada caso con evaluadores: las 4 métricas de RAGAS + abstención.
     d) Todo queda en Datasets & Experiments -> ortelana-golden-set-v1 -> experimento.
     e) Cambiás una perilla en config.toml, volvés a correr y comparás los dos
        experimentos lado a lado en la UI (botón "Compare").

Antes de correr: cp .env.sample .env y completar GOOGLE_API_KEY y LANGSMITH_API_KEY.
"""

import json
import logging
import math
import os
import sys
import time
import tomllib
from pathlib import Path

from dotenv import load_dotenv

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
logging.getLogger("instructor").setLevel(logging.CRITICAL)

# =============================================================================
# 0. Configuración
# =============================================================================
# load_dotenv va ANTES de importar LangChain/LangSmith: el tracing se activa
# leyendo LANGSMITH_TRACING, LANGSMITH_API_KEY y LANGSMITH_PROJECT del entorno.
# No hace falta ninguna otra línea de código para que LangChain mande traces.
AQUI = Path(__file__).resolve().parent
load_dotenv(AQUI / ".env")

import anydoc
from google import genai
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langsmith import Client, traceable
from langsmith.wrappers import wrap_openai
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

with open(AQUI / "config.toml", "rb") as f:
    cfg = tomllib.load(f)

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
if os.environ.get("LANGSMITH_TRACING", "").lower() != "true" or not os.environ.get("LANGSMITH_API_KEY"):
    sys.exit("Falta LANGSMITH_TRACING=true y/o LANGSMITH_API_KEY en .env (ver .env.sample).")

cfg_eval = cfg["evaluacion"]
METRICAS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

# Las perillas del pipeline viajan como metadata de cada trace y de cada
# experimento: en la UI se puede filtrar y comparar por top_n, chunk_size, etc.
pipeline = {
    "embeddings": cfg["embeddings"]["model_name"].split("/")[-1],
    "chunk_size": cfg["chunking"]["size"],
    "chunk_overlap": cfg["chunking"]["overlap"],
    "k_candidatos": cfg["retrieval"]["k_candidatos"],
    "top_n": cfg["retrieval"]["top_n"],
    "usar_reranker": cfg["retrieval"]["usar_reranker"],
    "rag_model": cfg["llm"]["rag_model"],
    "rag_temperature": cfg["llm"]["rag_temperature"],
}

# =============================================================================
# 1. Indexación (igual que ragas-ejemplo). Local: no genera traces.
# =============================================================================
embeddings = HuggingFaceEmbeddings(
    model_name=cfg["embeddings"]["model_name"],
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)
size, overlap = cfg["chunking"]["size"], cfg["chunking"]["overlap"]
vectorstore = Chroma(
    persist_directory=str(AQUI / cfg["ingesta"]["persist_dir"]),
    embedding_function=embeddings,
    collection_name=f"ortelana_{pipeline['embeddings']}_{size}_{overlap}",
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
# 2. Pipeline RAG instrumentado
# =============================================================================
# Dos formas de generar spans en LangSmith:
#   - Automática: todo Runnable de LangChain (prompt, LLM, structured output)
#     se traza solo con LANGSMITH_TRACING=true.
#   - Explícita: @traceable sobre funciones propias. Chroma + CrossEncoder no
#     pasan por un Runnable, así que sin el decorador el retrieval y el
#     rerank serían invisibles en el trace.

class RagAnswer(BaseModel):
    respuesta: str = Field(description="Respuesta directa y concisa a la pregunta")
    informacion_insuficiente: bool = Field(
        description="True si el contexto recuperado no contiene la respuesta"
    )

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
)
rag_chain = RAG_PROMPT | rag_llm.with_structured_output(RagAnswer)

k = cfg["retrieval"]["k_candidatos"]
top_n = cfg["retrieval"]["top_n"]
if cfg["retrieval"]["usar_reranker"]:
    from sentence_transformers import CrossEncoder
    cross_encoder = CrossEncoder(cfg["retrieval"]["crossencoder_model"])


# run_type="retriever": LangSmith muestra la salida como lista de documentos
# (contenido + metadata) en vez de JSON crudo. Guardamos los scores en la
# metadata de cada chunk para poder ver en el trace POR QUÉ quedó arriba.
@traceable(run_type="retriever", name="recuperar_chunks")
def recuperar(pregunta: str) -> list[Document]:
    """Retrieval + rerank. Devuelve los top_n docs en orden."""
    docs = []
    for d, distancia in vectorstore.similarity_search_with_score(pregunta, k=k):
        d.metadata["distancia_vectorial"] = round(float(distancia), 4)
        docs.append(d)
    if cfg["retrieval"]["usar_reranker"]:
        scores = cross_encoder.predict([(pregunta, d.page_content) for d in docs])
        for d, s in zip(docs, scores):
            d.metadata["score_reranker"] = round(float(s), 4)
        docs.sort(key=lambda d: d.metadata["score_reranker"], reverse=True)
    return docs[:top_n]


# run_type="chain" es el span padre: agrupa retrieval + prompt + LLM.
# tags/metadata quedan en el trace y sirven para filtrar en la UI.
@traceable(run_type="chain", name="rag_tecnico", tags=["rag", "ortelana"], metadata=pipeline)
def responder(pregunta: str) -> dict:
    docs = recuperar(pregunta)
    contexto = "\n\n---\n\n".join(f"[{d.metadata['filename']}]\n{d.page_content}" for d in docs)
    # Este invoke se anida solo dentro de "rag_tecnico" (LangChain detecta el span padre).
    resp = rag_chain.invoke({"pregunta": pregunta, "contexto": contexto})
    return {
        "answer": resp.respuesta,
        "informacion_insuficiente": resp.informacion_insuficiente,
        "contexts": [d.page_content for d in docs],
    }


def con_reintentos(fn, intentos=4):
    """Mismo manejo de cuota del free tier de Gemini que en ragas-ejemplo."""
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            if "PerDay" in str(e):
                sys.exit("Cuota diaria de Gemini agotada. El experimento parcial queda "
                         "en LangSmith; cambiá de modelo en config.toml o probá mañana.")
            reintentable = any(c in str(e) for c in ("429", "RESOURCE_EXHAUSTED", "503"))
            if not reintentable or i == intentos - 1:
                raise
            print("    (Gemini pidió esperar: rate limit o saturación, espero 30s...)")
            time.sleep(30)


# =============================================================================
# Modo 1: una sola pregunta -> un trace
# =============================================================================
if "--pregunta" in sys.argv:
    pregunta = sys.argv[sys.argv.index("--pregunta") + 1]
    salida = con_reintentos(lambda: responder(pregunta))
    print(f"\nRespuesta: {salida['answer']}")
    print(f"informacion_insuficiente={salida['informacion_insuficiente']}")
    print(f"\nTrace enviado al proyecto '{os.environ.get('LANGSMITH_PROJECT', 'default')}'.")
    print("Abrí https://smith.langchain.com -> Tracing Projects para verlo.")
    sys.exit(0)  # el cliente de LangSmith vacía la cola de traces al salir

# =============================================================================
# Modo 2, paso a: golden set -> Dataset de LangSmith
# =============================================================================
# Un Dataset es la versión "en la nube" del golden set. Cada Example tiene:
#   inputs           -> lo que recibe el RAG (la pregunta)
#   outputs          -> la referencia (ground_truth, debe_abstenerse)
#   metadata         -> id y categoría (para filtrar en la UI)
client = Client()
nombre_dataset = cfg["langsmith"]["dataset"]

if not client.has_dataset(dataset_name=nombre_dataset):
    golden_set = json.loads((AQUI / cfg_eval["golden_set"]).read_text(encoding="utf-8"))
    dataset = client.create_dataset(
        nombre_dataset, description="Golden set del RAG de OrTelana (clase 08)"
    )
    client.create_examples(dataset_id=dataset.id, examples=[
        {
            "inputs": {"question": c["question"]},
            "outputs": {"ground_truth": c["ground_truth"], "debe_abstenerse": c["debe_abstenerse"]},
            "metadata": {"id": c["id"], "categoria": c["categoria"]},
        }
        for c in golden_set
    ])
    print(f"Dataset '{nombre_dataset}' creado con {len(golden_set)} ejemplos.")
else:
    print(f"Dataset '{nombre_dataset}' ya existe en LangSmith: se reutiliza.")

# =============================================================================
# Modo 2, paso b: target = la función que LangSmith ejecuta por cada Example
# =============================================================================
# evaluate() llama al target con example.inputs y crea un trace por caso.
# Dentro de ese trace aparece todo el árbol de responder().
def rag_target(inputs: dict) -> dict:
    salida = con_reintentos(lambda: responder(inputs["question"]))
    time.sleep(cfg_eval["pausa_segundos"])
    return salida

# =============================================================================
# Modo 2, paso c: evaluadores (RAGAS adentro de LangSmith)
# =============================================================================
# Un evaluador recibe inputs (pregunta), outputs (lo que devolvió el target)
# y reference_outputs (lo del dataset) y devuelve {"key", "score", "comment"}.
# LangSmith guarda ese score como "feedback" del caso: aparece como columna
# en el experimento y permite ordenar por peor faithfulness, etc.
#
# wrap_openai: las llamadas del juez también se trazan (spans dentro de cada
# evaluador), así se ve qué afirmaciones extrajo y cómo las verificó.
juez_llm = llm_factory(
    cfg_eval["judge_model"],
    client=wrap_openai(AsyncOpenAI(
        api_key=GOOGLE_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )),
)
juez_embeddings = GoogleEmbeddings(
    client=genai.Client(api_key=GOOGLE_API_KEY), model=cfg_eval["judge_embeddings"]
)
faithfulness = Faithfulness(llm=juez_llm)
answer_relevancy = AnswerRelevancy(llm=juez_llm, embeddings=juez_embeddings, strictness=1)
context_precision = ContextPrecision(llm=juez_llm)
context_recall = ContextRecall(llm=juez_llm)

# Cada métrica pide solo las columnas que necesita (igual que en ragas-ejemplo).
CALCULOS = {
    "faithfulness": lambda q, o, gt: faithfulness.score(
        user_input=q, response=o["answer"], retrieved_contexts=o["contexts"]),
    "answer_relevancy": lambda q, o, gt: answer_relevancy.score(
        user_input=q, response=o["answer"]),
    "context_precision": lambda q, o, gt: context_precision.score(
        user_input=q, reference=gt, retrieved_contexts=o["contexts"]),
    "context_recall": lambda q, o, gt: context_recall.score(
        user_input=q, reference=gt, retrieved_contexts=o["contexts"]),
}


def evaluador_ragas(metrica):
    """Envuelve una métrica de RAGAS con la firma que espera LangSmith."""
    def evaluador(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        if reference_outputs["debe_abstenerse"]:
            # Fuera de dominio: sin ground_truth útil, la métrica no aplica.
            return {"key": metrica, "score": None, "comment": "No aplica (fuera de dominio)"}
        r = con_reintentos(lambda: CALCULOS[metrica](
            inputs["question"], outputs, reference_outputs["ground_truth"]))
        return {"key": metrica, "score": r.value, "comment": getattr(r, "reason", None)}
    evaluador.__name__ = metrica  # nombre del span del evaluador en la UI
    return evaluador


def abstencion_ok(outputs: dict, reference_outputs: dict) -> dict:
    """Check determinista (no RAGAS): ¿se abstuvo cuando debía y solo cuando debía?"""
    ok = outputs["informacion_insuficiente"] == reference_outputs["debe_abstenerse"]
    return {"key": "abstencion_ok", "score": ok}

# =============================================================================
# Modo 2, paso d: correr el experimento
# =============================================================================
# experiment_prefix: nombre legible del experimento (LangSmith le agrega un sufijo).
# metadata: las perillas, para saber qué cambió entre experimentos al comparar.
# max_concurrency=0: casos en serie, para no reventar la cuota de Gemini.
prefijo = f"top{top_n}-k{k}-chunk{size}-{'rerank' if pipeline['usar_reranker'] else 'norerank'}"
resultados = client.evaluate(
    rag_target,
    data=nombre_dataset,
    evaluators=[*(evaluador_ragas(m) for m in METRICAS), abstencion_ok],
    experiment_prefix=prefijo,
    description="RAG técnico de OrTelana evaluado con RAGAS (juez Gemini)",
    metadata=pipeline,
    max_concurrency=0,
)

# =============================================================================
# Modo 2, paso e: resumen local + quality gate (como en un CI)
# =============================================================================
# Los mismos números están en la UI; acá los recalculamos para poder cortar
# con exit code 1 si alguna métrica queda bajo el umbral mínimo.
valores = {m: [] for m in [*METRICAS, "abstencion_ok"]}
for fila in resultados:
    for r in fila["evaluation_results"]["results"]:
        if r.key in valores and r.score is not None and not math.isnan(float(r.score)):
            valores[r.key].append(float(r.score))

print(f"\n{'=' * 70}\nEXPERIMENTO {resultados.experiment_name}")
fallos = []
for m in METRICAS:
    prom = sum(valores[m]) / len(valores[m]) if valores[m] else float("nan")
    umbral = cfg_eval["umbral_minimo"][m]
    estado = "ok" if prom >= umbral else "BAJO UMBRAL"
    if estado != "ok":
        fallos.append(f"{m} = {prom:.3f} < umbral {umbral}")
    print(f"  {m:<18} {prom:.3f}  (umbral {umbral})  {estado}")
if valores["abstencion_ok"] and min(valores["abstencion_ok"]) < 1:
    fallos.append("hay casos con abstención incorrecta (filtrá abstencion_ok=0 en la UI)")

print("\nComparar contra otra corrida: Datasets & Experiments -> "
      f"{nombre_dataset} -> seleccionar 2 experimentos -> Compare.")
if fallos:
    print("\nFALLO: no desplegar esta versión del pipeline.")
    for motivo in fallos:
        print(f"  - {motivo}")
    sys.exit(1)
print("\nOK: todas las métricas sobre el umbral.")
