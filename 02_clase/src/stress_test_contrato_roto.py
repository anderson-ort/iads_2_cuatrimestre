"""
Laboratorio "El Contrato Roto" - Clase 2
Procesa el lote de 15 mensajes contra el extractor de Ortelana SIN
ninguna herramienta de validacion externa (no Pydantic, no reintentos,
no parsers tolerantes). El objetivo es medir, no resolver.
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types  # Importamos errors para capturar el 429
from lote_stress_semantico import LOTE_MENSAJES

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Inicializar el cliente oficial de Google GenAI
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

# Mismo prompt que 03_clase.md, sin modificaciones defensivas
SYSTEM_PROMPT = """
Eres un sistema de extraccion de datos para Ortelana Textil.
Tu tarea es leer mensajes de texto libre enviados por distribuidores mayoristas
y extraer la informacion relevante en formato JSON.

Campos a extraer:
- cuit: string (formato XX-XXXXXXXX-X, None si no esta presente)
- razon_social: string (nombre de la empresa, None si no esta)
- responsable: string (nombre de la persona de contacto, None si no esta)
- telefono: string (None si no esta)
- email: string (None si no esta)
- rubro: string (descripcion del rubro del negocio, None si no esta)

Reglas:
- Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin explicaciones.
- Si un campo no esta presente en el mensaje, usa null.
- No inventes datos que no esten en el mensaje.
- El CUIT puede venir en distintos formatos. Normaliza siempre al formato XX-XXXXXXXX-X.
"""


def llamar_extractor_sin_red(mensaje: str) -> str:
    respuesta = client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=mensaje,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=400,
            temperature=0.1,
        ),
    )
    return respuesta.text


def clasificar_error(texto_crudo: str, excepcion: Exception) -> str:
    """
    Clasifica el tipo de fallo segun lo pedido en el PDF de la Clase 2:
    JSONDecodeError, KeyError, o tipo de dato mezclado.
    """
    if isinstance(excepcion, json.JSONDecodeError):
        return "JSONDecodeError_formato_invalido"

    if isinstance(excepcion, KeyError):
        return "KeyError_campo_ausente"

    return f"error_no_clasificado_{type(excepcion).__name__}"


def verificar_campos_y_tipos(datos: dict) -> list:
    """
    Una vez que el JSON parsea bien, verifica si los CAMPOS ESPERADOS
    estan presentes y si los tipos son los correctos.
    """
    campos_esperados = [
        "cuit",
        "razon_social",
        "responsable",
        "telefono",
        "email",
        "rubro",
    ]
    problemas = []

    for campo in campos_esperados:
        if campo not in datos:
            problemas.append(f"KeyError_simulado: falta el campo '{campo}'")
            continue
        valor = datos[campo]
        if valor is not None and not isinstance(valor, str):
            problemas.append(
                f"TipoMezclado: '{campo}' deberia ser string o null, vino {type(valor).__name__}"
            )

    campos_extra = set(datos.keys()) - set(campos_esperados)
    if campos_extra:
        problemas.append(f"CamposNoSolicitados: {campos_extra}")

    return problemas


def ejecutar_stress_test():
    resultados = []

    for caso in LOTE_MENSAJES:
        print(f"\n{'-' * 60}")
        print(f"[{caso['id']:02d}] Falla esperada: {caso['tipo_falla_esperada']}")

        # Inicializamos el registro antes del try para asegurar que exista ante cualquier fallo
        registro = {
            "id": caso["id"],
            "tipo_falla_esperada": caso["tipo_falla_esperada"],
            "mensaje": caso["mensaje"],
            "respuesta_cruda": "",
            "colapso": False,
            "tipo_error": None,
            "problemas_silenciosos": [],
        }

        try:
            # La llamada a la API ahora está protegida dentro del bloque try
            texto_crudo = llamar_extractor_sin_red(caso["mensaje"])
            registro["respuesta_cruda"] = texto_crudo

            datos = json.loads(texto_crudo)
            problemas = verificar_campos_y_tipos(datos)
            if problemas:
                registro["problemas_silenciosos"] = problemas
                print(f"  JSON parseo OK pero con problemas: {problemas}")
            else:
                print(f"  OK: {datos}")

        except errors.ClientError as e:
            # Captura explícita del error 429 / RESOURCE_EXHAUSTED o problemas de cliente
            registro["colapso"] = True
            registro["tipo_error"] = f"ClientError_429_QuotaExhausted"
            print(f"  COLAPSO POR CUOTA (API 429): {e.message}")
            resultados.append(registro)
            continue  # Salta inmediatamente al siguiente mensaje de la lista

        except json.JSONDecodeError as e:
            registro["colapso"] = True
            registro["tipo_error"] = clasificar_error(registro["respuesta_cruda"], e)
            print(f"  COLAPSO: {registro['tipo_error']}")
            print(f"  Respuesta cruda: {registro['respuesta_cruda'][:150]}")

        resultados.append(registro)

    return resultados


if __name__ == "__main__":
    resultados = ejecutar_stress_test()

    with open("reporte_contrato_roto.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print("\n\nReporte guardado en reporte_contrato_roto.json")
