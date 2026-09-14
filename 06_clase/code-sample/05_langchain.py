import os
import logging
import warnings
from typing import Dict
from dotenv import load_dotenv

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# 1. Silenciar alertas de terminal y librerías
warnings.filterwarnings("ignore")
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("langchain_core").setLevel(logging.ERROR)

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.output_parsers import StrOutputParser

load_dotenv()


# ==============================================================================
# 1. SERVICIO DE BASE DE DATOS VECTORIAL
# ==============================================================================
class VectorStoreService:
    """Gestiona la inicialización de embeddings, ChromaDB y recuperación."""

    def __init__(self, persist_dir: str = "./database"):
        self.persist_dir = persist_dir
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        self.vectorstore = Chroma(
            persist_directory=self.persist_dir, 
            embedding_function=self.embeddings
        )
        self._seed_database_if_empty()

    def _seed_database_if_empty(self) -> None:
        if self.vectorstore._collection.count() == 0:
            documentos = [
                Document(page_content="LangChain Core contiene las abstracciones fundamentales como Runnable, Prompts y Parsers."),
                Document(page_content="RAG (Retrieval-Augmented Generation) combina la búsqueda semántica en vector stores con la generación de LLMs."),
                Document(page_content="LCEL (LangChain Expression Language) utiliza el operador pipe | para encadenar componentes de forma declarativa."),
                Document(page_content="Sentence Transformers provee modelos locales para transformar texto en vectores numéricos densos de alta calidad.")
            ]
            splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
            self.vectorstore.add_documents(splitter.split_documents(documentos))

    def get_retriever(self, k: int = 2):
        return self.vectorstore.as_retriever(search_kwargs={"k": k})


# ==============================================================================
# 2. SERVICIO DE MEMORIA PERSISTENTE (Archivos JSON)
# ==============================================================================
class PersistentSessionMemoryService:
    """Guarda y recupera el historial de chat persistido en disco (.history/)."""

    def __init__(self, storage_dir: str = "./history"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def get_session_history(self, session_id: str) -> FileChatMessageHistory:
        file_path = os.path.join(self.storage_dir, f"{session_id}.json")
        return FileChatMessageHistory(file_path)


# ==============================================================================
# 3. PIPELINE RAG CONVERSACIONAL
# ==============================================================================
class ConversationalRAGPipeline:
    """Ensambla las cadenas LCEL con el almacenamiento en disco."""

    def __init__(self, retriever, memory_service: PersistentSessionMemoryService):
        self.retriever = retriever
        self.memory_service = memory_service
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.2
        )
        self.chain = self._build_chain()

    def _build_contextualize_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Dada un historial de conversación y la última pregunta del usuario "
                "que podría hacer referencia al contexto en el historial, formula una pregunta "
                "independiente que se pueda entender sin el historial de conversación. "
                "NO respondas a la pregunta, solo reescríbela si es necesario o devuélvela tal cual."
            )),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        return prompt | self.llm | StrOutputParser()

    def _build_chain(self):
        contextualize_q_chain = self._build_contextualize_chain()

        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Eres un asistente para tareas de respuesta a preguntas.\n"
                "Utiliza los siguientes fragmentos de contexto recuperados para responder "
                "a la pregunta. Si no sabes la respuesta, di que no la sabes.\n\n"
                "Contexto Recuperado:\n{context}"
            )),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        def contextualized_question(input_dict):
            if input_dict.get("chat_history"):
                return contextualize_q_chain
            return input_dict["input"]

        rag_chain = (
            RunnablePassthrough.assign(
                context=contextualized_question | self.retriever | format_docs
            )
            | qa_prompt
            | self.llm
            | StrOutputParser()
        )

        return RunnableWithMessageHistory(
            rag_chain,
            self.memory_service.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="output",
        )

    def stream_answer(self, question: str, session_id: str):
        config = {"configurable": {"session_id": session_id}}
        return self.chain.stream({"input": question}, config=config)


# ==============================================================================
# 4. CLI INTERFACING (Typer)
# ==============================================================================
app = typer.Typer(help="CLI Conversacional RAG con Memoria Persistente")
console = Console()

@app.command()
def main(
    session_id: str = typer.Option("sesion_cli_123", "--session", "-s", help="ID de la sesión de chat")
):
    """Inicia una sesión interactiva de Chat RAG en la terminal."""
    console.print(Panel.fit(
        f"[bold green]Modo Chat RAG Activo[/bold green]\n"
        f"ID de Sesión: [cyan]{session_id}[/cyan]\n"
        f"Escribe [bold red]'salir'[/bold red] o [bold red]'exit'[/bold red] para finalizar.",
        border_style="cyan"
    ))

    vector_service = VectorStoreService()
    memory_service = PersistentSessionMemoryService()
    pipeline = ConversationalRAGPipeline(
        retriever=vector_service.get_retriever(),
        memory_service=memory_service
    )

    while True:
        pregunta = Prompt.ask("\n[bold yellow]👤 Tú[/bold yellow]")
        
        if pregunta.strip().lower() in ["salir", "exit", "quit"]:
            console.print("[bold red]Sesión finalizada. ¡Hasta luego![/bold red]")
            break

        if not pregunta.strip():
            continue

        console.print("[bold cyan]🤖 Asistente:[/bold cyan] ", end="")
        
        try:
            for chunk in pipeline.stream_answer(pregunta, session_id):
                console.print(chunk, end="", highlight=False)
            console.print()
        except Exception as e:
            console.print(f"\n[bold red]Error durante la ejecución:[/bold red] {e}")


if __name__ == "__main__":
    app()
