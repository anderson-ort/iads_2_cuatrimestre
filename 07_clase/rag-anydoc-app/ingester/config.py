import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Proveedor de embeddings -> variable de entorno con su API key.
API_KEY_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY",
}


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración en: {path}")
    
    with open(path, "rb") as f:
        return tomllib.load(f)


def get_api_key(provider_key: str) -> str:
    """Devuelve la API key del proveedor leída del entorno (cargado desde .env)."""
    env_var = API_KEY_ENV_VARS.get(provider_key)
    return os.environ.get(env_var, "") if env_var else ""
