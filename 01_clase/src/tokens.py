"""
Compara el costo en tokens de procesar el mismo mensaje de distribuidor
en espanol vs una version equivalente en ingles, y mide el impacto de
un system prompt largo vs uno corto.
"""

# Usamos el encoding de referencia para modelos GPT (proxy razonable para
# comparar economia de tokens; los modelos de Anthropic usan su propio
# tokenizador pero el orden de magnitud relativo es comparable)

import os
import tiktoken
# Importamos el SDK moderno de Google GenAI
from google import genai

# 1. Tokenizer de OpenAI (Referencia)
encoding_openai = tiktoken.get_encoding("cl100k_base")

# 2. Tokenizer para  Gemini
# Recuerda tener la variable de entorno GEMINI_API_KEY configurada
try:
    client = genai.Client()
    USAR_GEMINI_REAL = True
except Exception:
    USAR_GEMINI_REAL = False
    print("No se detectó GEMINI_API_KEY. Los valores de Gemini se simularán para el ejemplo.\n")

# Usamos el modelo estándar actual para tareas de texto rápido
MODELO_GEMINI = "gemini-2.5-flash"

def contar_tokens_openai(texto: str) -> int:
    return len(encoding_openai.encode(texto))

def contar_tokens_gemini(texto: str) -> int:
    if not USAR_GEMINI_REAL:
        # Simulación: Históricamente Gemini es un ~15-20% más eficiente en español que cl100k_base
        return int(contar_tokens_openai(texto) * 0.82)
    
    # Llamada oficial al método de conteo de Gemini
    response = client.models.count_tokens(
        model=MODELO_GEMINI,
        contents=texto
    )
    return response.total_tokens


# --- Mismos textos del ejemplo original ---
MENSAJE_ES = """
Buenas tardes, me contacto desde Modas del Sur SRL para registrarme como
distribuidor mayorista. Nuestro CUIT es 30-71234567-8. Somos una empresa de
indumentaria femenina con 3 anios de trayectoria, tenemos local fisico en
Buenos Aires. El responsable de compras soy yo, Claudia Torres.
"""

MENSAJE_EN = """
Good afternoon, I am contacting you from Modas del Sur SRL to register as a
wholesale distributor. Our tax ID is 30-71234567-8. We are a women's apparel
company with 3 years of operation, we have a physical store in Buenos Aires.
I am the purchasing manager, Claudia Torres.
"""

SYSTEM_PROMPT_CORTO = "Extrae CUIT, razon social y responsable. Devuelve JSON."

SYSTEM_PROMPT_LARGO = """
Eres un sistema de extraccion de datos para Ortelana Textil.
Tu tarea es leer mensajes de texto libre enviados por distribuidores mayoristas
y extraer la informacion relevante en formato JSON.
Campos a extraer: cuit, razon_social, responsable, telefono, email, rubro.
Reglas: Devuelve SOLO el JSON, sin texto adicional, sin markdown.
Si un campo no esta presente en el mensaje, usa null. No inventes datos.
El CUIT puede venir en distintos formatos. Normaliza siempre al formato XX-XXXXXXXX-X.
"""


def ejecutar_comparativa():
    # --- IDIOMAS ---
    t_es_oa = contar_tokens_openai(MENSAJE_ES)
    t_en_oa = contar_tokens_openai(MENSAJE_EN)
    
    t_es_gem = contar_tokens_gemini(MENSAJE_ES)
    t_en_gem = contar_tokens_gemini(MENSAJE_EN)
    
    print("--- COMPARACIÓN DE IDIOMAS ---")
    print(f"[OpenAI Tiktoken]  Español: {t_es_oa} | Inglés: {t_en_oa} (Diferencia: {((t_es_oa-t_en_oa)/t_en_oa)*100:.1f}% más en ES)")
    print(f"[Google Gemini]   Español: {t_es_gem} | Inglés: {t_en_gem} (Diferencia: {((t_es_gem-t_en_gem)/t_en_gem)*100:.1f}% más en ES)")
    print("\n Nota: Verás que la brecha de costo entre ES e EN es menor en Gemini gracias a su tokenizador multilingual.")

    # --- SYSTEM PROMPTS ---
    p_corto_gem = contar_tokens_gemini(SYSTEM_PROMPT_CORTO)
    p_largo_gem = contar_tokens_gemini(SYSTEM_PROMPT_LARGO)
    dif_tokens = p_largo_gem - p_corto_gem
    
    print("\n---  IMPACTO DEL SYSTEM PROMPT (En Gemini) ---")
    print(f"Tokens Prompt Corto: {p_corto_gem}")
    print(f"Tokens Prompt Largo: {p_largo_gem}")
    print(f"Diferencia neta: {dif_tokens} tokens adicionales por solicitud.")
    
    # Proyección a escala
    llamadas_diarias = 200
    exceso_diario = dif_tokens * llamadas_diarias
    # En Gemini 1.5/2.5 el Context Caching puede mitigar esto si el volumen es masivo
    print(f"Proyección ({llamadas_diarias} llamadas/día): {exceso_diario:,} tokens extra al día.")


if __name__ == "__main__":
    ejecutar_comparativa()