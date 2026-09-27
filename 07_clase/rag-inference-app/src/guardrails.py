
def guardrail_check(texto: str) -> bool:
    """Punto de extension para guardrails (ej. NeMo Guardrails, Llama Guard,
    o reglas propias de negocio). Por ahora solo valida que no este vacia."""
    return bool(texto and texto.strip())
