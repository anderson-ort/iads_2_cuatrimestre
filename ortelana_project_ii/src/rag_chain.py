import warnings

from google.genai import types
from src.config import client, MODELO_LLM
from src.models import FiltrosConsultaSchema, RespuestaComercialSchema, TelaResultado

warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")

def extraer_intencion_y_filtros(mensaje_usuario: str) -> FiltrosConsultaSchema:
    
    prompt_parser = """
    Analiza la solicitud del cliente de Ortelana Textil y extrae los filtros operativos e intención semántica.
    """
    response = client.models.generate_content(
        model=MODELO_LLM,
        contents=mensaje_usuario,
        config=types.GenerateContentConfig(
            system_instruction=prompt_parser,
            response_mime_type="application/json",
            response_schema=FiltrosConsultaSchema,
            temperature=0.0
        )
    )
    return FiltrosConsultaSchema.model_validate_json(response.text)


def generar_respuesta_final(mensaje_usuario: str, articulos_recuperados: list[TelaResultado]) -> RespuestaComercialSchema:
    if articulos_recuperados:
        contexto_str = "\n".join([
            f"- [{t.id}] {t.descripcion_semantica} | Sucursal: {t.sucursal} | Stock: {t.en_stock}"
            for t in articulos_recuperados
        ])
    else:
        contexto_str = "No se encontraron artículos que cumplan los criterios estrictos."

    system_instruction = f"""
    # ROLE
    Sos un extractor de información estructurada para Ortelana Textil.
    Tu única función es leer mensajes de clientes (WhatsApp, email, notas de pedido)
        
    # TASK
    Responde al cliente de forma profesional y clara basándote ÚNICAMENTE en este contexto recuperado:

    {contexto_str}

    """

    response = client.models.generate_content(
        model=MODELO_LLM,
        contents=mensaje_usuario,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=RespuestaComercialSchema,
            temperature=0.2
        )
    )
    
    return RespuestaComercialSchema.model_validate_json(response.text)