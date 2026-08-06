# extractor_validado.py
"""
Extractor de datos de distribuidores con Structured Outputs nativo de Google GenAI
y validacion Pydantic V2.
Implementa el marco teorico de la Clase 3:
  1. Garantia del Proveedor: Gemini fuerza la salida JSON estructurada bajo response_schema.
  2. Garantia de Aplicacion: Pydantic recibe ese JSON y ejecuta coaccion y validadores.
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import ValidationError
from schemas import DistribuidorOnboardingSchema

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

SYSTEM_PROMPT = """
Eres un sistema de extraccion de datos para Ortelana Textil.
Tu tarea es leer mensajes de texto libre enviados por distribuidores mayoristas
y mapear la informacion estrictamente al esquema JSON solicitado.

No inventes datos que no esten en el mensaje. Si un campo no esta presente, usa null.
NUNCA asignes valor True al campo cuit_verificado_externamente: eso lo decide unicamente el backend.
"""


def extraer_con_structured_outputs(mensaje: str) -> dict:
    """
    Llama a Gemini exigiendo cumplimiento del esquema Pydantic y captura
    tanto colapsos de infraestructura, cuota o validacion de aplicacion.
    """
    resultado = {
        "mensaje_original": mensaje,
        "colapso_proveedor": False,
        "colapso_aplicacion": False,
        "datos_validados": None,
        "error": None,
    }

    try:
        # Garantía del Proveedor: Pasamos el esquema directamente a la configuración
        respuesta = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=mensaje,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=500,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=DistribuidorOnboardingSchema,
            ),
        )
        texto_json = respuesta.text
    except errors.ClientError as e:
        resultado["colapso_proveedor"] = True
        resultado["error"] = (
            f"Falla o limite de cuota (429/ClientError) con Gemini: {e.message}"
        )
        return resultado
    except Exception as e:
        resultado["colapso_proveedor"] = True
        resultado["error"] = f"Falla critica de comunicacion con el proveedor: {e}"
        return resultado

    # Garantía de Aplicación: Validación secundaria en Python (custom field_validators)
    try:
        datos_dict = json.loads(texto_json)
        datos_validados = DistribuidorOnboardingSchema(**datos_dict)
        resultado["datos_validados"] = datos_validados.model_dump()
    except json.JSONDecodeError as e:
        resultado["colapso_aplicacion"] = True
        resultado["error"] = f"Gemini devolvio un texto que no es JSON valido: {e}"
    except ValidationError as e:
        resultado["colapso_aplicacion"] = True
        resultado["error"] = (
            f"Los datos de Gemini violaron las reglas de negocio de Ortelana: {e}"
        )

    return resultado


if __name__ == "__main__":
    mensaje_prueba = """
    Hola gente de Ortelana! Soy del taller 'Modas del Sur', mi cuit es el
    20-34556789-2. Quiero registrarme como distribuidor mayorista, vendemos
    indumentaria femenina. Contacto: Claudia Torres, ctorres@modasdelsur.com.ar.
    Me gustaria aplicar a la categoria VIP Oro si es posible.
    """

    resultado = extraer_con_structured_outputs(mensaje_prueba)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
