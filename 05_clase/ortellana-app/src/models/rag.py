from typing import List, Optional
from pydantic import BaseModel, Field
from ortelana.models.product import Product


class QueryRoute(BaseModel):
    intent: str = Field(
        description="Ruta de la consulta: 'PRODUCT', 'DOCUMENT' o 'HYBRID'"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Explicación de la clasificación"
    )


class SearchResult(BaseModel):
    product: Product
    distance: Optional[float] = None


class RAGResponse(BaseModel):
    query: str
    intent: str
    answer: str
    sources: List[Product] = Field(default_factory=list)
    provider: str