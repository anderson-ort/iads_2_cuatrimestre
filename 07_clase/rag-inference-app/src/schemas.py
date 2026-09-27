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
