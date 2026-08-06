from typing import Optional

import chromadb
from chromadb.api.types import EmbeddingFunction

# Se puede usar por medio de variables de entorno, lo que seria lo recomendado

DB_PATH = "./ortelana_vector_db"
COLECCION = "catalogo_telas"


class OrtelanaCatalogRepository:
    """
    CRUD puro para interactuar con ChromaDB. No tiene reglas de negocio complejas.
    """

    def __init__(
        self,
        embedding_function: EmbeddingFunction,
        db_path: str = DB_PATH,
        collection_name: str = COLECCION,
    ):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
            metadata={"descripcion": "Catálogo unificado de telas de Ortelana Textil"},
        )

    def count(self) -> int:
        return self.collection.count()

    def get_existing_ids(self) -> set[str]:
        response = self.collection.get(include=[])
        return set(response["ids"])

    def create_or_upsert_batch(
        self, ids: list[str], documents: list[str], metadatas: list[dict]
    ):
        if not ids:
            return

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query_hybrid(
        self, query_text: str, where_filter: Optional[dict] = None, n_results: int = 2
    ) -> dict:

        kwargs = {"query_texts": [query_text], "n_results": n_results}

        if where_filter:
            kwargs["where"] = where_filter
        return self.collection.query(**kwargs)

    def update_metadata_fields(self, id_registro: str, updates: dict):

        registro_actual = self.collection.get(ids=[id_registro], include=["metadatas"])

        if not registro_actual["ids"]:
            raise ValueError(f"El registro con ID '{id_registro}' no existe.")

        metadatos_actualizados = dict(registro_actual["metadatas"][0])
        metadatos_actualizados.update(updates)

        self.collection.update(ids=[id_registro], metadatas=[metadatos_actualizados])
