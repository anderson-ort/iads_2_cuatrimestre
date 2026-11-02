"""Load source documents and the Mongo catalog, then (re)build the Atlas Vector Search index."""

import logging
from collections.abc import Iterable
from pathlib import Path

import anydoc
from langchain_core.documents import Document
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pymongo import MongoClient

from src.config import Settings
from src.retrieval import open_vectorstore

logger = logging.getLogger(__name__)

HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]
INDEX_TIMEOUT_SECONDS = 120


def load_documents(directory: Path) -> list[Document]:
    """Convert every file in `directory` (pdf, docx, xlsx...) to markdown."""
    return [
        Document(page_content=anydoc.to_markdown(str(path)), metadata={"source": path.name})
        for path in sorted(directory.iterdir())
        if path.is_file()
    ]


def split_documents(
    documents: Iterable[Document], chunk_size: int, chunk_overlap: int
) -> list[Document]:
    """Split by markdown headers first, then by size. Ids are `<source>-<n>`."""
    header_splitter = MarkdownHeaderTextSplitter(HEADERS)
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks: list[Document] = []
    for doc in documents:
        sections = header_splitter.split_text(doc.page_content) or [doc]
        for section in sections:
            section.metadata.update(doc.metadata, tipo="documento")
        for n, chunk in enumerate(size_splitter.split_documents(sections)):
            chunk.id = f"{doc.metadata['source']}-{n}"
            chunks.append(chunk)
    return chunks


def catalog_to_documents(records: Iterable[dict]) -> list[Document]:
    """Map catalog records to documents; metadata is kept as flat scalars."""
    documents = []
    for record in records:
        metadata = {
            key: ", ".join(value) if isinstance(value, list) else value
            for key, value in record["metadatos"].items()
        }
        documents.append(
            Document(
                id=record["id"],
                page_content=f"{record['nombre']}: {record['descripcion_semantica']}",
                metadata={"tipo": "producto", "source": "catalogo", **metadata},
            )
        )
    return documents


def fetch_catalog(client: MongoClient, database: str, collection: str) -> list[dict]:
    return list(client[database][collection].find({}, {"_id": 0}))


def ensure_vector_index(store: MongoDBAtlasVectorSearch, settings: Settings) -> None:
    """Create the Atlas vector index once; it becomes queryable asynchronously."""
    if next(store.collection.list_search_indexes(settings.vectorstore.index), None):
        return
    store.create_vector_search_index(
        dimensions=settings.llm.active.embedding_dimensions or -1,
        wait_until_complete=INDEX_TIMEOUT_SECONDS,
    )


def build_index(settings: Settings) -> int:
    """Rebuild the collection from scratch so re-running ingest is idempotent."""
    documents = split_documents(
        load_documents(settings.path(settings.ingest.documents_dir)),
        settings.ingest.chunk_size,
        settings.ingest.chunk_overlap,
    )
    with MongoClient(settings.secrets.mongodb_uri.get_secret_value()) as client:
        catalog = fetch_catalog(
            client, settings.mongo.catalog_database, settings.mongo.catalog_collection
        )
        documents += catalog_to_documents(catalog)

        store = open_vectorstore(settings, client)
        ensure_vector_index(store, settings)
        # The Atlas index definition stays; only the documents are replaced.
        store.collection.delete_many({})
        store.add_documents(documents, ids=[d.id for d in documents])
    logger.info("Indexed %d chunks (%d products)", len(documents), len(catalog))
    return len(documents)
