"""Chat and embedding model factories for the configured provider (Google GenAI or Cohere)."""

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from src.config import Settings


def _google_key(settings: Settings):
    key = settings.secrets.google_api_key
    if key is None:
        raise ValueError("GOOGLE_API_KEY is required when llm.provider = 'google'")
    return key


def chat_model(settings: Settings, *, fast: bool = False) -> BaseChatModel:
    """Return the chat model; `fast` selects the cheap model used for routing."""
    cfg = settings.llm.active
    model = cfg.fast_model if fast else cfg.chat_model

    if settings.llm.provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=settings.llm.temperature,
            google_api_key=_google_key(settings),
        )

    from langchain_cohere import ChatCohere

    return ChatCohere(
        model=model,
        temperature=settings.llm.temperature,
        cohere_api_key=settings.secrets.cohere_api_key,
    )


def embeddings(settings: Settings) -> Embeddings:
    cfg = settings.llm.active

    if settings.llm.provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=cfg.embedding_model,
            output_dimensionality=cfg.embedding_dimensions,
            google_api_key=_google_key(settings),
        )

    from langchain_cohere import CohereEmbeddings

    return CohereEmbeddings(
        model=cfg.embedding_model, cohere_api_key=settings.secrets.cohere_api_key
    )
