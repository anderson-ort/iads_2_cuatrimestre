# Ingestador RAG + Router (proyecto completo)

## Estructura del proyecto

```
rag_app/
├── schemas.py
├── prompts.py
├── retrieval.py
├── router_chain.py
├── rag_chain.py
├── mock_tools.py
├── guardrails.py
├── services.py
├── streamlit_app.py
├── main.py
├── requirements.txt
```

`rag_app/` **no copia** el paquete `ingester` del proyecto `rag-anydoc-app/`: lo
importa directamente. De ahi saca dos piezas ya probadas y mantenidas en un solo
lugar:

- `ingester/vectorstore.py` → `VectorStoreManager` (conexion + persistencia en
  ChromaDB).
- `ingester/embeddings.py` → `IEmbeddingProvider` y sus implementaciones
  (`HuggingFaceEmbeddingProvider`, `GeminiEmbeddingProvider`,
  `CohereEmbeddingProvider`).

De esta forma el ingestador (la app Streamlit de `rag-anydoc-app/app.py`) y el
asistente de preguntas (`rag_app/`) comparten **la misma configuracion de
vectorstore** (`config.toml`: `persist_dir` + `collection_name`) y no hay dos
formas distintas de abrir Chroma.

## Documentacion

## Refactor: Pydantic end-to-end y prompts centralizados

### Que cambio

1. **`prompts.py` (nuevo)**: todos los prompts vivian hardcodeados dentro de
   `router_chain.py` y `rag_chain.py`. Ahora estan en un solo lugar.
2. **`ConsultaProducto` (nuevo, en `schemas.py`)**: `consultar_stock` y
   `consultar_promociones` recibian un `str` crudo. Ahora reciben un modelo
   pydantic validado, con normalizacion (`strip().lower()`) centralizada en
   `.normalizado()` en vez de repetida en cada funcion.

Con esto, **toda entrada y salida del pipeline que cruza un limite de
funcion/LLM es un modelo pydantic**: nada de dicts sueltos ni strings sin forma.

### Mapa de esquemas (`schemas.py`)

| Modelo | Donde se usa | Rol |
|---|---|---|
| `RouterDecision` | salida de `router_chain.py` | fuerza `intent` a uno de 4 valores validos (enum), evita que el LLM invente una categoria |
| `ConsultaProducto` | entrada de `mock_tools.py` | valida y normaliza el nombre de producto antes de consultar |
| `StockAnswer` | salida de `consultar_stock` | disponibilidad + cantidad + mensaje |
| `PromoAnswer` | salida de `consultar_promociones` | lista de promociones + mensaje |
| `RagAnswer` | salida de `rag_chain.py` | `informacion_insuficiente: bool` obliga a declarar cuando el contexto no alcanza, en vez de vacilar |
| `FuenteCitada` | dentro de `RagAnswer.fuentes` | archivo + fragmento citado |

Todas las salidas de LLM pasan por `llm.with_structured_output(Modelo)`
(function calling de Gemini), no por parseo de texto libre.

### `prompts.py`

```python
ROUTER_SYSTEM_PROMPT = "..."   # usado por router_chain.py
RAG_SYSTEM_PROMPT   = "..."    # usado por rag_chain.py
RAG_HUMAN_TEMPLATE  = "Contexto:\n{contexto}\n\nPregunta: {pregunta}"
```

`router_chain.py` y `rag_chain.py` ahora importan de aca en vez de tener el
texto embebido en un `ChatPromptTemplate.from_messages([...])` inline.

### Flujo de datos actualizado

```
pregunta (str)
  -> router_chain -> RouterDecision (intent, producto, justificacion)
       intent = stock/promociones -> ConsultaProducto(producto=...)
                                        -> consultar_stock / consultar_promociones
                                        -> StockAnswer / PromoAnswer
       intent = tecnico -> rag_chain -> RagAnswer (respuesta, confianza, fuentes, informacion_insuficiente)
```

## Integracion con `VectorStoreManager` (rag-anydoc-app)

### Que cambio

Antes `main.py` construia los embeddings y el vectorstore a mano:

```python
embeddings = HuggingFaceEmbeddings(...)
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings, ...)
```

Ahora eso vive en `services.py`, que delega en el paquete `ingester`:

```python
VectorStoreManager(embedding_provider, persist_dir, collection_name).get_vectorstore()
```

### Por que

- **Una sola fuente de verdad**: el ingestador y el asistente abren la misma
  coleccion con el mismo `persist_dir`/`collection_name` del `config.toml`.
