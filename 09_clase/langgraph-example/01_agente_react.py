"""Ejemplo 1: un solo agente ReAct con LangGraph + Gemini + herramientas.

Un agente, 6 herramientas (base JSON, políticas, web). Muestra:
  - bind_tools + ToolNode + arista condicional (el ciclo ReAct).
  - Trayectoria visible: qué tool pidió el LLM, con qué args y qué observó.
  - Varias tools en una misma pregunta (RAG + datos transaccionales).
  - Memoria de conversación con checkpointer (thread_id).
  - Límite de iteraciones (recursion_limit) con fallback seguro.

Uso:
    uv run python 01_agente_react.py                       # corre las preguntas demo
    uv run python 01_agente_react.py --pregunta "¿Qué linos tienen stock?"
    uv run python 01_agente_react.py --chat                # conversación con memoria
    uv run python 01_agente_react.py --grafo               # imprime el grafo en Mermaid
"""

import sys
import uuid
import typer

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from modules.prompts import SYSTEM_PROMPT
from modules.demo import PREGUNTAS_DEMO 
from modules.react import RECURSION_LIMIT, construir_agente_react, imprimir_mensaje
from modules.tools import TICKETS, ALL


# InMemorySaver guarda el estado del grafo por thread_id: es la "memoria" de la
# conversación. En producción se usa un checkpointer persistente (SQLite/Postgres).
agente = construir_agente_react(ALL, SYSTEM_PROMPT, checkpointer=InMemorySaver())

app = typer.Typer(help="CLI para interaccion con langgraph", add_completion=True)


def preguntar(pregunta: str, thread_id: str) -> None:
    print(f"\n{'=' * 78}\nUSUARIO: {pregunta}")
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    try:
        # stream_mode="updates": un evento por nodo ejecutado -> vemos el ciclo
        # agente -> herramientas -> agente en vivo.
        for evento in agente.stream({"messages": [HumanMessage(pregunta)]}, config, stream_mode="updates"):
            for nodo, update in evento.items():
                for msg in update["messages"]:
                    imprimir_mensaje(msg, prefijo=f"  ({nodo})")
    except GraphRecursionError:
        # Falla segura y explicable en vez de un bucle infinito.
        print(f"  [CORTE] Se alcanzó recursion_limit={RECURSION_LIMIT} sin respuesta final.")


def renderizar_grafo():
    """Muestra la estructura del grafo en formato ASCII en consola y Mermaid para la web."""
    try:
        print("\n--- Vista ASCII (Consola) ---")
        print(agente.get_graph().draw_ascii())
    except Exception:
        pass  # Requiere pygraphviz/grandalf opcionalmente
    
    print("\n--- Código Mermaid (Copiar en https://mermaid.live) ---")
    print(agente.get_graph().draw_mermaid())

def ejecutar_chat(thread_id: str | None = None):
    """Modo interactivo por consola con memoria persistente en la sesión."""
    thread = thread_id or str(uuid.uuid4())
    print(f"Chat con memoria (ID Sesión: {thread[:8]}...)")
    print("Escribí 'salir', 'exit' o presioná Ctrl+C para terminar.\n")
    
    try:
        while (pregunta := input("> ").strip()).lower() not in {"salir", "exit"}:
            if pregunta:
                preguntar(pregunta, thread)
    except (KeyboardInterrupt, EOFError):
        print("\n\nSesión finalizada.")

    if TICKETS:
        print(f"\nTickets creados en esta sesión: {TICKETS}")

def ejecutar_demo():
    """Modo demostración por defecto: ejecuta preguntas individuales y una prueba de memoria."""
    for pregunta in PREGUNTAS_DEMO:
        preguntar(pregunta, thread_id=str(uuid.uuid4()))

    print(f"\n{'#' * 78}\nMEMORIA: dos turnos en el mismo thread_id")
    thread = str(uuid.uuid4())
    preguntar("¿Cuál es el estado del pedido PED-1002?", thread)
    preguntar("Abrí un ticket para ese pedido: quiero agregar 5 metros más de frisa.", thread)
    
    if TICKETS:
        print(f"\nTickets creados: {TICKETS}")

@app.command()
def graph():
    """Imprime la representación visual del grafo."""
    renderizar_grafo()

@app.command()
def ask(
    pregunta: str = typer.Argument(..., help="Texto de la consulta"),
    thread: str = typer.Option(None, "--thread", "-t", help="ID de hilo/sesión opcional")
):
    """Realiza una sola pregunta puntual."""
    preguntar(pregunta, thread_id=thread or str(uuid.uuid4()))

@app.command()
def chat(
    thread: str = typer.Option(None, "--thread", "-t", help="Reanudar un hilo existente")
):
    """Inicia una sesión de chat interactiva."""
    ejecutar_chat(thread_id=thread)

@app.command()
def demo():
    """Ejecuta la batería de pruebas de demostración."""
    ejecutar_demo()

if __name__ == "__main__":
    app()
