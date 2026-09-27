import sys
from pathlib import Path
from typing import Tuple

from langchain_chroma import Chroma

# Reutiliza el paquete ingester del proyecto hermano rag-anydoc-app.
ANY_DOC_APP = Path(__file__).resolve().parents[2] / "rag-anydoc-app"
if str(ANY_DOC_APP) not in sys.path:
    sys.path.insert(0, str(ANY_DOC_APP))

from ingester.config import load_config as load_ingester_config
from ingester.services import build_vector_manager as build_ingester_vector_manager
from ingester.vectorstore import VectorStoreManager

from config import load_config
from retrieval import CrossEncoderReranker, CohereReranker, Reranker
from router_chain import build_router_chain
from rag_chain import build_rag_chain

# El config.toml de esta app es la unica fuente de verdad de sus parametros
# (LLM, reranker, retrieval). El vectorstore, en cambio, se toma del
# config.toml de rag-anydoc-app para no desalinear la busqueda de la ingesta.
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"
INGESTER_CONFIG_PATH = ANY_DOC_APP / "config.toml"


def build_vector_manager(provider_key: str, api_key: str) -> VectorStoreManager:
    """Reutiliza la logica del ingester: el mapeo provider -> coleccion,
    dimensiones y modelo sale del config.toml de rag-anydoc-app. Asi la
    busqueda abre exactamente el vectorstore que creo la ingesta."""
    cfg = load_ingester_config(INGESTER_CONFIG_PATH)
    # persist_dir es relativo a rag-anydoc-app, no al CWD actual.
    cfg["vectorstore"]["persist_dir"] = str(
        (ANY_DOC_APP / cfg["vectorstore"]["persist_dir"]).resolve()
    )
    return build_ingester_vector_manager(provider_key, api_key, cfg)


def build_vectorstore(provider_key: str, api_key: str) -> Chroma:
    return build_vector_manager(provider_key, api_key).get_vectorstore()


def _collection_summary(manager: VectorStoreManager) -> dict:
    """Nombre de la coleccion y cantidad de chunks que se van a consultar.
    Sirve para detectar si se eligio un provider distinto al de la ingesta:
    en ese caso Chroma abre una coleccion vacia y el retrieval no devuelve nada."""
    stats = manager.get_stats()
    return {
        "collection_name": manager.collection_name,
        "total_chunks": stats["total_chunks"],
        "total_files": stats["total_files"],
    }


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
    manager = build_vector_manager(provider_key, embedding_api_key)
    vectorstore = manager.get_vectorstore()
    collection = _collection_summary(manager)
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
        "collection": collection,
        "reranker": reranker,
        "router": router,
        "rag_structured_llm": rag_structured_llm,
    }