- **Intercambio de embeddings sin tocar el pipeline**: los providers ya estan
  encapsulados detras de `IEmbeddingProvider`; el resto del codigo solo pide
  `get_vectorstore()`.
- **Reutilizacion de `get_stats()`** para diagnostico (cantidad de chunks y
  archivos) desde la UI.

### Como se importa `ingester` (proyecto hermano)

`rag_app/` esta al lado de `rag-anydoc-app/`. En `services.py` se agrega la ruta
del vecino a `sys.path` una vez:

```python
ANY_DOC_APP = Path(__file__).resolve().parents[1] / "rag-anydoc-app"
if str(ANY_DOC_APP) not in sys.path:
    sys.path.insert(0, str(ANY_DOC_APP))
```

Asi `from ingester.vectorstore import VectorStoreManager` funciona sin instalar
nada. El `config.toml` tambien se lee de `ANY_DOC_APP`, y el `persist_dir`
relativo (`./database/chroma_db`) se resuelve contra esa carpeta, para que no
dependa del directorio desde el que se lance Streamlit.

### Advertencia: dimensiones de embeddings

Chroma no admite vectores de distinta dimension en una misma coleccion. Hay que
usar **el mismo proveedor con el que se ingestaron** los documentos o la
busqueda de similitud falla (o devuelve basura). Por eso en la UI el selector de
embeddings va acompanado de una nota, y el `GeminiEmbeddingProvider` /
`CohereEmbeddingProvider` piden su API key.

## Capa Streamlit (Q&A)

`streamlit_app.py` es una UI de chat para el usuario final. No ingesta: asume
que la base ya fue cargada por `rag-anydoc-app` (pagina de ingesta).

### Barra lateral (configuracion)

- Selector de **proveedor de embeddings** (HuggingFace local / Gemini / Cohere).
- **API key** condicional segun el proveedor (Gemini o Cohere).
- **Google API key** para el LLM (por defecto lee `GOOGLE_API_KEY` del entorno).
- Selector de **reranker** (Cross-Encoder local / Cohere Rerank), con su API key
  cuando corresponde.

### Caching y estado

- `@st.cache_resource` para no recargar el modelo de embeddings, el reranker ni
  reconstruir las cadenas en cada interaccion.
- `st.session_state` para el historial del chat.
- `st.chat_input` + `st.chat_message` para la conversacion.

### Render de la respuesta

Reutiliza exactamente la logica de despacho de `main.py`:

- Muestra `RouterDecision` (`intent` + justificacion).
- `STOCK` / `PROMOCIONES` → `ConsultarProducto` + `mock_tools`.
- `TECNICO` → `RagAnswer`; si `informacion_insuficiente` avisa, si no muestra
  respuesta, confianza y fuentes.
- Cualquier excepcion (p. ej. dimensiones incompatibles) se muestra con
  `st.error` sin tumbar la app.

### Flujo

```
[Sidebar] provider + keys + reranker
      |
      v
services.build_pipeline(...)  --(cache_resource)--> router, rag_chain
      |
      v
pregunta (st.chat_input)
      |
      v
router.invoke -> RouterDecision
      |\
      | \-> stock/promos -> mock_tools -> respuesta
      | \-> tecnico -> rag_chain -> RagAnswer (respuesta + fuentes)
      |
      v
st.chat_message (historial en session_state)
```

## Codigo

### `schemas.py`

```python
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    PROMOCIONES = "promociones"
    STOCK = "stock"
    TECNICO = "tecnico"
    OTRO = "otro"


class RouterDecision(BaseModel):
    """Salida estructurada del router. El enum obliga al LLM a elegir una
    categoria valida en vez de responder texto libre ambiguo."""

    intent: Intent = Field(description="Categoria de la consulta del usuario")
    producto: Optional[str] = Field(
        default=None, description="Nombre del producto mencionado, si aplica"
    )
    justificacion: str = Field(description="Una oracion breve justificando la clasificacion")


class Confianza(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class FuenteCitada(BaseModel):
    archivo: str
    fragmento: str = Field(description="Extracto breve del chunk usado, maximo 25 palabras")


class RagAnswer(BaseModel):
    """Respuesta del pipeline tecnico. informacion_insuficiente fuerza al modelo
    a declarar explicitamente cuando el contexto no alcanza, en lugar de
    vacilar o inventar (mitiga alucinaciones)."""

    respuesta: str = Field(description="Respuesta directa y concisa a la pregunta")
    confianza: Confianza
    informacion_insuficiente: bool = Field(
        description="True si el contexto recuperado no contiene la respuesta"
    )
    fuentes: List[FuenteCitada] = Field(default_factory=list)


class ConsultaProducto(BaseModel):
    """Entrada validada para las herramientas de stock/promociones. Centraliza
    la normalizacion (strip + lower) para que ambas herramientas la reciban
    ya limpia, en vez de repetir el parseo de string crudo en cada una."""

    producto: Optional[str] = Field(default=None, description="Nombre del producto consultado")

    def normalizado(self) -> Optional[str]:
        return self.producto.strip().lower() if self.producto else None


class StockAnswer(BaseModel):
    producto: str
    disponible: bool
    cantidad: Optional[int] = None
    mensaje: str


class PromoAnswer(BaseModel):
    producto: Optional[str] = None
    promociones: List[str] = Field(default_factory=list)
    mensaje: str
```

