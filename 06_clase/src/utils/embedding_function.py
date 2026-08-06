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
            "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY", "RETRIEVAL_QUERY"
        ] = "RETRIEVAL_DOCUMENT",
    ):
        self.client = genai.Client()
        self.model = model_name
        self.dimension = dimension
        self.task_type = task_type

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []

        response = self.client.models.embed_content(
            model=self.model,
            contents=list(input),
            config=types.EmbedContentConfig(
                task_type=self.task_type, output_dimensionality=self.dimension
            ),
        )

        if response.embeddings is None:
            raise ValueError("La API de Gemini devolvió una respuesta vacía (None).")

        # CORRECCIÓN: Nos aseguramos de que cada embedding tenga valores y no sea None
        embeddings_list: list[list[float]] = []

        for emb in response.embeddings:
            if emb.values is None:
                raise ValueError(
                    "Uno de los contenidos no pudo ser transformado en embedding por Gemini."
                )
            embeddings_list.append(emb.values)

        return embeddings_list
