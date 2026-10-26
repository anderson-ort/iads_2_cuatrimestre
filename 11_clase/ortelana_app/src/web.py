"""Web search through the local SearXNG instance, falling back to DuckDuckGo."""

import logging

import httpx
from ddgs import DDGS
from ddgs.exceptions import DDGSException

from src.config import Settings

logger = logging.getLogger(__name__)


class WebSearch:
    def __init__(self, http: httpx.Client, searxng_url: str, max_results: int) -> None:
        self.http = http
        self.searxng_url = searxng_url.rstrip("/")
        self.max_results = max_results

    def search(self, query: str) -> str:
        try:
            results = self._searxng(query)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("SearXNG failed (%s), falling back to DuckDuckGo", exc)
            try:
                results = self._duckduckgo(query)
            except DDGSException as ddg_exc:
                return f"Web search unavailable: {ddg_exc}"
        if not results:
            return f"No web results for: {query!r}"
        return "\n\n".join(f"{r['title']}\n{r['url']}\n{r['snippet']}" for r in results)

    def _searxng(self, query: str) -> list[dict]:
        response = self.http.get(
            f"{self.searxng_url}/search", params={"q": query, "format": "json"}
        )
        response.raise_for_status()
        return [
            {"title": r["title"], "url": r["url"], "snippet": r.get("content", "")}
            for r in response.json()["results"][: self.max_results]
        ]

    def _duckduckgo(self, query: str) -> list[dict]:
        return [
            {"title": r["title"], "url": r["href"], "snippet": r["body"]}
            for r in DDGS().text(query, max_results=self.max_results)
        ]


def build_web_search(settings: Settings) -> WebSearch:
    http = httpx.Client(timeout=settings.web.timeout_seconds)
    return WebSearch(http, settings.web.searxng_url, settings.web.max_results)