### `prompts.py`

```python
ROUTER_SYSTEM_PROMPT = """\
Clasificas la consulta de un usuario en una de estas categorias:
- promociones: descuentos, ofertas, cuotas.
- stock: disponibilidad o cantidad de un producto.
- tecnico: dudas conceptuales, politicas, documentacion, procedimientos.
- otro: cualquier otra cosa.
Responde unicamente con el esquema pedido. No agregues texto fuera de el.\
"""

RAG_SYSTEM_PROMPT = """\
Respondes preguntas usando SOLO el contexto entregado. No inventes datos que \
no esten en el. Si el contexto no alcanza para responder, marca \
informacion_insuficiente=true y dilo en 'respuesta' en vez de adivinar. \
Nunca uses frases vacilantes como 'podria ser' o 'tal vez': da una afirmacion \
clara, o declara explicitamente que falta informacion. Cita cada fuente que \
uses en 'fuentes'.\
"""

RAG_HUMAN_TEMPLATE = "Contexto:\n{contexto}\n\nPregunta: {pregunta}"
```

### `retrieval.py`

```python
from typing import List, Protocol

from langchain_core.documents import Document
from langchain_chroma import Chroma


class Reranker(Protocol):
    def rerank(self, query: str, docs: List[Document], top_n: int) -> List[Document]: ...


class CrossEncoderReranker:
    """Cross-encoder local via sentence-transformers. Gratis, sin limite de
    llamadas ni API key: es la opcion por defecto para el free tier."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, docs: List[Document], top_n: int = 4) -> List[Document]:
        if not docs:
            return []
        pairs = [(query, d.page_content) for d in docs]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]


class CohereReranker:
    """Alternativa via API de Cohere (plan free: ~1000 llamadas/mes).
    Util si se prefiere no cargar el modelo local en memoria."""

    def __init__(self, api_key: str, model: str = "rerank-multilingual-v3.0"):
        import cohere

        self.client = cohere.Client(api_key)
        self.model = model

    def rerank(self, query: str, docs: List[Document], top_n: int = 4) -> List[Document]:
        if not docs:
            return []
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=[d.page_content for d in docs],
            top_n=top_n,
        )
        return [docs[r.index] for r in response.results]


def biencoder_retrieve(vectorstore: Chroma, query: str, k: int = 10) -> List[Document]:
    """Primera etapa: busqueda densa rapida (bi-encoder) con recall alto y
    precision moderada. El reranker refina estos candidatos despues."""
    return vectorstore.similarity_search(query, k=k)
```

### `router_chain.py`

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas import RouterDecision
from prompts import ROUTER_SYSTEM_PROMPT

ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [("system", ROUTER_SYSTEM_PROMPT), ("human", "{pregunta}")]
)


def build_router_chain(api_key: str):
    # Clasificar 4 categorias no requiere razonamiento: modelo lite y
    # thinking_budget=0 (sin tokens de pensamiento) para bajar costo y latencia.
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=api_key,
        temperature=0,
        thinking_budget=0,
    )
    # with_structured_output fuerza al modelo a devolver un RouterDecision
    # valido (via function calling), no texto libre que haya que parsear.
    structured_llm = llm.with_structured_output(RouterDecision)
    return ROUTER_PROMPT | structured_llm
```

### `rag_chain.py`

```python
from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas import RagAnswer
from retrieval import biencoder_retrieve, Reranker
from prompts import RAG_SYSTEM_PROMPT, RAG_HUMAN_TEMPLATE

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [("system", RAG_SYSTEM_PROMPT), ("human", RAG_HUMAN_TEMPLATE)]
)


