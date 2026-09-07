from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ACTIVE_PROVIDER: str = Field(default="gemini")

    # Gemini
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_LLM_MODEL: str = Field(default="gemini-2.5-flash")
    GEMINI_EMBED_MODEL: str = Field(default="embedding-001")

    # Cohere
    COHERE_API_KEY: str = Field(default="")
    COHERE_LLM_MODEL: str = Field(default="command-r-plus")
    COHERE_EMBED_MODEL: str = Field(default="embed-multilingual-light-v3.0")

    # Infraestructura
    MONGODB_URI: str = Field(default="mongodb://localhost:27017")
    MONGODB_DATABASE: str = Field(default="ortelana_db")
    CHROMADB_HOST: str = Field(default="localhost")
    CHROMADB_PORT: int = Field(default=8000)


settings = Settings()