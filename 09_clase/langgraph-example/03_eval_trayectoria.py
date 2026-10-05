"""Ejemplo 3: evaluar la TRAYECTORIA del agente, no solo la respuesta final.

En la clase 08 RAGAS medía la calidad de la respuesta de un RAG. En un agente
además importa el camino (ver "Observabilidad y evaluación" en agents.md):

  - tool_selection: ¿usó todas las herramientas esperadas?
  - sin_prohibidas: ¿evitó las que NO debía usar? (ej. web para stock)
  - pasos: cantidad de tool calls (eficiencia)
  - contiene: ¿la respuesta final menciona el dato clave? (check determinista)

Checks deterministas, sin LLM juez: baratos y reproducibles. Si .env tiene
LANGSMITH_TRACING=true, cada caso además queda como trace en LangSmith.

Uso:
    uv run python 03_eval_trayectoria.py run                  # corre todos los casos
    uv run python 03_eval_trayectoria.py run --caso 2         # corre solo un caso (índice)
    uv run python 03_eval_trayectoria.py run --pausa 0        # sin espera entre casos
    uv run python 03_eval_trayectoria.py list                 # lista los casos
"""

import time
import uuid

import typer
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError

from langsmith import traceable
from modules.demo import CASOS, EVAL_PREGUNTAS_DEMO
from modules.prompts import SYSTEM_PROMPT
from modules.react import RECURSION_LIMIT, construir_agente_react, herramientas_usadas, texto
from modules.tools import ALL

# Mismo agente y mismo prompt que el ejemplo 1: evaluamos lo que se usa en producción.
agente = construir_agente_react(ALL, SYSTEM_PROMPT)

app = typer.Typer(help="CLI para evaluar la trayectoria del agente", add_completion=True)

@traceable(name="eval_caso", run_type="chain")
def evaluar_caso(caso: dict) -> dict:
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": RECURSION_LIMIT}
    try:
        estado = agente.invoke({"messages": [HumanMessage(caso["pregunta"])]}, config)
        usadas = herramientas_usadas(estado["messages"])
        final = texto(estado["messages"][-1])
    except GraphRecursionError:
        usadas, final = ["<recursion_limit>"], ""

    r = {
        "tool_selection": caso["esperadas"] <= set(usadas),
        "sin_prohibidas": not (caso["prohibidas"] & set(usadas)),
        "contiene": caso["contiene"] is None or caso["contiene"].lower() in final.lower(),
        "pasos": len(usadas),
    }
    ok = all(v for k, v in r.items() if k != "pasos")
    print(f"\n[{'OK ' if ok else 'MAL'}] {caso['pregunta']}")
    print(f"      tools={usadas}  ->  {r}")
    print(f"      respuesta: {final[:160]}")
    return r


def imprimir_resumen(resultados: list[dict]) -> None:
    n = len(resultados)
    print(f"\n{'=' * 78}")
    for m in ("tool_selection", "sin_prohibidas", "contiene"):
        print(f"  {m:<15} {sum(r[m] for r in resultados) / n:.0%}")
    print(f"  {'pasos_promedio':<15} {sum(r['pasos'] for r in resultados) / n:.1f}")


@app.command("list")
def listar():
    """Lista los casos de evaluación con sus tools esperadas y prohibidas."""
    for i, caso in enumerate(CASOS):
        print(f"[{i}] {caso['pregunta']}")
        print(f"     esperadas={sorted(caso['esperadas'])}  prohibidas={sorted(caso['prohibidas'])}"
              f"  contiene={caso['contiene']!r}")


@app.command()
def run(
    caso: int = typer.Option(None, "--caso", "-c", help="Índice de un único caso a evaluar"),
    pausa: float = typer.Option(2.0, "--pausa", "-p", help="Segundos entre casos (free tier de Gemini)"),
):
    """Evalúa la trayectoria del agente. Sale con código 1 si alguna trayectoria falla."""
    if caso is not None and not 0 <= caso < len(CASOS):
        raise typer.BadParameter(f"--caso debe estar entre 0 y {len(CASOS) - 1}")
    casos = CASOS if caso is None else [CASOS[caso]]

    resultados = []
    for i, c in enumerate(casos):
        if i:
            time.sleep(pausa)
        resultados.append(evaluar_caso(c))

    imprimir_resumen(resultados)

    # Quality gate, como en langsmith_eval.py: exit 1 si alguna trayectoria falla.
    if not all(r["tool_selection"] and r["sin_prohibidas"] for r in resultados):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