def format_context(docs: List[Document]) -> str:
    if not docs:
        return "(sin resultados relevantes)"
    partes = [f"[{d.metadata.get('filename', 'desconocido')}]\n{d.page_content}" for d in docs]
    return "\n\n---\n\n".join(partes)


def build_rag_chain(api_key: str, vectorstore: Chroma, reranker: Reranker):
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0)
    structured_llm = llm.with_structured_output(RagAnswer)

    def retrieve_and_rerank(inputs: dict) -> dict:
        pregunta = inputs["pregunta"]
        candidatos = biencoder_retrieve(vectorstore, pregunta, k=10)
        top_docs = reranker.rerank(pregunta, candidatos, top_n=4)
        return {"pregunta": pregunta, "contexto": format_context(top_docs)}

    return RunnableLambda(retrieve_and_rerank) | RAG_PROMPT | structured_llm
```

### `mock_tools.py`

```python
from schemas import ConsultaProducto, StockAnswer, PromoAnswer

# TODO: reemplazar por consultas reales a la DB/API de stock y promociones.
MOCK_STOCK = {"notebook": 12, "monitor": 0, "teclado": 34}
MOCK_PROMOS = {
    "notebook": ["15% off con tarjeta X", "3 cuotas sin interes"],
    "monitor": ["2x1 en accesorios"],
}


def consultar_stock(consulta: ConsultaProducto) -> StockAnswer:
    p = consulta.normalizado()
    cantidad = MOCK_STOCK.get(p) if p else None
    if cantidad is None:
        return StockAnswer(
            producto=consulta.producto or "desconocido",
            disponible=False,
            mensaje="Producto no encontrado en el catalogo.",
        )
    return StockAnswer(
        producto=consulta.producto,
        disponible=cantidad > 0,
        cantidad=cantidad,
        mensaje=f"Quedan {cantidad} unidades." if cantidad > 0 else "Sin stock.",
    )


def consultar_promociones(consulta: ConsultaProducto) -> PromoAnswer:
    p = consulta.normalizado()
    if p:
        promos = MOCK_PROMOS.get(p, [])
        msg = f"{len(promos)} promocion(es) encontradas." if promos else "Sin promociones para ese producto."
        return PromoAnswer(producto=consulta.producto, promociones=promos, mensaje=msg)
    todas = [f"{k}: {', '.join(v)}" for k, v in MOCK_PROMOS.items()]
    return PromoAnswer(producto=None, promociones=todas, mensaje="Promociones generales.")
```

### `guardrails.py`

```python
def guardrail_check(texto: str) -> bool:
    """Punto de extension para guardrails (ej. NeMo Guardrails, Llama Guard,
    o reglas propias de negocio). Por ahora solo valida que no este vacio."""
    return bool(texto and texto.strip())
```

### `services.py`

```python
import sys
from pathlib import Path
from typing import Tuple

from langchain_chroma import Chroma

# Reutiliza el paquete ingester del proyecto hermano rag-anydoc-app.
ANY_DOC_APP = Path(__file__).resolve().parents[1] / "rag-anydoc-app"
if str(ANY_DOC_APP) not in sys.path:
    sys.path.insert(0, str(ANY_DOC_APP))

from ingester.config import load_config
from ingester.embeddings import (
    HuggingFaceEmbeddingProvider,
    GeminiEmbeddingProvider,
    CohereEmbeddingProvider,
)
from ingester.vectorstore import VectorStoreManager

from retrieval import CrossEncoderReranker, CohereReranker, Reranker
from router_chain import build_router_chain
from rag_chain import build_rag_chain

CONFIG_PATH = ANY_DOC_APP / "config.toml"

# (clase, seccion del config.toml, requiere api key)
EMBEDDING_PROVIDERS = {
    "huggingface": (HuggingFaceEmbeddingProvider, "huggingface", False),
    "gemini": (GeminiEmbeddingProvider, "gemini", True),
    "cohere": (CohereEmbeddingProvider, "cohere", True),
}


def build_embedding_provider(provider_key: str, api_key: str = ""):
    cls, section, requires_api_key = EMBEDDING_PROVIDERS[provider_key]
    model_name = load_config(CONFIG_PATH)[section]["model_name"]
    kwargs = {"model_name": model_name}
    if requires_api_key:
        if not api_key:
            raise ValueError(f"El proveedor '{provider_key}' requiere una API key.")
        kwargs["api_key"] = api_key
    return cls(**kwargs)


