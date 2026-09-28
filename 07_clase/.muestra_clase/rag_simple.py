"""RAG mínimo: parse -> chunk -> embed -> store -> query.

Todos los parámetros vienen de config.toml (misma carpeta).
Correr desde rag-anydoc-app/ para usar su entorno y su .env:

    uv run python ../.muestra_clase/rag_simple.py
"""

import os
import tomllib
from pathlib import Path

import anydoc
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# 0. Configuración
AQUI = Path(__file__).resolve().parent
load_dotenv(AQUI / ".env")  # API keys (solo Gemini/Cohere las necesitan)
with open(AQUI / "config.toml", "rb") as f:
    cfg = tomllib.load(f)

modo = cfg["run"]["modo"]
provider = cfg["embeddings"]["provider"]
p_cfg = cfg[provider]
print(f"Modo: {modo} | Proveedor: {provider} | Colección: {p_cfg['collection_name']}")

# 1. Modelo de embeddings
if provider == "huggingface":
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(
        model_name=p_cfg["model_name"],
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
elif provider == "gemini":
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    embeddings = GoogleGenerativeAIEmbeddings(
        model=p_cfg["model_name"],
        google_api_key=os.environ["GEMINI_API_KEY"],
        output_dimensionality=p_cfg["dimensions"],
    )
elif provider == "cohere":
    from langchain_cohere import CohereEmbeddings
    embeddings = CohereEmbeddings(
        model=p_cfg["model_name"], cohere_api_key=os.environ["COHERE_API_KEY"]
    )
else:
    raise ValueError(f"Proveedor desconocido: {provider}")

# 2. Base vectorial (persistida dentro de .muestra_clase/)
vectorstore = Chroma(
    persist_directory=str(AQUI / cfg["vectorstore"]["persist_dir"]),
    embedding_function=embeddings,
    collection_name=p_cfg["collection_name"],
)

# 3. Ingesta: parse -> chunk -> embed + store
if modo in ("ingest", "all"):
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3"), ("####", "H4")]
    )
    rec_splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunking"]["size"],
        chunk_overlap=cfg["chunking"]["overlap"],
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    for ruta in cfg["ingesta"]["archivos"]:
        ruta = AQUI / ruta
        nombre = ruta.name
        print(f"\n=== {nombre}")

        # Parse: cualquier formato -> Markdown
        markdown = anydoc.to_markdown(str(ruta))
        print(f"Parse: {len(markdown)} caracteres")

        # Chunk: primero por títulos de Markdown, después por tamaño
        metadata = {"filename": nombre, "category": cfg["ingesta"]["category"]}
        secciones = md_splitter.split_text(markdown) or [Document(page_content=markdown)]
        for s in secciones:
            s.metadata.update(metadata)
        chunks = rec_splitter.split_documents(secciones)
        print(f"Chunk: {len(chunks)} fragmentos")

        # Embed + Store: ids determinísticos -> re-ingestar reemplaza, no duplica
        ids = [f"{nombre}-{i}" for i in range(len(chunks))]
        vectorstore.add_documents(chunks, ids=ids)
        print(f"Store: {len(chunks)} chunks guardados")

# 4. Consulta: los k chunks más cercanos
if modo in ("query", "all"):
    consulta = cfg["consulta"]["texto"]
    print(f"\n=== Consulta: {consulta!r}")
    resultados = vectorstore.similarity_search_with_score(consulta, k=cfg["consulta"]["k"])
    for i, (doc, score) in enumerate(resultados, start=1):
        fragmento = doc.page_content[:80].replace("\n", " ")
        print(f"#{i} dist={score:.4f} [{doc.metadata['filename']}] {fragmento}...")

# 5. Estadísticas de la colección
if modo in ("stats", "all"):
    data = vectorstore.get(include=["metadatas"])
    archivos = sorted({m["filename"] for m in data["metadatas"] if m})
    print(f"\n=== Stats\nTotal chunks: {len(data['ids'])}")
    for a in archivos:
        print(f"- {a}")
