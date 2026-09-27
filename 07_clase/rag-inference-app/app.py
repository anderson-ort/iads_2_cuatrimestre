"""
UI didactica del Asistente RAG + Router (Streamlit).

Comparte el flujo paso a paso de src/pipeline.py con el CLI (cli.py): ambos
consumen los mismos eventos, solo cambia como los muestran. Esta version NO usa
las cadenas ya compuestas (router | rag_chain); invoca cada pieza por separado
(embeddings, router, busqueda por cercania, reranker, generacion) para mostrar
en pantalla, paso a paso, que esta haciendo el sistema en cada etapa. Pensada
para mostrarle el flujo a los alumnos, no para produccion.
"""

import os
import sys
from pathlib import Path

import streamlit as st

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

st.set_page_config(page_title=CFG["app"]["title"], layout="wide")
st.title(CFG["app"]["title"])
st.caption(
    "Cada consulta se ejecuta en vivo mostrando cada etapa del pipeline: "
    "embedding de la consulta, router, busqueda por cercania, reranking y "
    "generacion de la respuesta."
)

PROVIDER_LABELS = {
    "HuggingFace (local, debe coincidir con la ingesta)": "huggingface",
    "Google Gemini": "gemini",
    "Cohere": "cohere",
}
RERANKER_LABELS = {
    "Cross-Encoder local": "crossencoder",
    "Cohere Rerank": "cohere",
}

PROVIDER_KEYS = list(PROVIDER_LABELS.values())
RERANKER_KEYS = list(RERANKER_LABELS.values())


@st.cache_resource(show_spinner="Cargando modelos y cadenas...")
def get_components(provider_key, embedding_api_key, google_api_key, reranker_key, cohere_api_key):
    return build_components(
        google_api_key=google_api_key,
        provider_key=provider_key,
        embedding_api_key=embedding_api_key,
        reranker_nombre=reranker_key,
        cohere_api_key=cohere_api_key,
    )


with st.sidebar:
    st.header("Configuracion")

    provider_label = st.selectbox(
        "Proveedor de embeddings",
        list(PROVIDER_LABELS),
        index=PROVIDER_KEYS.index(CFG["embeddings"]["default_provider"]),
    )
    provider_key = PROVIDER_LABELS[provider_label]

    embedding_api_key = ""
    if provider_key == "gemini":
        embedding_api_key = st.text_input(
            "Gemini API key (embeddings)",
            type="password",
            value=os.environ.get("GEMINI_API_KEY", ""),
        )
    elif provider_key == "cohere":
        embedding_api_key = st.text_input(
            "Cohere API key (embeddings)",
            type="password",
            value=os.environ.get("COHERE_API_KEY", ""),
        )

    google_api_key = st.text_input(
        "Google API key (LLM)",
        type="password",
        value=os.environ.get("GOOGLE_API_KEY", ""),
    )

    reranker_label = st.selectbox(
        "Reranker",
        list(RERANKER_LABELS),
        index=RERANKER_KEYS.index(CFG["reranker"]["default"]),
    )
    reranker_key = RERANKER_LABELS[reranker_label]

    cohere_api_key = ""
    if reranker_key == "cohere":
        cohere_api_key = st.text_input(
            "Cohere API key (rerank)",
            type="password",
            value=os.environ.get("COHERE_API_KEY", ""),
        )

    st.caption(
        "El proveedor de embeddings debe ser el mismo con el que se ingestaron "
        "los documentos: Chroma no admite distintas dimensiones en una misma coleccion."
    )

    st.divider()
    st.subheader("Parametros del pipeline")
    k_candidatos = st.slider(
        "Candidatos del bi-encoder (k)",
        min_value=2,
        max_value=20,
        value=CFG["retrieval"]["k_candidatos"],
    )
    top_n_rerank = st.slider(
        "Documentos finales tras el reranker (top_n)",
        min_value=1,
        max_value=10,
        value=CFG["retrieval"]["top_n"],
    )
    mostrar_pasos = st.checkbox("Mostrar el paso a paso interno", value=True)