def build_vector_manager(provider_key: str, api_key: str = "") -> VectorStoreManager:
    cfg = load_config(CONFIG_PATH)
    # persist_dir es relativo a rag-anydoc-app, no al CWD actual.
    persist_dir = str((ANY_DOC_APP / cfg["vectorstore"]["persist_dir"]).resolve())
    provider = build_embedding_provider(provider_key, api_key)
    return VectorStoreManager(
        embedding_provider=provider,
        persist_dir=persist_dir,
        collection_name=cfg["vectorstore"]["collection_name"],
    )


def build_vectorstore(provider_key: str, api_key: str = "") -> Chroma:
    return build_vector_manager(provider_key, api_key).get_vectorstore()


def build_reranker(nombre: str, cohere_api_key: str = "") -> Reranker:
    if nombre == "cohere":
        if not cohere_api_key:
            raise ValueError("El reranker de Cohere requiere una API key.")
        return CohereReranker(api_key=cohere_api_key)
    return CrossEncoderReranker()


def build_pipeline(
    google_api_key: str,
    provider_key: str,
    embedding_api_key: str = "",
    reranker_nombre: str = "crossencoder",
    cohere_api_key: str = "",
) -> Tuple:
    vectorstore = build_vectorstore(provider_key, embedding_api_key)
    reranker = build_reranker(reranker_nombre, cohere_api_key)
    router = build_router_chain(google_api_key)
    rag_chain = build_rag_chain(google_api_key, vectorstore, reranker)
    return router, rag_chain
```

### `main.py` (CLI)

```python
import os
import sys

from schemas import Intent, ConsultaProducto
from services import build_pipeline
from guardrails import guardrail_check
from mock_tools import consultar_stock, consultar_promociones


def main() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el entorno.")
        sys.exit(1)

    # Mismo wiring que la UI pero con embeddings locales (HuggingFace) y
    # reranker cross-encoder. Cambiar los parametros para usar Gemini/Cohere.
    router, rag_chain = build_pipeline(
        google_api_key=api_key,
        provider_key="huggingface",
        reranker_nombre="crossencoder",
    )

    print("Asistente listo. Escriba 'salir' para terminar.")
    while True:
        pregunta = input("\nPregunta: ").strip()
        if not pregunta or pregunta.lower() in {"salir", "exit"}:
            break
        if not guardrail_check(pregunta):
            print("Entrada invalida.")
            continue

        decision = router.invoke({"pregunta": pregunta})
        print(f"[router -> {decision.intent.value}] {decision.justificacion}")

        if decision.intent == Intent.STOCK:
            resp = consultar_stock(ConsultaProducto(producto=decision.producto or pregunta))
            print(resp.mensaje)

        elif decision.intent == Intent.PROMOCIONES:
            resp = consultar_promociones(ConsultaProducto(producto=decision.producto))
            print(resp.mensaje)
            for p in resp.promociones:
                print(f" - {p}")

        elif decision.intent == Intent.TECNICO:
            resp = rag_chain.invoke({"pregunta": pregunta})
            if resp.informacion_insuficiente:
                print("No tengo informacion suficiente en la base para responder eso.")
            else:
                print(resp.respuesta)
                print(f"(confianza: {resp.confianza.value})")
                for f in resp.fuentes:
                    print(f"  fuente: {f.archivo} - {f.fragmento}")

        else:
            print("No pude clasificar la consulta. Reformule, por favor.")


if __name__ == "__main__":
    main()
```

### `streamlit_app.py` (UI de Q&A)

```python
import os

import streamlit as st

from schemas import Intent, ConsultaProducto
from services import build_pipeline
from guardrails import guardrail_check
from mock_tools import consultar_stock, consultar_promociones

st.set_page_config(page_title="Asistente RAG + Router", layout="wide")
st.title("Asistente RAG + Router")

PROVIDER_LABELS = {
    "HuggingFace (local, debe coincidir con la ingesta)": "huggingface",
    "Google Gemini": "gemini",
    "Cohere": "cohere",
}
RERANKER_LABELS = {
    "Cross-Encoder local": "crossencoder",
    "Cohere Rerank": "cohere",
}


@st.cache_resource(show_spinner="Cargando modelos y cadenas...")
def get_pipeline(provider_key, embedding_api_key, google_api_key, reranker_key, cohere_api_key):
    return build_pipeline(
        google_api_key=google_api_key,
        provider_key=provider_key,
        embedding_api_key=embedding_api_key,
        reranker_nombre=reranker_key,
        cohere_api_key=cohere_api_key,
    )


