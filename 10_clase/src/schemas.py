from typing import Literal
from pydantic import BaseModel, EmailStr, Field


class QueryRequest(BaseModel):
    pregunta: str = Field(min_length=1, examples=["Hay stock de Denim Azul?"])
    thread_id: str | None = Field(None, examples=["a1b2c3d4e5f60718"])


class QueryMemoryRequest(QueryRequest):
    email: EmailStr | None = Field(None, examples=["usuario@empresa.com"])


class QueryResponse(BaseModel):
    thread_id: str
    respuesta: str
    memoria: Literal["volatil", "persistente"]


class Mensaje(BaseModel):
    rol: Literal["usuario", "asistente"]
    contenido: str


class EstadoResponse(BaseModel):
    thread_id: str
    total: int
    mensajes: list[Mensaje]


class HealthResponse(BaseModel):
    status: str
    llm_provider: str

class Ruta(BaseModel):
    agente: Literal["fiscal", "datos", "web", "general"]




class Actividad(BaseModel):
    descripcion: str
    id: str
    nomenclador: str
    periodo: str


class CuitResponse(BaseModel):
    error: str = "N"
    razon_social: str
    condicion_impositiva: str
    direccion: str | None = None
    localidad: str | None = None
    codigopostal: str | None = None
    estado: str = "ACTIVO"
    provincia: str | None = None
    actividad: list[Actividad] = []
    errores: list[str] = [""]

