"""RAG + Router mínimo: pregunta -> router -> (tool mock | retrieval -> rerank -> LLM).

Lee la base Chroma que armó rag_simple.py (misma carpeta, mismo config.toml).
Correr desde rag-anydoc-app/ para usar su entorno:

    uv run python ../.muestra_clase/rag_inferencia.py
"""

import os
import tomllib
from enum import Enum
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

# 0. Configuración
AQUI = Path(__file__).resolve().parent
load_dotenv(AQUI / ".env")
with open(AQUI / "config.toml", "rb") as f:
    cfg = tomllib.load(f)

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
provider = cfg["embeddings"]["provider"]
p_cfg = cfg[provider]


# 1. Esquemas de salida: obligan al LLM a responder con estructura fija
class Intent(str, Enum):
    PROMOCIONES = "promociones"
    STOCK = "stock"
    TECNICO = "tecnico"
    OTRO = "otro"


class RouterDecision(BaseModel):
    intent: Intent = Field(description="Categoria de la consulta del usuario")
    producto: Optional[str] = Field(default=None, description="Producto mencionado, si aplica")
    justificacion: str = Field(description="Una oracion breve justificando la clasificacion")


class Fuente(BaseModel):
    archivo: str
    fragmento: str = Field(description="Extracto breve del chunk usado, maximo 25 palabras")


class RagAnswer(BaseModel):
    respuesta: str = Field(description="Respuesta directa y concisa a la pregunta")
    confianza: str = Field(description="alta | media | baja")
    informacion_insuficiente: bool = Field(
        description="True si el contexto recuperado no contiene la respuesta"
    )
    fuentes: List[Fuente] = Field(default_factory=list)


# 2. Prompts
ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Clasificas la consulta de un usuario en una de estas categorias:\n"
     "- promociones: descuentos, ofertas, cuotas.\n"
     "- stock: disponibilidad o cantidad de un producto.\n"
     "- tecnico: dudas conceptuales, politicas, documentacion, procedimientos.\n"
     "- otro: cualquier otra cosa.\n"
     "Responde unicamente con el esquema pedido."),
    ("human", "{pregunta}"),
])

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Respondes preguntas usando SOLO el contexto entregado. No inventes datos. "
     "Si el contexto no alcanza, marca informacion_insuficiente=true y dilo en "
     "'respuesta' en vez de adivinar. Cita cada fuente que uses en 'fuentes'."),
    ("human", "Contexto:\n{contexto}\n\nPregunta: {pregunta}"),
])

# 3. Herramientas mock (ramas stock y promociones): datos fijos, sin base real
MOCK_STOCK = {"notebook": 12, "monitor": 0, "teclado": 34}
MOCK_PROMOS = {
    "notebook": ["15% off con tarjeta X", "3 cuotas sin interes"],
    "monitor": ["2x1 en accesorios"],
}

# 4. Embeddings + base vectorial (los mismos que usó la ingesta)
if provider == "huggingface":
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(
        model_name=p_cfg["model_name"],
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
elif provider == "gemini":
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    embeddings = GoogleGenerativeAIEmbeddings(
        model=p_cfg["model_name"],
        google_api_key=os.environ["GEMINI_API_KEY"],
        output_dimensionality=p_cfg["dimensions"],
    )
elif provider == "cohere":
    from langchain_cohere import CohereEmbeddings
    embeddings = CohereEmbeddings(
        model=p_cfg["model_name"], cohere_api_key=os.environ["COHERE_API_KEY"]
    )
else:
    raise ValueError(f"Proveedor desconocido: {provider}")

vectorstore = Chroma(
    persist_directory=str(AQUI / cfg["vectorstore"]["persist_dir"]),
    embedding_function=embeddings,
    collection_name=p_cfg["collection_name"],
)
total_chunks = len(vectorstore.get()["ids"])
print(f"Colección: {p_cfg['collection_name']} | {total_chunks} chunks")
if total_chunks == 0:
    print("La colección está vacía: corré primero rag_simple.py con modo ingest.")

# 5. Reranker: reordena los candidatos del bi-encoder
tipo_reranker = cfg["reranker"]["tipo"]
if tipo_reranker == "crossencoder":
    from sentence_transformers import CrossEncoder
    cross_encoder = CrossEncoder(cfg["reranker"]["crossencoder_model"])

    def rerank(pregunta, docs, top_n):
        scores = cross_encoder.predict([(pregunta, d.page_content) for d in docs])
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]
elif tipo_reranker == "cohere":
    import cohere
    cohere_client = cohere.Client(os.environ["COHERE_API_KEY"])

    def rerank(pregunta, docs, top_n):
        resp = cohere_client.rerank(
            model=cfg["reranker"]["cohere_model"],
            query=pregunta,
            documents=[d.page_content for d in docs],
            top_n=top_n,
        )
        return [docs[r.index] for r in resp.results]
