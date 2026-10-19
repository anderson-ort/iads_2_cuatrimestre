import httpx
import uuid
import hashlib
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException, Request, Query, APIRouter
from langchain_core.messages import HumanMessage

from src.config import api
from src.memory import saver_volatil,saver_persistente
from src.agent import crear_orquestador
from src.config import proveedor, recortar
from src.schemas import (
    EstadoResponse,
    HealthResponse,
    Mensaje,
    QueryMemoryRequest,
    QueryRequest,
    QueryResponse,
    CuitResponse
)

ROLES = {"human": "usuario", "ai": "asistente"}
TAGS = ["ortelana-health"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Todo lo costoso se construye una sola vez al arrancar.
    app.state.grafos = {
        "volatil": crear_orquestador(saver_volatil),
        "persistente": crear_orquestador(saver_persistente),
    }
    yield


app = FastAPI(
        title="API de agentes",
        version="1.0.0",
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
        lifespan=lifespan)


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
@app.get("/health", response_model=HealthResponse, tags=TAGS)
def health():
    return HealthResponse(status="ok", llm_provider=proveedor())


@app.get("/cuit-users", response_model=CuitResponse, tags=TAGS)
def dev_check_cuit(cuit: str = Query(..., pattern=r"^\d{11}$")):

    SELECT_FIELDS = "error,razon_social,condicion_impositiva,direccion,localidad,codigopostal,estado,provincia,actividad,errores"

    try:
        r = api().get(
                "/cuit_simulado",
                params={"cuit": f"eq.{cuit}", "select": SELECT_FIELDS, "limit": 1},
                )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error consultando Supabase: {e}")

    rows = r.json()

    if not rows:
        raise HTTPException(status_code=404, detail="CUIT no encontrado")
    return rows[0]

router = APIRouter(prefix="/api/v1", tags=["ortelana-api"])

@router.post("/query", response_model=QueryResponse)
def query(body: QueryRequest, request: Request):
    """Memoria volatil (RAM). Reutilizando el thread_id devuelto se mantiene el contexto."""
    thread_id = body.thread_id or generar_thread_id()
    return _ejecutar(_grafo(request, "volatil"), "volatil", body.pregunta, thread_id)


@router.post("/query-memory", response_model=QueryResponse)
def query_memory(body: QueryMemoryRequest, request: Request):
    """Memoria persistente (SQLite). Prioridad: thread_id > email > id nuevo."""
    thread_id = body.thread_id or generar_thread_id(body.email)
    return _ejecutar(_grafo(request, "persistente"), "persistente", body.pregunta, thread_id)


@router.get("/state", response_model=EstadoResponse)
def state(
    request: Request,
    thread_id: str | None = None,
    email: str | None = None,
    memoria: Literal["volatil", "persistente"] = "persistente",
):
    """Historial del hilo, truncado a los ultimos 10 mensajes."""
    if not thread_id and not email:
        raise HTTPException(status_code=422, detail="Indicar thread_id o email")

    clave = thread_id or generar_thread_id(email)
    snapshot = _grafo(request, memoria).get_state({"configurable": {"thread_id": clave}})
    mensajes = snapshot.values.get("messages", [])
    if not mensajes:
        raise HTTPException(status_code=404, detail=f"Sin historial para {clave!r}")

    visibles = [
        Mensaje(rol=ROLES[m.type], contenido=_texto(m.content))
        for m in recortar(mensajes)
        if m.type in ROLES and m.content
    ]
    return EstadoResponse(thread_id=clave, total=len(visibles), mensajes=visibles)

app.include_router(router)
