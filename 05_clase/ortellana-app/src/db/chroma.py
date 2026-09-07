import chromadb
from chromadb.api.models.Collection import Collection
from ortelana.config import settings

_client: chromadb.HttpClient | None = None


def get_chroma_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT
        )
    return _client


def get_products_collection() -> Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(name="ortelana_products")