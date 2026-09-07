from enum import Enum
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class LineaTextil(str, Enum):
    INDUMENTARIA = "indumentaria"
    ALTA_COSTURA = "alta_costura"
    INDUSTRIAL = "industrial"
    TAPICERIA = "tapiceria"
    BLANCO = "blanco"
    DEPORTIVA = "deportiva"
    MARROQUINERIA = "marroquineria"


class ProductMetadata(BaseModel):
    linea_textil: LineaTextil
    sucursal_disponible: str
    en_stock: bool
    precio_metro: float = Field(gt=0, description="Precio por metro mayor a 0")
    tags_regionales: List[str] = Field(default_factory=list)


class Product(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(pattern=r"^TELA-\d{3}$", description="ID en formato TELA-XXX")
    nombre: str = Field(min_length=2)
    descripcion_semantica: str = Field(min_length=10)
    metadatos: ProductMetadata

    @property
    def vector_document(self) -> str:
        """Texto estructurado para indexación vectorial."""
        return f"{self.nombre}: {self.descripcion_semantica}"

    def to_mongo_dict(self) -> dict:
        """Exporta el modelo en un formato compatible con MongoDB."""
        return self.model_dump(mode="json")