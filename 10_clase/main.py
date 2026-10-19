import hashlib
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import HumanMessage
from src.memory import saver_volatil,saver_persistente
from src.agentes import crear_orquestador
from src.config import proveedor, recortar
from src.schemas import (
    EstadoResponse,
    HealthResponse,
    Mensaje,
    QueryMemoryRequest,
    QueryRequest,
    QueryResponse,
)

ROLES = {"human": "usuario", "ai": "asistente"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Todo lo costoso se construye una sola vez al arrancar.
    with SqliteSaver.from_conn_string(DB_PATH) as saver_sqlite:
        app.state.grafos = {
            "volatil": crear_orquestador(saver_volatil),
            "persistente": crear_orquestador(saver_persistente),
        }
        yield
    # Al salir del with, la conexion SQLite se cierra sola.


app = FastAPI(title="API de agentes", version="1.0.0", lifespan=lifespan)


def generar_thread_id(email: str | None = None) -> str:
    """hex16: determinista si hay email (misma sesion siempre), aleatorio si no."""
    if email:
        return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
    return uuid.uuid4().hex[:16]


def _texto(contenido) -> str:
    """Gemini puede devolver el contenido como lista de bloques."""
    if isinstance(contenido, str):
        return contenido
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in contenido)


def _grafo(request: Request, memoria: Literal["volatil", "persistente"]):
    return request.app.state.grafos[memoria]


def _ejecutar(grafo, memoria: str, pregunta: str, thread_id: str) -> QueryResponse:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        resultado = grafo.invoke({"messages": [HumanMessage(content=pregunta)]}, config)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error del agente: {exc}") from exc
    return QueryResponse(
        thread_id=thread_id,
        respuesta=_texto(resultado["messages"][-1].content),
        memoria=memoria,
    )


# Endpoints sync (def): FastAPI los ejecuta en threadpool y no bloquean el event loop.
@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", llm_provider=proveedor())


@app.post("/query", response_model=QueryResponse)
def query(body: QueryRequest, request: Request):
    """Memoria volatil (RAM). Reutilizando el thread_id devuelto se mantiene el contexto."""
    thread_id = body.thread_id or generar_thread_id()
    return _ejecutar(_grafo(request, "volatil"), "volatil", body.pregunta, thread_id)


@app.post("/query-memory", response_model=QueryResponse)
def query_memory(body: QueryMemoryRequest, request: Request):
    """Memoria persistente (SQLite). Prioridad: thread_id > email > id nuevo."""
    thread_id = body.thread_id or generar_thread_id(body.email)
    return _ejecutar(_grafo(request, "persistente"), "persistente", body.pregunta, thread_id)


@app.get("/state/{thread_id}", response_model=EstadoResponse)
def state(
    thread_id: str,
    request: Request,
    memoria: Literal["volatil", "persistente"] = "persistente",
):
    """Historial del hilo, truncado a los ultimos 10 mensajes."""
    snapshot = _grafo(request, memoria).get_state({"configurable": {"thread_id": thread_id}})
    mensajes = snapshot.values.get("messages", [])
    if not mensajes:
        raise HTTPException(status_code=404, detail=f"Sin historial para thread_id {thread_id!r}")

    visibles = [
        Mensaje(rol=ROLES[m.type], contenido=_texto(m.content))
        for m in recortar(mensajes)
        if m.type in ROLES and m.content
    ]
    return EstadoResponse(thread_id=thread_id, total=len(visibles), mensajes=visibles)
