from ortelana.db.chroma import get_products_collection as get_chroma_products
from ortelana.db.mongo import get_products_collection as get_mongo_products

__all__ = ["get_mongo_products", "get_chroma_products"]