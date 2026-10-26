"""Tools for the ReAct agent. They wrap the same functions the deterministic nodes use."""

from langchain_core.tools import BaseTool, tool

from src.cuit import CuitClient, describe_cuit
from src.retrieval import HybridRetriever
from src.web import WebSearch


def build_tools(
    retriever: HybridRetriever, cuit_client: CuitClient, web: WebSearch
) -> list[BaseTool]:
    @tool
    def search_ortelana(query: str) -> str:
        """Search Ortelana's internal knowledge: fabric catalog (prices, stock, branch),
        discounts and promotions, shipping, and distributor onboarding rules."""
        docs = retriever.search(query)
        return "\n\n".join(d.page_content for d in docs) or "No internal results."

    @tool
    def lookup_cuit(cuit: str) -> str:
        """Look up the fiscal data (company name, tax status, address, activity, state)
        of an Argentine CUIT with 11 digits."""
        return describe_cuit(cuit_client, cuit)

    @tool
    def search_web(query: str) -> str:
        """Search public, up-to-date information on the internet."""
        return web.search(query)

    return [search_ortelana, lookup_cuit, search_web]
