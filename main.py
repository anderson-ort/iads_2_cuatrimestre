import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from google import genai
from google.genai import types

from src.prompts import SYSTEM_INSTRUCTION
from src.models import MensajeEntrada, RespuestaExtraccion, ExtraccionOnboarding


load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
model = os.environ.get("GEMINI_MODEL_NAME","gemini-2.5-flash")

app = FastAPI(title="Ortelana Textil - Extraccion Onboarding")

@app.get("/")
def health() -> dict:
    return {"status": "ok"}


@app.post("/inference", response_model=RespuestaExtraccion)
def extraer(mensaje: MensajeEntrada) -> RespuestaExtraccion:
    try:
        response = client.models.generate_content(
            model=model,
            contents=mensaje.texto,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ExtraccionOnboarding,
                temperature=0.0,
            ),
        )
    except Exception as e:
        # Error de red, API key, rate limit, etc.
        raise HTTPException(status_code=502, detail=f"Error al llamar al modelo: {e}")

    try:
        datos = ExtraccionOnboarding.model_validate_json(response.text)

    except ValidationError as e:
        # El JSON llego bien formado pero violo una regla (ej: CUIT invalido)
        return RespuestaExtraccion(ok=False, error=e.errors()[0]["msg"])

    return RespuestaExtraccion(ok=True, datos=datos)
