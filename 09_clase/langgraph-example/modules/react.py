"""Piezas compartidas: LLM Gemini, grafo ReAct de LangGraph e impresión de trayectoria.

El grafo ReAct mínimo (el mismo diagrama de agents.md):

    START -> agente --¿pidió tool?--> No  -> END
               ^                      Sí
               |                       v
               +------------------ herramientas (ToolNode)

En la clase 08 (langsmith_eval.py) el flujo era una CADENA fija:
recuperar -> prompt -> LLM. Acá el LLM decide en cada vuelta si necesita
una herramienta, cuál y con qué argumentos; el grafo solo define qué
transiciones están permitidas.
"""

import json
import os
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv

# Igual que en la clase 08: .env antes de importar LangChain. Si .env trae
# LANGSMITH_TRACING=true, cada ejecución del grafo aparece como trace.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain.agents import create_agent

MODELO = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Cada vuelta agente->herramientas consume 2 "super-steps". 12 = ~6 vueltas.
RECURSION_LIMIT = int(os.environ.get("RECURSION_LIMIT", "12"))


def crear_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("Falta GOOGLE_API_KEY en .env (ver .env.sample).")
    return ChatGoogleGenerativeAI(model=MODELO, temperature=temperature)


# =============================================================================
# Estado
# =============================================================================
# add_messages es el reducer: cada nodo devuelve SOLO los mensajes nuevos y
# LangGraph los agrega al historial (como operator.add, pero además respeta
# ids de mensaje, lo que permite reemplazar/editar mensajes si hiciera falta).
class EstadoAgente(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# =============================================================================
# Constructor del grafo ReAct
# =============================================================================

#     # bind_tools: manda al LLM el JSON Schema de cada tool (nombre, docstring,
#     # tipos). Es todo lo que el modelo "ve" para elegir.
#     llm_con_tools = crear_llm().bind_tools(herramientas)
#
#     def nodo_agente(estado: EstadoAgente) -> dict:
#         # El system prompt NO se guarda en el estado: se antepone en cada
#         # llamada. Así un mismo historial sirve para distintos subagentes.
#         respuesta = llm_con_tools.invoke([SystemMessage(system_prompt), *estado["messages"]])
#         return {"messages": [respuesta]}
#
#     def debe_continuar(estado: EstadoAgente) -> str:
#         # La "decisión" del agente es solo esto: ¿el último AIMessage trae
#         # tool_calls? Si sí, se ejecutan; si no, es la respuesta final.
#         ultimo = estado["messages"][-1]
#         return "herramientas" if getattr(ultimo, "tool_calls", None) else END
#
#     grafo = StateGraph(EstadoAgente)
#     grafo.add_node("agente", nodo_agente)
#     # ToolNode ejecuta TODAS las tool_calls del AIMessage (en paralelo si son
#     # varias) y devuelve un ToolMessage por cada una, con su tool_call_id.
#     # handle_tool_errors=True: una excepción vuelve al LLM como texto de error
#     # en vez de romper el grafo (el agente puede corregir los argumentos).
#     grafo.add_node("herramientas", ToolNode(herramientas, handle_tool_errors=True))
#     grafo.add_edge(START, "agente")
#     grafo.add_conditional_edges("agente", debe_continuar, ["herramientas", END])
#     grafo.add_edge("herramientas", "agente")  # la observación vuelve al agente
#     return grafo.compile(checkpointer=checkpointer, name=nombre)
#
# Opcion mucho mas comoda usando la opcion directa de langgraph
# create_react_agent se encarga de crear el StateGraph, el ToolNode (con handle_tool_errors), las aristas condicionales y el bucle ReAct exactamente como lo tienes programado en tu script.
# https://docs.langchain.com/oss/python/langgraph/checkpointers -> sobre los checkpointers 
def construir_agente_react(herramientas: list, system_prompt: str, checkpointer=None, nombre: str = "agente"):
    return create_agent(
            model=crear_llm(),
            tools=herramientas,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            name=nombre
            )


# Utilidades de impresión

def texto(msg: AIMessage) -> str:
    """Gemini 3 puede devolver content como lista de partes: .text las une."""
    return msg.text if hasattr(msg, "text") else str(msg.content)


def _corto(s: str, n: int = 220) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n] + "…"


def imprimir_mensaje(msg: AnyMessage, prefijo: str = " ") -> None:
    """Muestra un paso de la trayectoria ReAct: Act (tool_call) u Observe (ToolMessage)."""
    if isinstance(msg, AIMessage) and msg.tool_calls:
        for tc in msg.tool_calls:
            args = json.dumps(tc["args"], ensure_ascii=False)
            print(f"{prefijo} [ACT]     {tc['name']}({args})")
    elif isinstance(msg, ToolMessage):
        print(f"{prefijo} [OBSERVE] {msg.name} -> {_corto(msg.content)}")
    elif isinstance(msg, AIMessage):
        print(f"{prefijo} [FINAL]   {texto(msg)}")


def herramientas_usadas(mensajes: list[AnyMessage]) -> list[str]:
    """Trayectoria resumida: nombres de tools en orden (útil para evaluar)."""
    return [tc["name"] for m in mensajes if isinstance(m, AIMessage) for tc in m.tool_calls]
