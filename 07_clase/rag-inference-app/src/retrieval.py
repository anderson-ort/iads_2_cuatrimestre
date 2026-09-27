from typing import List, Protocol, Tuple

# Protocol -> Funcionaria como una interfaz pues hace check de los metodos que estemos declarando.

from langchain_core.documents import Document
from langchain_chroma import Chroma


class Reranker(Protocol):
    def rerank(self, query: str, docs: List[Document], top_n: int) -> List[Document]: ...


class CrossEncoderReranker:
    """Cross-encoder local via sentence-transformers. Gratis, sin limite de
    llamadas ni API key: es la opcion por defecto para el free tier."""

    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, docs: List[Document], top_n: int) -> List[Document]:
        if not docs:
            return []
        pairs = [(query, d.page_content) for d in docs]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]


class CohereReranker:
    """Alternativa via API de Cohere (plan free: ~1000 llamadas/mes).
    Util si se prefiere no cargar el modelo local en memoria."""

    def __init__(self, api_key: str, model: str):
        import cohere

        self.client = cohere.Client(api_key)
        self.model = model

    def rerank(self, query: str, docs: List[Document], top_n: int) -> List[Document]:
        if not docs:
            return []
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=[d.page_content for d in docs],
            top_n=top_n,
        )
        return [docs[r.index] for r in response.results]


def biencoder_retrieve(vectorstore: Chroma, query: str, k: int) -> List[Document]:
    """Primera etapa: busqueda densa rapida (bi-encoder) con recall alto y
    precision moderada. El reranker refina estos candidatos despues."""
    return vectorstore.similarity_search(query, k=k)


def biencoder_retrieve_with_scores(vectorstore: Chroma, query: str, k: int) -> List[Tuple[Document, float]]:
    """Igual que biencoder_retrieve, pero conserva la distancia devuelta por
    Chroma para poder mostrarla en la UI didactica (menor distancia = mas
    similar). No se usa en el pipeline de produccion, solo para ensenar."""
    return vectorstore.similarity_search_with_score(query, k=k)


def embed_query_for_display(vectorstore: Chroma, query: str) -> List[float]:
    """Devuelve el vector de embedding de la consulta para mostrarlo en la UI
    (dimension y primeros valores) antes de hacer la busqueda. Cubre las dos
    formas en que langchain_chroma puede exponer la funcion de embeddings
    segun la version instalada."""
    embedding_fn = getattr(vectorstore, "embeddings", None) or getattr(
        vectorstore, "_embedding_function", None
    )
    if embedding_fn is None:
        raise AttributeError(
            "No se pudo acceder a la funcion de embeddings del vectorstore."
        )
    return embedding_fn.embed_query(query)
