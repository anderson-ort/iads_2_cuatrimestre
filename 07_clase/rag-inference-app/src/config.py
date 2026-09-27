import sys
from pathlib import Path

from dotenv import load_dotenv

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# Carga las claves de API de rag-inference-app/.env en el entorno (sin pisar
# variables ya definidas en el shell). HuggingFace no necesita clave.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración en: {path}")
    
    with open(path, "rb") as f:
        return tomllib.load(f)