# No construir el pipeline hasta tener la key del LLM.
if not google_api_key:
    st.info("Ingrese la Google API key en la barra lateral para empezar.")
    st.stop()

try:
    componentes = get_components(
        provider_key, embedding_api_key, google_api_key, reranker_key, cohere_api_key
    )
except Exception as e:
    st.error(f"No se pudo inicializar el pipeline: {e}")
    st.stop()

info_coleccion = componentes["collection"]
st.caption(
    f"Coleccion en uso: `{info_coleccion['collection_name']}` · "
    f"{info_coleccion['total_chunks']} chunks · "
    f"{info_coleccion['total_files']} archivos"
)
if info_coleccion["total_chunks"] == 0:
    st.warning(
        "La coleccion seleccionada esta vacia. Elegi el mismo proveedor de "
        "embeddings con el que ingestaste los documentos."
    )

if "historial" not in st.session_state:
    st.session_state.historial = []


class StreamlitPresenter:
    """Traduce los eventos del pipeline a widgets de Streamlit. Reproduce el
    comportamiento original: cada paso abre un st.status que se cierra con su
    label final (complete o error). Si mostrar_pasos es False ignora los pasos
    y solo deja pasar el evento Final."""

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

        if not self.mostrar_pasos:
            return

        if isinstance(evento, Embedding):
            st.write(f"Dimension del vector: **{len(evento.vector)}**")
            st.code(
                str([round(v, 4) for v in evento.vector[:8]]) + " ...", language="text"
            )
            st.caption(f"Tiempo: {evento.elapsed:.3f} s")
        elif isinstance(evento, EmbeddingError):
            st.warning(f"No se pudo mostrar el vector de embedding: {evento.mensaje}")
        elif isinstance(evento, Router):
            st.json(evento.decision.model_dump())
        elif isinstance(evento, Tool):
            st.json(evento.respuesta.model_dump())
        elif isinstance(evento, Retrieval):
            for i, (doc, score) in enumerate(evento.candidatos, start=1):
                archivo = doc.metadata.get("filename", "desconocido")
                st.markdown(f"**#{i}** - distancia: `{score:.4f}` - archivo: `{archivo}`")
                st.caption(
                    doc.page_content[:220]
                    + ("..." if len(doc.page_content) > 220 else "")
                )
        elif isinstance(evento, Rerank):
            for i, doc in enumerate(evento.top_docs, start=1):
                archivo = doc.metadata.get("filename", "desconocido")
                puesto_original = evento.posiciones.get(id(doc), "?")
                st.markdown(
                    f"**Puesto nuevo #{i}** (era #{puesto_original}) - archivo: `{archivo}`"
                )
                st.caption(
                    doc.page_content[:220]
                    + ("..." if len(doc.page_content) > 220 else "")
                )
        elif isinstance(evento, Generation):
            st.text_area(
                "Contexto enviado al LLM", evento.contexto, height=180, disabled=True
            )
            st.json(evento.respuesta.model_dump())


def ejecutar_pipeline(pregunta: str) -> str:
    """Consume el flujo compartido y devuelve la respuesta final en texto plano
    para guardarla en el historial."""
    presenter = StreamlitPresenter(mostrar_pasos)
    for evento in run_pipeline(pregunta, componentes, k_candidatos, top_n_rerank):
        if isinstance(evento, Final):
            return evento.texto
        presenter.handle(evento)
    return ""


for turno in st.session_state.historial:
    with st.chat_message(turno["role"]):
        st.markdown(turno["contenido"])

if pregunta := st.chat_input("Escribi tu pregunta..."):
    if not guardrail_check(pregunta):
        st.warning("Entrada invalida.")
        st.stop()

    st.session_state.historial.append({"role": "user", "contenido": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        try:
            respuesta = ejecutar_pipeline(pregunta)
        except Exception as e:
            respuesta = f"Error procesando la consulta: {e}"
            st.error(respuesta)
        else:
            st.markdown(respuesta)

    st.session_state.historial.append({"role": "assistant", "contenido": respuesta})
