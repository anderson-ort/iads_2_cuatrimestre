import os
import tempfile
import pandas as pd
import streamlit as st
from pathlib import Path

from ingester.embeddings import (
    HuggingFaceEmbeddingProvider,
    GeminiEmbeddingProvider,
    CohereEmbeddingProvider,
)
from ingester.parser import AnyDocParserService
from ingester.chunker import HybridChunker
from ingester.vectorstore import VectorStoreManager
from ingester.config import load_config


CONFIG_PATH = Path(__file__).parent / "config.toml"
config = load_config(CONFIG_PATH)

# FUNCIONES CON CACHÉ (evitan instanciar objetos pesados repetidamente)
PROVIDERS_MAP = {
    "huggingface": (HuggingFaceEmbeddingProvider, "huggingface", False),
    "gemini": (GeminiEmbeddingProvider, "gemini", True),
    "cohere": (CohereEmbeddingProvider, "cohere", True),
}

@st.cache_resource(show_spinner="Cargando modelo de embeddings en memoria...")
def get_embedding_provider(provider_option: str, api_key: str):
    """Carga e instancia el proveedor de embeddings en caché."""
    provider_key = next((k for k in PROVIDERS_MAP if k in provider_option.lower()), None)

    if not provider_key:
        raise ValueError(f"Proveedor no reconocido: {provider_option}")

    cls, config_section, requires_api_key = PROVIDERS_MAP[provider_key]

    if requires_api_key and not api_key:
        st.warning("Por favor, ingrese su API Key en la barra lateral para continuar.")
        st.stop()

    model_name = config[config_section]["model_name"]
    kwargs = {"model_name": model_name}
    
    if requires_api_key:
        kwargs["api_key"] = api_key

    return cls(**kwargs)


@st.cache_resource(show_spinner="Conectando a ChromaDB...")
def get_vector_manager(_provider, persist_dir: str, collection_name:str):
    """Mantiene activa la instancia de conexión con ChromaDB."""
    return VectorStoreManager(embedding_provider=_provider, persist_dir=persist_dir, collection_name=collection_name)


# CONFIGURACIÓN DE PÁGINA E INTERFAZ

st.set_page_config(page_title=config["app"]["title"], layout="wide")
st.title(config["app"]["title"])

st.sidebar.header("1. Inyección de Embeddings")
provider_option = st.sidebar.selectbox(
    "Modelo de Embedding",
    ["HuggingFace (Local Multilingüe)", "Google Gemini (text-embedding-004)", "Cohere (embed-multilingual-v3.0)"],
)

api_key = ""
if "Gemini" in provider_option:
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
elif "Cohere" in provider_option:
    api_key = st.sidebar.text_input("Cohere API Key", type="password")

# Obtención reutilizable del proveedor de embeddings
embedding_provider = get_embedding_provider(provider_option, api_key)

st.sidebar.header("2. Opciones de Chunking")
chunk_size = st.sidebar.slider(
    "Tamaño máximo de chunk", 
    config["chunking"]["min_size"], 
    config["chunking"]["max_size"], 
    config["chunking"]["default_size"], 
    step=100
)
chunk_overlap = st.sidebar.slider("Overlap (Traslape)", 0, 400, 120, step=20)

st.sidebar.header("3. Categoría de los documentos")
category = st.sidebar.selectbox("Categoría", config["app"]["categories"])

# Instancias reutilizables de servicios
parser_service = AnyDocParserService()
vector_mgr = get_vector_manager(embedding_provider, config["vectorstore"]["persist_dir"], config["vectorstore"]["collection_name"])

tab_ingest, tab_retrieval, tab_metadata = st.tabs(["Carga de Archivos", "Test de Retrieval", "Metadatos"])

# TAB 1: CARGA DE ARCHIVOS
with tab_ingest:
    st.markdown(
        "Formatos soportados por AnyDoc: **PDF (texto), Word (.docx, .doc), "
        "PowerPoint (.pptx, .ppt), Excel (.xlsx, .xls), EPUB, CSV, RTF, ODT**."
    )
    uploaded_files = st.file_uploader(
        "Seleccionar archivos para ingestar",
        type=["pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "epub", "csv", "rtf", "odt"],
        accept_multiple_files=True,
    )

    if st.button("Procesar e Ingestar en ChromaDB", type="primary"):
        if not uploaded_files:
            st.warning("Seleccione al menos un archivo.")
        else:
            try:
                # Se asignan los valores reales del slider en lugar de usar los fijos del config
                chunker = HybridChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                total_chunks = 0
                progress_bar = st.progress(0)

                for idx, file in enumerate(uploaded_files):
                    ext = file.name.split(".")[-1]
                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                            tmp.write(file.getvalue())
                            tmp_path = tmp.name

                        parsed_docs = parser_service.parse(tmp_path, file.name)
                        for d in parsed_docs:
                            d.metadata["category"] = category
                        chunks = chunker.split_documents(parsed_docs)
                        total_chunks += vector_mgr.add_documents(chunks)
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)

                    progress_bar.progress((idx + 1) / len(uploaded_files))

                st.success(f"Completado. Se generaron e indexaron {total_chunks} chunks.")
            except Exception as e:
                st.error(f"Error durante el procesamiento: {e}")

# TAB 2: RETRIEVAL
with tab_retrieval:
    st.subheader("Búsqueda y visualización de Chunks")
    query = st.text_input("Ingrese una consulta o palabra clave:")
    top_k = st.slider("Número de resultados (k)", 1, 10, 3)

    if st.button("Probar Retrieval"):
        if not query.strip():
            st.warning("Escriba una consulta válida.")
        else:
            try:
                vs = vector_mgr.get_vectorstore()
                results = vs.similarity_search_with_score(query, k=top_k)

                if not results:
                    st.info("No se encontraron coincidencias.")
                else:
                    for i, (doc, score) in enumerate(results, start=1):
                        with st.expander(f"Resultado #{i} | Distancia: {score:.4f} | Archivo: {doc.metadata.get('filename')}"):
                            st.markdown("**Contenido del Chunk:**")
                            st.code(doc.page_content, language="markdown")
                            st.markdown("**Metadatos Extraídos:**")
                            st.json(doc.metadata)
            except Exception as e:
                st.error(f"Error ejecutando la búsqueda: {e}")

# TAB 3: METADATOS
with tab_metadata:
    st.subheader("Información agregada de ChromaDB")
    if st.button("Cargar / Actualizar Estadísticas"):
        try:
            stats = vector_mgr.get_stats()

            col1, col2 = st.columns(2)
            col1.metric("Total de Chunks Indexados", stats["total_chunks"])
            col2.metric("Total de Archivos Únicos", stats["total_files"])

            st.markdown("### Documentos Presentes en la Base Vectorial")
            if stats["file_names"]:
                st.dataframe(pd.DataFrame({"Nombre del Archivo": stats["file_names"]}), use_container_width=True)
            else:
                st.info("La colección de ChromaDB está vacía.")
        except Exception as e:
            st.error(f"Error consultando los metadatos: {e}")
