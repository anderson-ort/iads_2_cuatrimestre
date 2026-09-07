import typer

from rich.console import Console
from rich.panel import Panel

from ortelana.providers.factory import ProviderFactory
from ortelana.rag.engine import RAGEngine
from ortelana.sync.initial import run_initial_sync

app = typer.Typer(title="Ortelana RAG CLI")
console = Console()


def handle_provider(args: list[str]) -> None:
    """Gestiona la consulta y cambio de proveedor sin anidación."""
    if not args:
        current = ProviderFactory.get_current_provider_name()
        console.print(f"Proveedor actual: [bold]{current}[/bold]")
        return

    new_provider = args[0].lower()

    try:
        ProviderFactory.set_provider(new_provider)
        console.print(f"[green]Proveedor cambiado a: {new_provider}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


def handle_sync() -> None:
    """Ejecuta el proceso de sincronización inicial."""
    console.print("[cyan]Sincronizando y validando productos...[/cyan]")
    run_initial_sync()


def handle_help() -> None:
    """Muestra la ayuda de comandos disponibles."""
    console.print("[bold]Comandos disponibles:[/bold]")
    console.print("  [cyan]/provider [nombre][/cyan] - Muestra o cambia el proveedor (gemini | cohere)")
    console.print("  [cyan]/sync[/cyan]              - Re-sincroniza la base de datos con el catálogo")
    console.print("  [cyan]/help[/cyan]              - Muestra esta lista de comandos")
    console.print("  [cyan]/exit[/cyan]              - Sale de la aplicación\n")


def handle_query(engine: RAGEngine, user_input: str) -> None:
    """Procesa las consultas hacia el motor RAG."""
    with console.status("[bold cyan]Consultando catálogo...[/bold cyan]"):
        rag_res = engine.query(user_input)

    console.print(f"\n[bold]Respuesta ({rag_res.intent}):[/bold]\n{rag_res.answer}\n")
    
    if rag_res.sources:
        sources_str = ", ".join(s.nombre for s in rag_res.sources)
        console.print(f"[dim]Fuentes utilizadas: {sources_str}[/dim]\n")



@app.command()
def interactive() -> None:
    console.print(Panel.fit(
        "[bold blue]ORTELANA TEXTIL - RAG ASSISTANT[/bold blue]\n"
        "[dim]Consultas de catálogo validadas con Pydantic[/dim]", 
        border_style="blue"
    ))

    handle_help()

    engine = RAGEngine()

    while True:
        try:
            
            current_p = ProviderFactory.get_current_provider_name()
            user_input = console.input(f"[bold green]ortelana ({current_p})>[/bold green] ").strip()

            if not user_input:
                continue

            parts = user_input.split()
            cmd, args = parts[0].lower(), parts[1:]

            match cmd:
                case "/exit" | "exit" | "quit":
                    console.print("[yellow]Saliendo del asistente...[/yellow]")
                    break
                case "/sync":
                    handle_sync()
                case "/provider":
                    handle_provider(args)
                case "/help":
                    handle_help()
                case _ if cmd.startswith("/"):
                    console.print(f"[red]Comando no reconocido '{cmd}'. Usa /help para ver opciones.[/red]\n")
                case _:
                    handle_query(engine, user_input)

        except KeyboardInterrupt:
            break
        
        except Exception as e:
            console.print(f"[bold red]Error al procesar consulta:[/bold red] {e}\n")


if __name__ == "__main__":
    app()