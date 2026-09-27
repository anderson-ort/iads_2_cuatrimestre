"""Flujo del ingester, agnóstico de la UI.

Extrae la orquestación (parse -> chunk -> embed -> store, retrieval y stats) que
originalmente vivía dentro de app.py, para que tanto la app de Streamlit
(app.py) como el CLI (cli.py) ejecuten exactamente la misma secuencia.

El flujo no conoce Streamlit ni Rich: emite eventos y cada entrypoint los
traduce a su propia representación. El evento Final transporta un resumen en
texto plano."""

from dataclasses import dataclass
from typing import Iterator, List, Tuple, Union

from langchain_core.documents import Document

from .chunker import HybridChunker
from .parser import AnyDocParserService
from .vectorstore import VectorStoreManager


@dataclass
class StepStart:
    numero: int
    titulo: str
    expanded: bool = True


@dataclass
class StepEnd:
    numero: int
    label: str
    state: str = "complete"


@dataclass
class FileStart:
    index: int
    total: int
    filename: str


@dataclass
class Parsed:
    filename: str
    num_documents: int
    num_chars: int


@dataclass
class Chunked:
    filename: str
    num_chunks: int


@dataclass
class Stored:
    filename: str
    num_chunks: int
    total_chunks: int


@dataclass
class FileError:
    filename: str
    mensaje: str


@dataclass
class Retrieval:
    candidatos: List[Tuple[Document, float]]
    k: int


@dataclass
class Stats:
    total_chunks: int
    total_files: int
    file_names: List[str]


@dataclass
class Final:
    texto: str


Evento = Union[
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
]


def ejecutar_ingesta(
    file_paths: List[Tuple[str, str]],
    vector_manager: VectorStoreManager,
    chunk_size: int,
    chunk_overlap: int,
    category: str,
) -> Iterator[Evento]:
    """Ingesta una lista de (ruta_en_disco, nombre_original) emitiendo eventos.

    Cada archivo se procesa de forma independiente: si uno falla se emite un
    FileError y se continúa con el resto."""

    parser_service = AnyDocParserService()
    chunker = HybridChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    total_chunks = 0
    files_ok = 0
    files_error = 0
    total = len(file_paths)

    for index, (path, filename) in enumerate(file_paths, start=1):
        yield FileStart(index, total, filename)

        yield StepStart(1, "Parse: convertir el archivo a Markdown")
        try:
            parsed_docs = parser_service.parse(path, filename)
        except Exception as e:
            files_error += 1
            yield FileError(filename, str(e))
            yield StepEnd(1, f"Parse: {filename} (error)", "error")
            continue
        for d in parsed_docs:
            d.metadata["category"] = category
        num_chars = sum(len(d.page_content) for d in parsed_docs)
        yield Parsed(filename, len(parsed_docs), num_chars)
        yield StepEnd(1, f"Parse: {filename} -> {num_chars} caracteres", "complete")

        yield StepStart(2, "Chunk: partir el texto en fragmentos")
        chunks = chunker.split_documents(parsed_docs)
        yield Chunked(filename, len(chunks))
        yield StepEnd(2, f"Chunk: {filename} -> {len(chunks)} chunks", "complete")

        yield StepStart(3, "Embed + Store: vectorizar y guardar en ChromaDB")
        stored = vector_manager.add_documents(chunks)
        total_chunks += stored
        files_ok += 1
        yield Stored(filename, stored, total_chunks)
        yield StepEnd(3, f"Store: {filename} -> {stored} chunks indexados", "complete")

    yield Final(
        f"Ingesta completa: {total_chunks} chunks de {files_ok}/{total} archivos "
        f"({files_error} con error)."
    )


def ejecutar_query(
    query: str,
    vector_manager: VectorStoreManager,
    k: int,
) -> Iterator[Evento]:
    """Ejecuta una búsqueda por similitud emitiendo los candidatos."""
    yield StepStart(1, f"Retrieval: top {k} por cercanía")
    vs = vector_manager.get_vectorstore()
    candidatos = vs.similarity_search_with_score(query, k=k)
    yield Retrieval(candidatos, k)
    yield StepEnd(1, f"Retrieval -> {len(candidatos)} candidatos", "complete")
    yield Final(f"{len(candidatos)} resultados para '{query}'.")


def ejecutar_stats(vector_manager: VectorStoreManager) -> Iterator[Evento]:
    """Lee las estadísticas de la colección vectorial."""
    yield StepStart(1, "Metadatos de ChromaDB")
    stats = vector_manager.get_stats()
    yield Stats(stats["total_chunks"], stats["total_files"], stats["file_names"])
    yield StepEnd(1, f"Metadatos -> {stats['total_chunks']} chunks", "complete")
    yield Final(
        f"{stats['total_chunks']} chunks indexados en {stats['total_files']} archivos."
    )
