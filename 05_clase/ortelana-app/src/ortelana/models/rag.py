from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from ortelana.models.product import Product


class QueryRoute(BaseModel):
    intent: Literal["PRODUCT", "DOCUMENT", "HYBRID"] = Field(
        description="Clasificación de la consulta: PRODUCT (telas, precios, stock), DOCUMENT (envíos, pagos, trámites) o HYBRID (ambas)."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Breve justificación en una frase sobre la decisión tomada.",
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