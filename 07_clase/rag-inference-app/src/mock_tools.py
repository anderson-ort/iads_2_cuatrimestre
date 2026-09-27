"""Herramientas mock para las ramas 'stock' y 'promociones' del router.

STUB: hoy devuelven datos hardcodeados para poder ejecutar el flujo completo sin
una base de datos. La firma de cada funcion (ConsultaProducto -> *Answer) es el
punto de enchufe del tool real: cuando exista la base, se reemplaza el cuerpo por
la consulta correspondiente sin tocar pipeline.py, el router ni los esquemas.
"""

from schemas import ConsultaProducto, StockAnswer, PromoAnswer

# TODO: reemplazar por consultas reales a la DB/API de stock y promociones.
MOCK_STOCK = {"notebook": 12, "monitor": 0, "teclado": 34}
MOCK_PROMOS = {
    "notebook": ["15% off con tarjeta X", "3 cuotas sin interes"],
    "monitor": ["2x1 en accesorios"],
}


def consultar_stock(consulta: ConsultaProducto) -> StockAnswer:
    p = consulta.normalizado()
    cantidad = MOCK_STOCK.get(p) if p else None
    if cantidad is None:
        return StockAnswer(
            producto=consulta.producto or "desconocido",
            disponible=False,
            mensaje="Producto no encontrado en el catalogo.",
        )
    return StockAnswer(
        producto=consulta.producto,
        disponible=cantidad > 0,
        cantidad=cantidad,
        mensaje=f"Quedan {cantidad} unidades." if cantidad > 0 else "Sin stock.",
    )


def consultar_promociones(consulta: ConsultaProducto) -> PromoAnswer:
    p = consulta.normalizado()
    if p:
        promos = MOCK_PROMOS.get(p, [])
        msg = f"{len(promos)} promocion(es) encontradas." if promos else "Sin promociones para ese producto."
        return PromoAnswer(producto=consulta.producto, promociones=promos, mensaje=msg)
    todas = [f"{k}: {', '.join(v)}" for k, v in MOCK_PROMOS.items()]
    return PromoAnswer(producto=None, promociones=todas, mensaje="Promociones generales.")
