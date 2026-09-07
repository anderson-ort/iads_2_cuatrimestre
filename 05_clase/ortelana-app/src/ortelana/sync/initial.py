from typing import List
from ortelana.db.chroma import get_products_collection as get_chroma_products
from ortelana.db.mongo import get_products_collection as get_mongo_products
from ortelana.models.product import Product
from ortelana.providers.factory import ProviderFactory


def run_initial_sync() -> None:
    mongo_col = get_mongo_products()
    chroma_col = get_chroma_products()  # Selecciona la colección dinámica según el proveedor activo
    embedder = ProviderFactory.get_embedding()
    provider_name = ProviderFactory.get_current_provider_name()

    raw_docs = list(mongo_col.find({}))
    if not raw_docs:
        print("No se encontraron productos en MongoDB Atlas para sincronizar.")
        return

    print(
        f"Cargando y validando {len(raw_docs)} productos desde MongoDB Atlas..."
    )
    products: List[Product] = [Product.model_validate(doc) for doc in raw_docs]

    ids = [p.id for p in products]
    documents = [p.vector_document for p in products]
    metadatas = [p.metadatos.model_dump() for p in products]

    print(
        f"Generando vectores mediante '{provider_name}' para la colección '{chroma_col.name}'..."
    )
    embeddings = embedder.embed_batch(documents)

    chroma_col.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(
        f"Sincronización exitosa: {len(ids)} vectores cargados en '{chroma_col.name}'."
    )


if __name__ == "__main__":
    run_initial_sync()