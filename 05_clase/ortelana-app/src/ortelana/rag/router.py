from ortelana.models.rag import QueryRoute
from ortelana.providers.factory import ProviderFactory


class QueryRouter:

    @staticmethod
    def route(query: str) -> QueryRoute:
        prompt = (
            f"Analiza la consulta: '{query}'."
            f"Devuelve un JSON con la propiedad 'intent' (valores permitidos: 'PRODUCT', 'DOCUMENT', 'HYBRID')."
        )

        llm = ProviderFactory.get_llm()
        return llm.extract_structured(prompt, QueryRoute)