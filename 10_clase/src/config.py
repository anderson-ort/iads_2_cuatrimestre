import os
from datetime import date
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, trim_messages

load_dotenv()

MAX_MENSAJES:int = 10
MAX_PASOS:int = 4

def proveedor() -> str:
    """GenAI es el principal; Cohere se usa solo si falta la key de Google."""
    if os.getenv("GOOGLE_API_KEY"):
        return "genai"
    if os.getenv("COHERE_API_KEY"):
        return "cohere"
    raise RuntimeError("Configurá GOOGLE_API_KEY (principal) o COHERE_API_KEY.")


@lru_cache(maxsize=1)
def api() -> httpx.Client:
    """Cliente httpx configurado para Supabase (PostgREST). Se crea una sola vez."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_KEY"]
    return httpx.Client(
        base_url=f"{base}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=10,
    )

@lru_cache
def obtener_llm() -> BaseChatModel:
    if proveedor() == "genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("GENAI_MODEL", "gemini-2.5-flash"), temperature=0
        )

    from langchain_cohere import ChatCohere

    return ChatCohere(model=os.getenv("COHERE_MODEL", "command-a-03-2025"), temperature=0)


def contexto() -> str:
    return (
        f"Hoy es {date.today().isoformat()}. Trabajas para un distribuidor mayorista de telas "
        "con sucursales en Buenos Aires, Cordoba y Rosario. Los precios estan en pesos (ARS) por metro. "
        "Responde en espanol, de forma breve y usando solo datos obtenidos de las herramientas."
    )


def recortar(mensajes: list[BaseMessage]) -> list[BaseMessage]:
    """Ventana de los ultimos N mensajes, siempre iniciando en un mensaje humano
    para no dejar pares tool-call/tool-result cortados."""
    return trim_messages(
        mensajes,
        max_tokens=MAX_MENSAJES,
        token_counter=len,  # cuenta mensajes, no tokens
        strategy="last",
        start_on="human",
        include_system=False,
    )
