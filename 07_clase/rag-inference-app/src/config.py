import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración en: {path}")
    
    with open(path, "rb") as f:
        return tomllib.load(f)
