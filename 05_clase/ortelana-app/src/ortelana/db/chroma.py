import chromadb
from chromadb.api import ClientAPI
from ortelana.config import settings
from ortelana.providers.factory import ProviderFactory

_client: ClientAPI | None = None


def get_chroma_client() -> ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT
        )
    return _client


def get_products_collection():
    client = get_chroma_client()
    provider_name = ProviderFactory.get_current_provider_name()
    collection_name = f"ortelana_products_{provider_name}"
    return client.get_or_create_collection(name=collection_name)