"""UI didáctica del Ingester RAG (Streamlit).

Comparte el flujo de ingester/pipeline.py con el CLI (cli.py): ambos consumen
los mismos eventos y solo cambia cómo los muestran. Esta app NO implementa
ninguna etapa: conecta parse -> chunk -> embed -> store y le da al usuario una
interfaz web con 3 pestañas (carga, retrieval, metadatos)."""

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ingester.config import load_config, get_api_key
from ingester.services import PROVIDERS_MAP, resolve_provider_key, build_vector_manager
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

CONFIG_PATH = Path(__file__).parent / "config.toml"
config = load_config(CONFIG_PATH)


@st.cache_resource(show_spinner="Cargando modelo de embeddings en memoria...")
def get_vector_manager(provider_key: str, api_key: str):
    """Mantiene activa la instancia (pesada) del VectorStoreManager."""
    return build_vector_manager(provider_key, api_key, config)


class StreamlitPresenter:
    """Traduce los eventos del pipeline a widgets de Streamlit. Los eventos de
    detalle (Parse/Chunk/Store/Retrieval/Stats) siempre se muestran; el paso a
    paso (StepStart/StepEnd) se puede ocultar con `mostrar_pasos`."""

    def __init__(self, mostrar_pasos: bool):
        self.mostrar_pasos = mostrar_pasos
        self._paso = None

    def _cerrar_paso(self, label: str, state: str) -> None:
        if self._paso is None:
            return
        self._paso.update(label=label, state=state)
        self._paso.__exit__(None, None, None)
        self._paso = None

    def handle(self, evento) -> None:
        if isinstance(evento, StepStart):
            if not self.mostrar_pasos:
                return
            self._cerrar_paso("Paso previo sin cerrar", "complete")
            self._paso = st.status(
                f"Paso {evento.numero}: {evento.titulo}", expanded=evento.expanded
            )
            self._paso.__enter__()
            return

        if isinstance(evento, StepEnd):
            if not self.mostrar_pasos:
                return
            self._cerrar_paso(evento.label, evento.state)
            return

        if isinstance(evento, Final):
            return

        if isinstance(evento, FileStart):
            st.markdown(f"**Archivo {evento.index}/{evento.total}:** `{evento.filename}`")
        elif isinstance(evento, Parsed):
            st.caption(
                f"Parse: {evento.num_documents} documento(s), {evento.num_chars} caracteres"
            )
        elif isinstance(evento, Chunked):
            st.caption(f"Chunk: {evento.num_chunks} chunks generados")
        elif isinstance(evento, Stored):
            st.caption(
                f"Store: {evento.num_chunks} chunks indexados (total {evento.total_chunks})"
            )
        elif isinstance(evento, FileError):
            st.error(f"Error en {evento.filename}: {evento.mensaje}")
        elif isinstance(evento, Retrieval):
            if not evento.candidatos:
                st.info("No se encontraron coincidencias.")
            for i, (doc, score) in enumerate(evento.candidatos, start=1):
                with st.expander(
                    f"Resultado #{i} | Distancia: {score:.4f} | "
                    f"Archivo: {doc.metadata.get('filename')}"
                ):
                    st.markdown("**Contenido del Chunk:**")
                    st.code(doc.page_content, language="markdown")
                    st.markdown("**Metadatos Extraídos:**")
                    st.json(doc.metadata)
        elif isinstance(evento, Stats):
            col1, col2 = st.columns(2)
            col1.metric("Total de Chunks Indexados", evento.total_chunks)
            col2.metric("Total de Archivos Únicos", evento.total_files)
            st.markdown("### Documentos Presentes en la Base Vectorial")
            if evento.file_names:
                st.dataframe(
                    pd.DataFrame({"Nombre del Archivo": evento.file_names}),
                    use_container_width=True,
                )
            else:
                st.info("La colección de ChromaDB está vacía.")


def run_events(eventos, presenter: StreamlitPresenter) -> str:
    final = ""
    for evento in eventos:
        if isinstance(evento, Final):
            final = evento.texto
        else:
            presenter.handle(evento)
    return final


# CONFIGURACIÓN DE PÁGINA E INTERFAZ
st.set_page_config(page_title=config["app"]["title"], layout="wide")
st.title(config["app"]["title"])

st.sidebar.header("1. Inyección de Embeddings")
provider_option = st.sidebar.selectbox(
    "Modelo de Embedding",
    ["HuggingFace", "Google Gemini", "Cohere"],
)
provider_key = resolve_provider_key(provider_option)
_, _, requires_api_key = PROVIDERS_MAP[provider_key]

api_key = ""
if provider_key == "gemini":
    api_key = st.sidebar.text_input(
        "Gemini API Key", type="password", value=get_api_key("gemini")
    )
elif provider_key == "cohere":
    api_key = st.sidebar.text_input(
        "Cohere API Key", type="password", value=get_api_key("cohere")
    )

if requires_api_key and not api_key:
    st.sidebar.warning("Ingrese su API Key en la barra lateral para continuar.")
    st.stop()

vector_mgr = get_vector_manager(provider_key, api_key)

st.sidebar.header("2. Opciones de Chunking")
chunk_size = st.sidebar.slider(
    "Tamaño máximo de chunk",
    config["chunking"]["min_size"],
    config["chunking"]["max_size"],
    config["chunking"]["default_size"],
    step=100,
)
chunk_overlap = st.sidebar.slider("Overlap (Traslape)", 0, 400, 120, step=20)

st.sidebar.header("3. Categoría de los documentos")
category = st.sidebar.selectbox("Categoría", config["app"]["categories"])

mostrar_pasos = st.sidebar.checkbox("Mostrar el paso a paso interno", value=True)

tab_ingest, tab_retrieval, tab_metadata = st.tabs(
    ["Carga de Archivos", "Test de Retrieval", "Metadatos"]
)

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
            presenter = StreamlitPresenter(mostrar_pasos)
            file_paths = []
            tmp_paths = []
            for file in uploaded_files:
                ext = file.name.split(".")[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    tmp.write(file.getvalue())
                    tmp_path = tmp.name
                file_paths.append((tmp_path, file.name))
                tmp_paths.append(tmp_path)

            try:
                resumen = run_events(
                    ejecutar_ingesta(
                        file_paths, vector_mgr, chunk_size, chunk_overlap, category
                    ),
                    presenter,
                )
                st.success(resumen)
            finally:
                for tmp_path in tmp_paths:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

# TAB 2: RETRIEVAL
with tab_retrieval:
    st.subheader("Búsqueda y visualización de Chunks")
    query = st.text_input("Ingrese una consulta o palabra clave:")
    top_k = st.slider("Número de resultados (k)", 1, 10, 3)

    if st.button("Probar Retrieval"):
        if not query.strip():
            st.warning("Escriba una consulta válida.")
        else:
            presenter = StreamlitPresenter(mostrar_pasos)
            run_events(ejecutar_query(query, vector_mgr, top_k), presenter)

# TAB 3: METADATOS
with tab_metadata:
    st.subheader("Información agregada de ChromaDB")
    if st.button("Cargar / Actualizar Estadísticas"):
        presenter = StreamlitPresenter(mostrar_pasos)
        run_events(ejecutar_stats(vector_mgr), presenter)
