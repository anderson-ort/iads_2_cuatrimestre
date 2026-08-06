"""
ChromaDB Custom con Google
Integra directamente el modelo de  gemini-embedding-001  directamente.

Implementa la interfaz EmbeddingFunction de ChromaDB usando
gemini-embedding-001. Usa task_type=RETRIEVAL_DOCUMENT por defecto
porque ChromaDB usa la misma funcion tanto para indexar documentos
como para embeber las consultas de collection.query(); en un caso
de uso mas avanzado se separarian ambos task_type con dos funciones.
"""

import os
from typing import Literal

from chromadb import Documents, EmbeddingFunction, Embeddings
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


MODELO_EMBEDDING = os.getenv("GEMINI_MODELO_EMBEDDING", "gemini-embedding-001")
DIMENSION = int(os.getenv("GEMINI_MODELO_EMBEDDING_DIMENSION", "768"))


class EmbeddingFunctionGemini(EmbeddingFunction):
    def __init__(
        self,
        model_name: str = MODELO_EMBEDDING,
        dimension: int = DIMENSION,
        task_type: Literal[
            "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY"
        ] = "RETRIEVAL_DOCUMENT",
    ):
        self.client = genai.Client()
        self.model = model_name
        self.dimension = dimension
        self.task_type = task_type

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model=self.model,
            contents=list(input),
            config=types.EmbedContentConfig(
                task_type=self.task_type, output_dimensionality=self.dimension
            ),
        )
        return [emb.values for emb in response.embeddings]
