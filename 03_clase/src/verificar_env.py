"""
Chequeo rapido de que las credenciales estan cargadas correctamente
desde .env para Google GenAI.
"""

import os

from dotenv import load_dotenv

load_dotenv()

clave = os.getenv("GEMINI_API_KEY")
modelo = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

if clave is None:
    print("ERROR: no se encontro GEMINI_API_KEY. Revisa tu archivo .env")
else:
    print(f"OK: Clave cargada correctamente (termina en ...{clave[-4:]})")
    print(f"OK: Usando modelo configurado: {modelo}")