else:
    raise ValueError(f"Reranker desconocido: {tipo_reranker}")

# 6. LLMs: with_structured_output devuelve objetos Pydantic, no texto libre
router_llm = ChatGoogleGenerativeAI(
    model=cfg["llm"]["router_model"],
    google_api_key=GOOGLE_API_KEY,
    temperature=cfg["llm"]["router_temperature"],
)
router = ROUTER_PROMPT | router_llm.with_structured_output(RouterDecision)

rag_llm = ChatGoogleGenerativeAI(
    model=cfg["llm"]["rag_model"],
    google_api_key=GOOGLE_API_KEY,
    temperature=cfg["llm"]["rag_temperature"],
)
rag_chain = RAG_PROMPT | rag_llm.with_structured_output(RagAnswer)

# 7. Pipeline: una vuelta por cada pregunta del config
k = cfg["retrieval"]["k_candidatos"]
top_n = cfg["retrieval"]["top_n"]

for pregunta in cfg["inferencia"]["preguntas"]:
    print(f"\n{'=' * 70}\nPregunta: {pregunta}")

    # Router: clasificar la intención
    decision = router.invoke({"pregunta": pregunta})
    print(f"Router: {decision.intent.value} | producto={decision.producto} | {decision.justificacion}")
    producto = (decision.producto or "").strip().lower()

    if decision.intent == Intent.STOCK:
        cantidad = MOCK_STOCK.get(producto)
        if cantidad is None:
            print("Respuesta: producto no encontrado en el catálogo.")
        else:
            print(f"Respuesta: quedan {cantidad} unidades de {producto}.")

    elif decision.intent == Intent.PROMOCIONES:
        promos = MOCK_PROMOS.get(producto) if producto else [
            f"{p}: {', '.join(v)}" for p, v in MOCK_PROMOS.items()
        ]
        print("Respuesta:", "; ".join(promos) if promos else "sin promociones.")

    elif decision.intent == Intent.TECNICO:
        # Retrieval: bi-encoder trae k candidatos por cercanía
        candidatos = vectorstore.similarity_search_with_score(pregunta, k=k)
        print(f"Retrieval: {len(candidatos)} candidatos")
        for i, (doc, score) in enumerate(candidatos, start=1):
            print(f"  #{i} dist={score:.4f} [{doc.metadata['filename']}]")

        # Rerank: cross-encoder elige los top_n más relevantes
        top_docs = rerank(pregunta, [doc for doc, _ in candidatos], top_n) if candidatos else []
        print(f"Rerank: {len(top_docs)} documentos finales")
        for i, doc in enumerate(top_docs, start=1):
            print(f"  #{i} [{doc.metadata['filename']}] {doc.page_content[:60].replace(chr(10), ' ')}...")

        # Generación: LLM responde solo con el contexto recuperado
        contexto = "\n\n---\n\n".join(
            f"[{d.metadata['filename']}]\n{d.page_content}" for d in top_docs
        ) or "(sin resultados relevantes)"
        resp = rag_chain.invoke({"pregunta": pregunta, "contexto": contexto})
        if resp.informacion_insuficiente:
            print("Respuesta: no tengo información suficiente en la base para responder eso.")
        else:
            print(f"Respuesta ({resp.confianza}): {resp.respuesta}")
            for fuente in resp.fuentes:
                print(f"  - fuente: {fuente.archivo} - {fuente.fragmento}")

    else:
        print("Respuesta: no pude clasificar la consulta. Reformule, por favor.")
