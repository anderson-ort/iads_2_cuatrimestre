import os
import warnings
from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Silenciar advertencias informativas de HF y Google SDK
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

app = typer.Typer(help="CLI interactiva para la cadena RAG con LangChain, Chroma y Gemini")
console = Console()

def obtener_cadena_rag():
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    PERSIST_DIRECTORY = "./database"
    
    # Cargar o instanciar la base de datos
    vectorstore = Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=embeddings_model
    )

    # Verificación "Get or Create"
    if vectorstore._collection.count() == 0:
        console.print("[yellow]🆕 Indexando documentos en ChromaDB por primera vez...[/yellow]")
        documentos_base = [
            Document(page_content="LangChain Core contiene las abstracciones fundamentales como Runnable, Prompts y Parsers."),
            Document(page_content="RAG (Retrieval-Augmented Generation) combina la búsqueda semántica en vector stores con la generación de LLMs."),
            Document(page_content="LCEL (LangChain Expression Language) utiliza el operador pipe | para encadenar componentes de forma declarativa."),
            Document(page_content="Sentence Transformers provee modelos locales para transformar texto en vectores numéricos densos de alta calidad.")
        ]
        splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
        docs_divididos = splitter.split_documents(documentos_base)
        vectorstore.add_documents(docs_divididos)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    TEMPLATE_RAG = """Responde únicamente basándote en el contexto proveído a continuación.
Si la información no se encuentra en el contexto, responde: 'No dispongo de suficiente información en los documentos.'

Contexto:
{context}

Pregunta: {question}

Respuesta:"""

    prompt = ChatPromptTemplate.from_template(TEMPLATE_RAG)
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.1
    )

    return (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

@app.command()
def info():
    """Muestra el desglose de componentes RAG en formato de tabla visual."""
    tabla = Table(title="DESGLOSE DE COMPONENTES DE LA CADENA RAG", show_header=True, header_style="bold cyan")
    tabla.add_column("Componente", style="bold yellow", width=22)
    tabla.add_column("Descripción")

    componentes = [
        ("Document", "Estructura de datos estándar con 'page_content' y 'metadata'."),
        ("ChatPromptTemplate", "Plantilla para inyectar contexto y preguntas dinámicas al modelo."),
        ("RunnablePassthrough", "Mantiene la pregunta original intacta a través del pipeline LCEL."),
        ("StrOutputParser", "Extrae la cadena de texto limpia omitiendo los metadatos de la respuesta."),
        ("Chroma", "Vector Store para almacenar embeddings y realizar búsquedas semánticas."),
        ("ChatGoogleGenerativeAI", "Conector con el motor LLM (Gemini) para la generación de respuesta.")
    ]

    for nombre, desc in componentes:
        tabla.add_row(nombre, desc)

    console.print(tabla)

@app.command()
def ask(
    pregunta: str = typer.Option(
        None,
        "--pregunta",
        "-p",
        help="Pregunta a realizar al pipeline RAG."
    )
):
    """Consulta al pipeline RAG directamente desde la terminal."""
    if not pregunta:
        pregunta = typer.prompt("🔹 Ingresa tu pregunta")

    with console.status("[bold green]Buscando contexto e invocando a Gemini...", spinner="dots"):
        rag_chain = obtener_cadena_rag()
        respuesta = rag_chain.invoke(pregunta)

    console.print()
    console.print(Panel(
        f"[bold white]{respuesta}[/bold white]",
        title=f"[bold cyan]Pregunta: {pregunta}[/bold cyan]",
        border_style="green",
        expand=False
    ))

if __name__ == "__main__":
    app()
