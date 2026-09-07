from ortelana.db.chroma import get_products_collection as get_chroma_products
from ortelana.db.mongo import get_products_collection as get_mongo_products
from ortelana.models.product import Product
from ortelana.providers.factory import ProviderFactory


def start_change_stream_worker() -> None:
    mongo_col = get_mongo_products()
    chroma_col = get_chroma_products()
    embedder = ProviderFactory.get_embedding()

    print("Escuchando eventos en tiempo real en MongoDB Atlas (Change Streams)...")

    try:
        with mongo_col.watch() as stream:
            for change in stream:
                operation = change.get("operationType")
                doc_id = change.get("documentKey", {}).get("_id")

                if operation in ["insert", "update", "replace"]:
                    raw_doc = mongo_col.find_one({"_id": doc_id})
                    if not raw_doc:
                        continue

                    product = Product.model_validate(raw_doc)
                    embedding = embedder.embed_text(product.vector_document)

                    chroma_col.upsert(
                        ids=[product.id],
                        documents=[product.vector_document],
                        embeddings=[embedding],
                        metadatas=[product.metadatos.model_dump()],
                    )
                    print(f"Vector actualizado en ChromaDB para ID: {product.id}")

    except Exception as e:
        print(f"Error en el sincronizador continuo: {e}")


if __name__ == "__main__":
    start_change_stream_worker()