with st.sidebar:
    st.header("Configuracion")

    provider_label = st.selectbox("Proveedor de embeddings", list(PROVIDER_LABELS))
    provider_key = PROVIDER_LABELS[provider_label]

    embedding_api_key = ""
    if provider_key == "gemini":
        embedding_api_key = st.text_input("Gemini API key (embeddings)", type="password")
    elif provider_key == "cohere":
        embedding_api_key = st.text_input("Cohere API key (embeddings)", type="password")

    google_api_key = st.text_input(
        "Google API key (LLM)",
        type="password",
        value=os.environ.get("GOOGLE_API_KEY", ""),
    )

    reranker_label = st.selectbox("Reranker", list(RERANKER_LABELS))
    reranker_key = RERANKER_LABELS[reranker_label]

    cohere_api_key = ""
    if reranker_key == "cohere":
        cohere_api_key = st.text_input("Cohere API key (rerank)", type="password")

    st.caption(
        "El proveedor de embeddings debe ser el mismo con el que se ingestaron "
        "los documentos: Chroma no admite distintas dimensiones en una misma coleccion."
    )

# No construir el pipeline hasta tener la key del LLM.
if not google_api_key:
    st.info("Ingrese la Google API key en la barra lateral para empezar.")
    st.stop()

try:
    router, rag_chain = get_pipeline(
        provider_key, embedding_api_key, google_api_key, reranker_key, cohere_api_key
    )
except Exception as e:
    st.error(f"No se pudo inicializar el pipeline: {e}")
    st.stop()

if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

for msg in st.session_state.mensajes:
    with st.chat_message(msg["role"]):
        st.markdown(msg["contenido"])

if pregunta := st.chat_input("Escribi tu pregunta..."):
    if not guardrail_check(pregunta):
        st.warning("Entrada invalida.")
        st.stop()

    st.session_state.mensajes.append({"role": "user", "contenido": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        try:
            decision = router.invoke({"pregunta": pregunta})
            st.caption(f"router -> {decision.intent.value}: {decision.justificacion}")

            if decision.intent == Intent.STOCK:
                resp = consultar_stock(ConsultaProducto(producto=decision.producto or pregunta))
                respuesta = resp.mensaje

            elif decision.intent == Intent.PROMOCIONES:
                resp = consultar_promociones(ConsultaProducto(producto=decision.producto))
                respuesta = resp.mensaje + "\n\n" + "\n".join(f"- {p}" for p in resp.promociones)

            elif decision.intent == Intent.TECNICO:
                resp = rag_chain.invoke({"pregunta": pregunta})
                if resp.informacion_insuficiente:
                    respuesta = "No tengo informacion suficiente en la base para responder eso."
                else:
                    respuesta = resp.respuesta
                    st.caption(f"confianza: {resp.confianza.value}")
                    for f in resp.fuentes:
                        st.caption(f"fuente: {f.archivo} - {f.fragmento}")

            else:
                respuesta = "No pude clasificar la consulta. Reformule, por favor."

            st.markdown(respuesta)
        except Exception as e:
            respuesta = f"Error procesando la consulta: {e}"
            st.error(respuesta)

    st.session_state.mensajes.append({"role": "assistant", "contenido": respuesta})
```

## Como ejecutar

```bash
# 1) Ingestar documentos (app Streamlit de rag-anydoc-app)
cd rag-anydoc-app
uv run start            # o: streamlit run app.py

# 2) Asistente de preguntas (UI de rag_app)
cd ../rag_app
streamlit run streamlit_app.py

# Alternativa CLI (sin UI)
cd rag_app
GOOGLE_API_KEY=... python main.py
```

## Pendiente / siguiente paso natural

- Guardrails reales: hoy `guardrail_check()` solo valida que la pregunta no
  este vacia. El hook ya esta listo para enchufar NeMo Guardrails / Llama Guard
  o patrones prohibidos sobre `RagAnswer.respuesta` antes de mostrarla.
- Historial conversacional con memoria (hoy cada pregunta es independiente).
- Cuando se migre a FastAPI, `ConsultaProducto` y `RouterDecision` sirven tal
  cual como modelos de request/response de los endpoints.

### `requirements.txt`

```text
streamlit
pydantic
langchain-core
langchain-chroma
langchain-huggingface
langchain-google-genai
langchain-cohere
sentence-transformers
cohere
# solo si se ingestan documentos dentro de rag_app (no para Q&A):
# firecrawl-anydoc
# pandas
```
