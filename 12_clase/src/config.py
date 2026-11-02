"""Typed settings: non-secret values from config.toml, secrets from .env."""

import logging
import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = ROOT / ".env"


class ProviderConfig(BaseModel):
    chat_model: str
    fast_model: str
    embedding_model: str
    embedding_dimensions: int | None = None


class LLMConfig(BaseModel):
    provider: Literal["google", "cohere"]
    temperature: float = 0.0
    google: ProviderConfig
    cohere: ProviderConfig

    @property
    def active(self) -> ProviderConfig:
        return getattr(self, self.provider)


class IngestConfig(BaseModel):
    documents_dir: Path
    chunk_size: int
    chunk_overlap: int


class MongoConfig(BaseModel):
    catalog_database: str
    catalog_collection: str
    checkpoint_database: str


class ChromaConfig(BaseModel):
    persist_dir: Path
    collection: str


class RetrievalConfig(BaseModel):
    k_candidates: int
    rrf_k: int = 60
    top_n: int
    rerank_model: str


class SupabaseConfig(BaseModel):
    url: str
    table: str
    timeout_seconds: float = 10


class WebConfig(BaseModel):
    searxng_url: str
    max_results: int
    timeout_seconds: float = 10


class GuardrailsConfig(BaseModel):
    config_dir: Path
    competitors: list[str]


class ApiConfig(BaseModel):
    host: str
    port: int


class LangSmithConfig(BaseModel):
    tracing: bool
    project: str


class EvaluationConfig(BaseModel):
    datasets_dir: Path
    judge_model: str
    judge_embedding_model: str
    retry_wait_seconds: float = 30


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    google_api_key: SecretStr | None = None
    cohere_api_key: SecretStr
    mongodb_uri: SecretStr
    supabase_key: SecretStr
    langsmith_api_key: SecretStr | None = None


class Settings(BaseModel):
    root: Path
    llm: LLMConfig
    ingest: IngestConfig
    mongo: MongoConfig
    chroma: ChromaConfig
    retrieval: RetrievalConfig
    supabase: SupabaseConfig
    web: WebConfig
    guardrails: GuardrailsConfig
    api: ApiConfig
    langsmith: LangSmithConfig
    evaluation: EvaluationConfig
    secrets: Secrets

    @property
    def collection_name(self) -> str:
        # Each provider produces vectors of a different dimension.
        return f"{self.chroma.collection}_{self.llm.provider}"

    def path(self, relative: Path) -> Path:
        return self.root / relative


def load_settings(
    path: Path = ROOT / "config.toml", env_file: Path | None = DEFAULT_ENV_FILE
) -> Settings:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return Settings(root=path.parent, secrets=Secrets(_env_file=env_file), **raw)


def configure_tracing(settings: Settings) -> None:
    """LangSmith reads its settings from the environment, so export them from config."""
    key = settings.secrets.langsmith_api_key
    if settings.langsmith.tracing and key is None:
        logger.warning("LangSmith tracing disabled: LANGSMITH_API_KEY is not set")
    os.environ["LANGSMITH_TRACING"] = str(settings.langsmith.tracing and key is not None).lower()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith.project
    if key is not None:
        os.environ["LANGSMITH_API_KEY"] = key.get_secret_value()
