"""Flujo didactico del Asistente RAG + Router, agnostico de la UI.

Extrae la logica paso a paso que originalmente vivia en la UI de Streamlit
para que tanto la app (app.py) como el CLI (cli.py) ejecuten exactamente la
misma secuencia: embedding de la consulta, router, y luego la rama que
corresponda (tool mock para stock/promociones, o busqueda por cercania ->
reranking -> generacion para consultas tecnicas).

El flujo no conoce Streamlit ni Rich: emite eventos y cada entrypoint los
traduce a su propia representacion. El evento Final transporta la respuesta en
texto plano (la misma que devolvia la UI para guardar en el historial)."""

import time
from dataclasses import dataclass
from typing import Iterator, List, Tuple, Union

from langchain_core.documents import Document

from schemas import (
    Intent,
    ConsultaProducto,
    RouterDecision,
    RagAnswer,
    StockAnswer,
    PromoAnswer,
)
from mock_tools import consultar_stock, consultar_promociones
from retrieval import biencoder_retrieve_with_scores, embed_query_for_display
from rag_chain import RAG_PROMPT, format_context


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
class Embedding:
    vector: List[float]
    elapsed: float


@dataclass
class EmbeddingError:
    mensaje: str


@dataclass
class Router:
    decision: RouterDecision


@dataclass
class Tool:
    tipo: str
    respuesta: Union[StockAnswer, PromoAnswer]


@dataclass
class Retrieval:
    candidatos: List[Tuple[Document, float]]
    k: int


@dataclass
class Rerank:
    top_docs: List[Document]
    posiciones: dict
    top_n: int


@dataclass
class Generation:
    contexto: str
    respuesta: RagAnswer


@dataclass
class Final:
    texto: str


Evento = Union[
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
]


def ejecutar_pipeline(
    pregunta: str,
    componentes: dict,
    k_candidatos: int,
    top_n_rerank: int,
) -> Iterator[Evento]:
    """Ejecuta el flujo completo emitiendo un evento por cada etapa.

    `componentes` es el dict que devuelve services.build_components(). La
    decision de mostrar u ocultar los pasos es del presenter, no del flujo:
    aca siempre se emiten todos los eventos."""

    vectorstore = componentes["vectorstore"]
    reranker = componentes["reranker"]
    router = componentes["router"]
    rag_structured_llm = componentes["rag_structured_llm"]

    # Paso 1: embedding de la consulta.
    yield StepStart(1, "Embedding de la consulta")
    t0 = time.time()
    try:
        vector = embed_query_for_display(vectorstore, pregunta)
        dt = time.time() - t0
        yield Embedding(vector, dt)
        yield StepEnd(
            1, f"Paso 1: Embedding de la consulta (dim {len(vector)})", "complete"
        )
    except Exception as e:
        yield EmbeddingError(str(e))
        yield StepEnd(1, "Paso 1: Embedding de la consulta (no disponible)", "error")

    # Paso 2: router.
    yield StepStart(2, "Router: clasificando la intencion")
    decision = router.invoke({"pregunta": pregunta})
    yield Router(decision)
    yield StepEnd(
        2, f"Paso 2: Router -> intencion = {decision.intent.value}", "complete"
    )

    # Ramas segun la intencion detectada.
    if decision.intent == Intent.STOCK:
        yield StepStart(3, "Consulta directa a mock_tools (stock)")
        resp = consultar_stock(ConsultaProducto(producto=decision.producto or pregunta))
        yield Tool("stock", resp)
        yield StepEnd(3, "Paso 3: Respuesta de stock obtenida", "complete")
        yield Final(resp.mensaje)
        return

    if decision.intent == Intent.PROMOCIONES:
        yield StepStart(3, "Consulta directa a mock_tools (promociones)")
        resp = consultar_promociones(ConsultaProducto(producto=decision.producto))
        yield Tool("promociones", resp)
        yield StepEnd(3, "Paso 3: Respuesta de promociones obtenida", "complete")
        yield Final(resp.mensaje + "\n\n" + "\n".join(f"- {p}" for p in resp.promociones))
        return

    if decision.intent == Intent.TECNICO:
        # Paso 3: busqueda por cercania (bi-encoder).
        candidatos_con_score = biencoder_retrieve_with_scores(
            vectorstore, pregunta, k=k_candidatos
        )
        yield StepStart(3, f"Busqueda por cercania (top {k_candidatos})")
        yield Retrieval(candidatos_con_score, k_candidatos)
        yield StepEnd(
            3,
            f"Paso 3: Busqueda por cercania -> {len(candidatos_con_score)} candidatos",
            "complete",
        )

        candidatos = [doc for doc, _ in candidatos_con_score]

        # Paso 4: reranking.
        top_docs = reranker.rerank(pregunta, candidatos, top_n=top_n_rerank)
        posicion_original = {id(doc): i for i, doc in enumerate(candidatos, start=1)}
        yield StepStart(4, f"Reranking (top {top_n_rerank} finales)")
        yield Rerank(top_docs, posicion_original, top_n_rerank)
        yield StepEnd(
            4, f"Paso 4: Reranking -> {len(top_docs)} documentos finales", "complete"
        )

        # Paso 5: generacion de la respuesta con el contexto reordenado.
        contexto = format_context(top_docs)
        yield StepStart(5, "Generacion de la respuesta (LLM + contexto)")
        mensajes = RAG_PROMPT.format_messages(pregunta=pregunta, contexto=contexto)
        resp = rag_structured_llm.invoke(mensajes)
        yield Generation(contexto, resp)
        yield StepEnd(5, "Paso 5: Respuesta generada", "complete")

        if resp.informacion_insuficiente:
            yield Final("No tengo informacion suficiente en la base para responder eso.")
            return
        respuesta = resp.respuesta + f"\n\n(confianza: {resp.confianza.value})"
        for f in resp.fuentes:
            respuesta += f"\n- fuente: {f.archivo} - {f.fragmento}"
        yield Final(respuesta)
        return

    yield Final("No pude clasificar la consulta. Reformule, por favor.")
