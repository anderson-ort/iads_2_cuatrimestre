import sys
from pathlib import Path
from typing import Tuple

from langchain_chroma import Chroma

# Reutiliza el paquete ingester del proyecto hermano rag-anydoc-app.
ANY_DOC_APP = Path(__file__).resolve().parents[2] / "rag-anydoc-app"
if str(ANY_DOC_APP) not in sys.path:
    sys.path.insert(0, str(ANY_DOC_APP))

from ingester.embeddings import (
    HuggingFaceEmbeddingProvider,
    GeminiEmbeddingProvider,
    CohereEmbeddingProvider,
)
from ingester.vectorstore import VectorStoreManager

from config import load_config
from retrieval import CrossEncoderReranker, CohereReranker, Reranker
from router_chain import build_router_chain
from rag_chain import build_rag_chain

# El config.toml de esta app es la unica fuente de verdad de sus parametros.
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"

# (clase, seccion del config.toml, requiere api key)
EMBEDDING_PROVIDERS = {
    "huggingface": (HuggingFaceEmbeddingProvider, "huggingface", False),
    "gemini": (GeminiEmbeddingProvider, "gemini", True),
    "cohere": (CohereEmbeddingProvider, "cohere", True),
}


def build_embedding_provider(provider_key: str, api_key: str):
    cls, section, requires_api_key = EMBEDDING_PROVIDERS[provider_key]
    model_name = load_config(CONFIG_PATH)[section]["model_name"]
    kwargs = {"model_name": model_name}
    if requires_api_key:
        if not api_key:
            raise ValueError(f"El proveedor '{provider_key}' requiere una API key.")
        kwargs["api_key"] = api_key
    return cls(**kwargs)


def build_vector_manager(provider_key: str, api_key: str) -> VectorStoreManager:
    cfg = load_config(CONFIG_PATH)
    # persist_dir es relativo a rag-anydoc-app, no al CWD actual.
    persist_dir = str((ANY_DOC_APP / cfg["vectorstore"]["persist_dir"]).resolve())
    provider = build_embedding_provider(provider_key, api_key)
    return VectorStoreManager(
        embedding_provider=provider,
        persist_dir=persist_dir,
        collection_name=cfg["vectorstore"]["collection_name"],
    )


def build_vectorstore(provider_key: str, api_key: str) -> Chroma:
    return build_vector_manager(provider_key, api_key).get_vectorstore()


def build_reranker(nombre: str, cohere_api_key: str) -> Reranker:
    cfg = load_config(CONFIG_PATH)["reranker"]
    if nombre == "cohere":
        if not cohere_api_key:
            raise ValueError("El reranker de Cohere requiere una API key.")
        return CohereReranker(api_key=cohere_api_key, model=cfg["cohere_model"])
    return CrossEncoderReranker(model_name=cfg["crossencoder_model"])


def build_pipeline(
    google_api_key: str,
    provider_key: str,
    embedding_api_key: str,
    reranker_nombre: str,
    cohere_api_key: str,
) -> Tuple:
    """Pipeline compuesto (router | rag_chain), sin exponer los pasos
    intermedios: para eso ver build_components()."""
    cfg = load_config(CONFIG_PATH)
    vectorstore = build_vectorstore(provider_key, embedding_api_key)
    reranker = build_reranker(reranker_nombre, cohere_api_key)
    router = build_router_chain(
        api_key=google_api_key,
        model_name=cfg["llm"]["router_model"],
        temperature=cfg["llm"]["router_temperature"],
        thinking_budget=cfg["llm"]["router_thinking_budget"],
    )
    rag_chain = build_rag_chain(
        api_key=google_api_key,
        vectorstore=vectorstore,
        reranker=reranker,
        model_name=cfg["llm"]["rag_model"],
        temperature=cfg["llm"]["rag_temperature"],
        k=cfg["retrieval"]["k_candidatos"],
        top_n=cfg["retrieval"]["top_n"],
    )
    return router, rag_chain


def build_components(
    google_api_key: str,
    provider_key: str,
    embedding_api_key: str,
    reranker_nombre: str,
    cohere_api_key: str,
) -> dict:
    """Arma las mismas piezas que build_pipeline pero sueltas, sin componerlas
    en una cadena. Pensado para los entrypoints didacticos (app.py y cli.py): cada
    pieza (vectorstore, reranker, router, LLM estructurado del RAG) se invoca
    por separado para poder mostrar el resultado de cada paso en pantalla."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    from schemas import RagAnswer

    cfg = load_config(CONFIG_PATH)
    vectorstore = build_vectorstore(provider_key, embedding_api_key)
    reranker = build_reranker(reranker_nombre, cohere_api_key)
    router = build_router_chain(
        api_key=google_api_key,
        model_name=cfg["llm"]["router_model"],
        temperature=cfg["llm"]["router_temperature"],
        thinking_budget=cfg["llm"]["router_thinking_budget"],
    )

    rag_llm = ChatGoogleGenerativeAI(
        model=cfg["llm"]["rag_model"],
        google_api_key=google_api_key,
        temperature=cfg["llm"]["rag_temperature"],
    )
    rag_structured_llm = rag_llm.with_structured_output(RagAnswer)

    return {
        "vectorstore": vectorstore,
        "reranker": reranker,
        "router": router,
        "rag_structured_llm": rag_structured_llm,
    }
