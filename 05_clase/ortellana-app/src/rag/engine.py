from typing import List
from ortelana.db.chroma import get_products_collection as get_chroma_products
from ortelana.db.mongo import get_products_collection as get_mongo_products
from ortelana.models.product import Product
from ortelana.models.rag import RAGResponse
from ortelana.providers.factory import ProviderFactory
from ortelana.rag.router import QueryRouter


class RAGEngine:
    def __init__(self):
        self.chroma_col = get_chroma_products()
        self.mongo_col = get_mongo_products()

    def query(self, user_query: str) -> RAGResponse:
        route_info = QueryRouter.route(user_query)
        embedder = ProviderFactory.get_embedding()
        llm = ProviderFactory.get_llm()

        query_embedding = embedder.embed_text(user_query)

        results = self.chroma_col.query(
            query_embeddings=[query_embedding], n_results=3
        )

        product_ids = results.get("ids", [[]])[0]
        retrieved_products: List[Product] = []

        if product_ids:
            raw_docs = list(self.mongo_col.find({"id": {"$in": product_ids}}))
            retrieved_products = [Product.model_validate(doc) for doc in raw_docs]

        context_items = [
            f"ID: {p.id} | Nombre: {p.nombre} | Descripción: {p.descripcion_semantica} | "
            f"Precio: ${p.metadatos.precio_metro} | Sucursal: {p.metadatos.sucursal_disponible} | "
            f"Stock: {'Disponible' if p.metadatos.en_stock else 'Agotado'}"
            for p in retrieved_products
        ]

        context_str = (
            "\n".join(context_items)
            if context_items
            else "No se encontraron productos coincidentes."
        )

        system_prompt = f"""Eres el asesor técnico y comercial de Ortelana Textil.
Responde a la consulta de forma profesional usando exclusivamente el siguiente contexto:

---
CONTEXTO DE PRODUCTOS DISPONIBLES:
{context_str}
---

Si los datos no permiten resolver la consulta, acláralo respetuosamente."""

        answer_text = llm.generate_response(user_query, system_instruction=system_prompt)

        return RAGResponse(
            query=user_query,
            intent=route_info.intent,
            answer=answer_text,
            sources=retrieved_products,
            provider=ProviderFactory.get_current_provider_name(),
        )