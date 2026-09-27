"""CLI didactico del Asistente RAG + Router (Typer + Rich).

Comparte el flujo paso a paso de src/pipeline.py con la UI (app.py). Corre en
modo REPL (escribi 'salir' para terminar) o con una pregunta puntual como
argumento. Usa Rich para mostrar cada etapa de forma legible en la terminal.

Ejemplos:
    uv run python cli.py
    uv run python cli.py "cuanto stock hay de notebook"
    uv run python cli.py "como funciona el router" --no-mostrar-pasos
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import load_config
from services import build_components
from guardrails import guardrail_check
from pipeline import (
    ejecutar_pipeline as run_pipeline,
    StepStart,
    StepEnd,
    Embedding,
    EmbeddingError,
    Router,
    Tool,
    Retrieval,
    Rerank,
    Generation,
    Final,
)

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
CFG = load_config(CONFIG_PATH)

app = typer.Typer(add_completion=False, help="Asistente RAG + Router (CLI didactico).")
console = Console()


class RichPresenter:
    """Traduce los eventos del pipeline a la terminal con Rich. Si
    mostrar_pasos es False ignora los pasos intermedios y solo deja pasar el
    evento Final."""

    def __init__(self, mostrar_pasos: bool):
        self.mostrar_pasos = mostrar_pasos

    def handle(self, evento) -> None:
        if isinstance(evento, Final):
            return
        if not self.mostrar_pasos:
            return

        if isinstance(evento, StepStart):
            console.rule(f"[bold cyan]Paso {evento.numero}[/]: {evento.titulo}")
        elif isinstance(evento, StepEnd):
            color = "green" if evento.state == "complete" else "red"
            console.print(f"[{color}]{evento.label}[/]")
        elif isinstance(evento, Embedding):
            valores = ", ".join(f"{v:.4f}" for v in evento.vector[:8])
            console.print(
                Panel(
                    f"Dimension: [bold]{len(evento.vector)}[/]\n"
                    f"[{valores}, ...]\n"
                    f"Tiempo: {evento.elapsed:.3f} s",
                    title="Embedding",
                    border_style="blue",
                )
            )
        elif isinstance(evento, EmbeddingError):
            console.print(
                f"[yellow]No se pudo mostrar el vector de embedding: {evento.mensaje}[/]"
            )
        elif isinstance(evento, Router):
            d = evento.decision
            console.print(
                Panel(
                    f"Intencion: [bold]{d.intent.value}[/]\n"
                    f"Producto: {d.producto or '-'}\n"
                    f"Justificacion: {d.justificacion}",
                    title="Router",
                    border_style="magenta",
                )
            )
        elif isinstance(evento, Tool):
            console.print(
                Panel(evento.respuesta.mensaje, title=evento.tipo, border_style="magenta")
            )
        elif isinstance(evento, Retrieval):
            tabla = Table(title=f"Candidatos del bi-encoder (k={evento.k})")
            tabla.add_column("#")
            tabla.add_column("distancia")
            tabla.add_column("archivo")
            tabla.add_column("fragmento")
            for i, (doc, score) in enumerate(evento.candidatos, start=1):
                archivo = doc.metadata.get("filename", "desconocido")
                fragmento = doc.page_content[:80] + (
                    "..." if len(doc.page_content) > 80 else ""
                )
                tabla.add_row(str(i), f"{score:.4f}", archivo, fragmento)
            console.print(tabla)
        elif isinstance(evento, Rerank):
            tabla = Table(title=f"Reranking (top {evento.top_n} finales)")
            tabla.add_column("puesto nuevo")
            tabla.add_column("era")
            tabla.add_column("archivo")
            tabla.add_column("fragmento")
            for i, doc in enumerate(evento.top_docs, start=1):
                archivo = doc.metadata.get("filename", "desconocido")
                puesto_original = evento.posiciones.get(id(doc), "?")
                fragmento = doc.page_content[:80] + (
                    "..." if len(doc.page_content) > 80 else ""
                )
                tabla.add_row(str(i), f"#{puesto_original}", archivo, fragmento)
            console.print(tabla)
        elif isinstance(evento, Generation):
            console.print(
                Panel(evento.contexto, title="Contexto enviado al LLM", border_style="blue")
            )


def _ejecutar(pregunta: str, presenter: RichPresenter, componentes: dict, k: int, top_n: int) -> str:
    for evento in run_pipeline(pregunta, componentes, k, top_n):
        if isinstance(evento, Final):
            return evento.texto
        presenter.handle(evento)
    return ""


@app.command()
def main(
    pregunta: Optional[str] = typer.Argument(
        None, help="Pregunta puntual. Si se omite, abre un REPL."
    ),
    provider: str = typer.Option(
        CFG["embeddings"]["default_provider"], "--provider", help="Proveedor de embeddings."
    ),
    reranker: str = typer.Option(
        CFG["reranker"]["default"], "--reranker", help="Reranker: crossencoder | cohere."
    ),
    k: int = typer.Option(
        CFG["retrieval"]["k_candidatos"], "--k", help="Candidatos del bi-encoder."
    ),
    top_n: int = typer.Option(
        CFG["retrieval"]["top_n"], "--top-n", help="Documentos finales tras el reranker."
    ),
    mostrar_pasos: bool = typer.Option(
        True, "--mostrar-pasos/--no-mostrar-pasos", help="Mostrar el paso a paso interno."
    ),
    google_api_key: str = typer.Option(
        "", "--google-api-key", envvar="GOOGLE_API_KEY", help="API key del LLM (Gemini)."
    ),
    embedding_api_key: str = typer.Option(
        "", "--embedding-api-key", help="API key del proveedor de embeddings (gemini/cohere)."
    ),
    cohere_api_key: str = typer.Option(
        "", "--cohere-api-key", help="API key del reranker Cohere."
    ),
) -> None:
    if not google_api_key:
        console.print("[red]Falta GOOGLE_API_KEY en el entorno.[/]")
        raise typer.Exit(code=1)

    with console.status("[bold]Cargando modelos y cadenas...[/]"):
        componentes = build_components(
            google_api_key=google_api_key,
            provider_key=provider,
            embedding_api_key=embedding_api_key,
            reranker_nombre=reranker,
            cohere_api_key=cohere_api_key,
        )
    presenter = RichPresenter(mostrar_pasos)

    if pregunta:
        if not guardrail_check(pregunta):
            console.print("[yellow]Entrada invalida.[/]")
            raise typer.Exit(code=1)
        console.print(f"[bold]Pregunta:[/] {pregunta}")
        respuesta = _ejecutar(pregunta, presenter, componentes, k, top_n)
        console.print(Panel(respuesta, title="Respuesta", border_style="green"))
        return

    console.print("[bold]Asistente listo.[/] Escribi 'salir' para terminar.")
    while True:
        pregunta = console.input("\n[bold cyan]Pregunta:[/] ").strip()
        if not pregunta or pregunta.lower() in {"salir", "exit"}:
            break
        if not guardrail_check(pregunta):
            console.print("[yellow]Entrada invalida.[/]")
            continue
        respuesta = _ejecutar(pregunta, presenter, componentes, k, top_n)
        console.print(Panel(respuesta, title="Respuesta", border_style="green"))


if __name__ == "__main__":
    app()
