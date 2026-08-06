"""
Wrapper que adapta EmbeddingFunctionGemini (interfaz ChromaDB) a la interfaz Embeddings que LangChain espera para su retriever de Chroma.
"""

from typing import Literal, cast

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings as LangChainEmbeddings
from utils.embedding_function import EmbeddingFunctionGemini

load_dotenv()


class GeminiEmbeddingsLangchain(LangChainEmbeddings):
    """
    Adapta EmbeddingFunctionGemini al contrato de LangChain.
    """

    def __init__(
        self,
        task_type: Literal[
            "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY"
        ] = "RETRIEVAL_DOCUMENT",
    ):
        self._fn_docs = EmbeddingFunctionGemini(task_type=task_type)
        self._fn_query = EmbeddingFunctionGemini(task_type="RETRIEVAL_QUERY")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Usado por LangChain al indexar documentos."""
        # Usamos `cast` para asegurarle al linter que la salida de ChromaDB
        # es exactamente la lista de listas de floats que LangChain espera.
        return cast(list[list[float]], self._fn_docs(texts))

    def embed_query(self, text: str) -> list[float]:
        """Usado por el Retriever de LangChain para embeber la consulta."""
        # Al extraer el primer elemento ([0]), el linter puede dudar si es un float o una lista.
        # Forzamos el tipo esperado por LangChain.
        res = self._fn_query([text])[0]
        return cast(list[float], res)
