from ortelana.config import settings
from ortelana.providers.base import BaseEmbeddingProvider, BaseLLMProvider
from ortelana.providers.cohere_provider import (
    CohereEmbeddingProvider,
    CohereLLMProvider,
)
from ortelana.providers.gemini_provider import (
    GeminiEmbeddingProvider,
    GeminiLLMProvider,
)


class ProviderFactory:
    _current_provider = settings.ACTIVE_PROVIDER

    @classmethod
    def set_provider(cls, name: str) -> None:
        if name.lower() not in ["gemini", "cohere"]:
            raise ValueError("Provider no soportado. Opciones: 'gemini' o 'cohere'.")
        cls._current_provider = name.lower()

    @classmethod
    def get_llm(cls) -> BaseLLMProvider:
        if cls._current_provider == "cohere":
            return CohereLLMProvider()
        return GeminiLLMProvider()

    @classmethod
    def get_embedding(cls) -> BaseEmbeddingProvider:
        if cls._current_provider == "cohere":
            return CohereEmbeddingProvider()
        return GeminiEmbeddingProvider()

    @classmethod
    def get_current_provider_name(cls) -> str:
        return cls._current_provider