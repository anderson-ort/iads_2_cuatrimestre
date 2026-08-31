import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODELO_LLM = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY no encontrada en el entorno.")

client = genai.Client()

# Actualizado al modelo estándar vigente
MODELO_EMBEDDINGS = "gemini-embedding-001"
# Dimensiones configuradas vía MRL
DIMENSION_EMBEDDINGS = 768
INDEX_FILE_PATH = "./database/ortelana_catalogo.index"
CATALOGO_JSON_PATH = "./database/catalogo.json"
