from pymongo import MongoClient
from pymongo.collection import Collection
from ortelana.config import settings

_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client


def get_products_collection() -> Collection:
    client = get_mongo_client()
    db = client[settings.MONGODB_DATABASE]
    print(db)
    return db["catalogo"]