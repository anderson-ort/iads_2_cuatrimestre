from .embeddings import (
    HuggingFaceEmbeddingProvider,
    GeminiEmbeddingProvider,
    CohereEmbeddingProvider,
)
from .vectorstore import VectorStoreManager

# (clase, seccion del config.toml, requiere api key)
PROVIDERS_MAP = {
    "huggingface": (HuggingFaceEmbeddingProvider, "huggingface", False),
    "gemini": (GeminiEmbeddingProvider, "gemini", True),
    "cohere": (CohereEmbeddingProvider, "cohere", True),
}


def resolve_provider_key(provider_option: str) -> str:
    """Traduce una opción de UI/CLI (ej. 'Google Gemini') a la clave canónica."""
    provider_key = next((k for k in PROVIDERS_MAP if k in provider_option.lower()), None)

    if not provider_key:
        raise ValueError(f"Proveedor no reconocido: {provider_option}")

    return provider_key


def build_embedding_provider(provider_key: str, api_key: str, config: dict):
    cls, config_section, requires_api_key = PROVIDERS_MAP[provider_key]
    model_name = config[config_section]["model_name"]
    kwargs = {"model_name": model_name}

    dimensions = config[config_section].get("dimensions")
    if dimensions:
        kwargs["dimensions"] = dimensions

    if requires_api_key:
        if not api_key:
            raise ValueError(f"El proveedor '{provider_key}' requiere una API key.")
        kwargs["api_key"] = api_key

    return cls(**kwargs)


def build_vector_manager(provider_key: str, api_key: str, config: dict) -> VectorStoreManager:
    """Arma el VectorStoreManager con el proveedor y la colección que le corresponde."""
    provider = build_embedding_provider(provider_key, api_key, config)
    return VectorStoreManager(
        embedding_provider=provider,
        persist_dir=config["vectorstore"]["persist_dir"],
        collection_name=config[provider_key]["collection_name"],
    )
