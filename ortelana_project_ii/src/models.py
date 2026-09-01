from pydantic import BaseModel, Field
from typing import Literal

class FiltrosConsultaSchema(BaseModel):
    """Esquema de extracción de filtros a partir del mensaje del cliente."""
    linea_textil: Literal["indumentaria", "alta_costura", "industrial", "tapiceria", "TODAS"] = Field(
        default="TODAS",
        description="Línea de productos a filtrar o TODAS si no especifica."
    )
    sucursal_preferida: Literal["central_buenos_aires", "filial_cordoba", "CUALQUIERA"] = Field(
        default="CUALQUIERA",
        description="Sucursal desde donde opera el cliente."
    )
    requiere_stock_inmediato: bool = Field(
        default=True,
        description="Si el cliente exige entrega inmediata."
    )
    terminos_busqueda_semantica: str = Field(
        description="La necesidad del cliente refinada para vectorización semántica."
    )

class TelaResultado(BaseModel):
    """Representación interna de un artículo recuperado y filtrado."""
    id: str
    descripcion_semantica: str
    linea_textil: str
    sucursal: str
    en_stock: bool
    distancia_l2: float

class RespuestaComercialSchema(BaseModel):
    """Estructura estricta para la respuesta comercial final enviada al cliente."""
    atendido: bool
    mensaje_comercial: str
    articulos_recomendados: list[str]
    advertencia_stock: str | None = None