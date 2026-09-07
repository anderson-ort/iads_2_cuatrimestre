from ortelana.models.rag import QueryRoute
from ortelana.providers.factory import ProviderFactory


class QueryRouter:
    @staticmethod
    def route(query: str) -> QueryRoute:
        prompt = f"""Analiza la consulta del cliente de Ortelana Textil y clasifica su intención:
Consulta: "{query}"

Reglas:
- PRODUCT: Si busca telas, disponibilidad, precios, tipos de tejido o materiales.
- DOCUMENT: Si pregunta por temas administrativos, métodos de envío, políticas de compra o pagos.
- HYBRID: Si combina ambas intenciones."""

        llm = ProviderFactory.get_llm()
        return llm.extract_structured(prompt, QueryRoute)