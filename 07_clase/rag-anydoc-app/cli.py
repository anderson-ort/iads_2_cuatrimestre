"""CLI didáctico del Ingester RAG (Typer + Rich).

Comparte el flujo paso a paso de ingester/pipeline.py con la UI (app.py): ambos
consumen los mismos eventos, solo cambia cómo los muestran. Usa Rich para
mostrar cada etapa de forma legible en la terminal.

Ejemplos:
    uv run python cli.py ingest documentos/manual.pdf --category tecnico
    uv run python cli.py query "como se aplica el descuento" --k 3
    uv run python cli.py stats
"""

from pathlib import Path
from typing import List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ingester.config import load_config, get_api_key
from ingester.services import (
    resolve_provider_key,
    build_vector_manager,
)
from ingester.pipeline import (
    ejecutar_ingesta,
    ejecutar_query,
    ejecutar_stats,
    StepStart,
    StepEnd,
    FileStart,
    Parsed,
    Chunked,
    Stored,
    FileError,
    Retrieval,
    Stats,
    Final,
)

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
CFG = load_config(CONFIG_PATH)

app = typer.Typer(add_completion=False, help="Ingester RAG (CLI didáctico).")
console = Console()


class RichPresenter:
    """Traduce los eventos del pipeline a la terminal con Rich."""

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
        elif isinstance(evento, FileStart):
            console.print(
                f"\n[bold]Archivo {evento.index}/{evento.total}:[/] {evento.filename}"
            )
        elif isinstance(evento, Parsed):
            console.print(
                Panel(
                    f"Documentos: [bold]{evento.num_documents}[/]\n"
                    f"Caracteres: {evento.num_chars}",
                    title="Parse",
                    border_style="blue",
                )
            )
        elif isinstance(evento, Chunked):
            console.print(
                Panel(
                    f"Chunks generados: [bold]{evento.num_chunks}[/]",
                    title="Chunk",
                    border_style="blue",
                )
            )
        elif isinstance(evento, Stored):
            console.print(
                Panel(
                    f"Chunks indexados: [bold]{evento.num_chunks}[/]\n"
                    f"Total acumulado: {evento.total_chunks}",
                    title="Store",
                    border_style="blue",
                )
            )
        elif isinstance(evento, FileError):
            console.print(f"[red]Error en {evento.filename}: {evento.mensaje}[/]")
        elif isinstance(evento, Retrieval):
            tabla = Table(title=f"Candidatos por cercanía (k={evento.k})")
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
        elif isinstance(evento, Stats):
            console.print(f"Total de chunks indexados: [bold]{evento.total_chunks}[/]")
            console.print(f"Total de archivos únicos: [bold]{evento.total_files}[/]")
            if evento.file_names:
                lista = "\n".join(f"- {n}" for n in evento.file_names)
                console.print(Panel(lista, title="Archivos en la colección", border_style="blue"))
            else:
                console.print("[yellow]La colección de ChromaDB está vacía.[/]")


def _pick_api_key(provider_key: str, gemini_api_key: str, cohere_api_key: str) -> str:
    explicit = gemini_api_key if provider_key == "gemini" else cohere_api_key
    return explicit or get_api_key(provider_key)


def _ejecutar(eventos, presenter: RichPresenter) -> str:
    final = ""
    for evento in eventos:
        if isinstance(evento, Final):
            final = evento.texto
        else:
            presenter.handle(evento)
    return final


def _build_manager(provider: str, gemini_api_key: str, cohere_api_key: str):
    provider_key = resolve_provider_key(provider)
    api_key = _pick_api_key(provider_key, gemini_api_key, cohere_api_key)
    with console.status("[bold]Cargando modelo de embeddings...[/]"):
        return build_vector_manager(provider_key, api_key, CFG)


_PROVIDER_OPTION = typer.Option(
    "huggingface", "--provider", help="Proveedor: huggingface | gemini | cohere."
)
_GEMINI_KEY_OPTION = typer.Option(
    "", "--gemini-api-key", envvar="GEMINI_API_KEY", help="API key de Gemini."
)
_COHERE_KEY_OPTION = typer.Option(
    "", "--cohere-api-key", envvar="COHERE_API_KEY", help="API key de Cohere."
)
_MOSTRAR_OPTION = typer.Option(
    True, "--mostrar-pasos/--no-mostrar-pasos", help="Mostrar el paso a paso interno."
)


@app.command()
def ingest(
    rutas: List[Path] = typer.Argument(
        ..., exists=True, dir_okay=False, help="Archivos a ingestar."
    ),
    provider: str = _PROVIDER_OPTION,
    category: str = typer.Option(
        CFG["app"]["categories"][0], "--category", help="Categoría de los documentos."
    ),
    chunk_size: int = typer.Option(
        CFG["chunking"]["default_size"], "--chunk-size", help="Tamaño máximo de chunk."
    ),
    chunk_overlap: int = typer.Option(
        CFG["chunking"]["default_overlap"], "--chunk-overlap", help="Solapamiento entre chunks."
    ),
    gemini_api_key: str = _GEMINI_KEY_OPTION,
    cohere_api_key: str = _COHERE_KEY_OPTION,
    mostrar_pasos: bool = _MOSTRAR_OPTION,
) -> None:
    """Parsea, corta, vectoriza y guarda los archivos en ChromaDB."""
    vector_manager = _build_manager(provider, gemini_api_key, cohere_api_key)
    presenter = RichPresenter(mostrar_pasos)
    file_paths = [(str(p), p.name) for p in rutas]
    resumen = _ejecutar(
        ejecutar_ingesta(file_paths, vector_manager, chunk_size, chunk_overlap, category),
        presenter,
    )
    console.print(Panel(resumen, title="Resumen", border_style="green"))


@app.command()
def query(
    consulta: str = typer.Argument(..., help="Consulta o palabra clave."),
    provider: str = _PROVIDER_OPTION,
    k: int = typer.Option(3, "--k", help="Número de resultados."),
    gemini_api_key: str = _GEMINI_KEY_OPTION,
    cohere_api_key: str = _COHERE_KEY_OPTION,
    mostrar_pasos: bool = _MOSTRAR_OPTION,
) -> None:
    """Prueba el retrieval: muestra los chunks más parecidos a la consulta."""
    if not consulta.strip():
        console.print("[red]Escriba una consulta válida.[/]")
        raise typer.Exit(code=1)

    vector_manager = _build_manager(provider, gemini_api_key, cohere_api_key)
    presenter = RichPresenter(mostrar_pasos)
    _ejecutar(ejecutar_query(consulta, vector_manager, k), presenter)


@app.command()
def stats(
    provider: str = _PROVIDER_OPTION,
    gemini_api_key: str = _GEMINI_KEY_OPTION,
    cohere_api_key: str = _COHERE_KEY_OPTION,
    mostrar_pasos: bool = _MOSTRAR_OPTION,
) -> None:
    """Muestra estadísticas de la colección vectorial."""
    vector_manager = _build_manager(provider, gemini_api_key, cohere_api_key)
    presenter = RichPresenter(mostrar_pasos)
    _ejecutar(ejecutar_stats(vector_manager), presenter)


if __name__ == "__main__":
    app()
