import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Literal

import httpx
from ddgs import DDGS
from .config import api 
from langchain_core.tools import tool

DATOS_PATH = Path(__file__).parent / "data" / "ortelana_db.json"

SECCION = Literal["productos", "clientes", "pedidos", "politicas"]

def _normalizar(texto: str) -> str:
    """Minusculas y sin tildes, para comparar 'Córdoba' con 'cordoba'."""
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").lower()


def _enriquecer_producto(p: dict) -> dict:
    precio_final = round(p["precio_metro_ars"] * (1 - p["descuento_pct"] / 100))
    return {**p, "precio_final_ars": precio_final, "stock_total_metros": sum(p["stock_metros"].values())}

def _error(*mensajes: str) -> str:
    return json.dumps({"error": "S", "errores": list(mensajes)}, ensure_ascii=False)

@tool
def buscar_datos_internos(seccion: SECCION, consulta: str = "") -> str:
    """Busca en la base interna de la empresa textil.

    Args:
        seccion: 'productos' (telas, precios, stock por sucursal), 'clientes' (credito,
            si es distribuidor, CUIT), 'pedidos' (estado, tracking, items) o
            'politicas' (devoluciones, envios, distribuidores).
        consulta: palabras clave como nombre o categoria de tela, nombre de cliente,
            CUIT, numero de pedido (PED-1001) o tema de politica. Dejala vacia para
            listar toda la seccion. No incluyas palabras como 'stock' o 'precio'.
    """
    datos = json.loads(DATOS_PATH.read_text(encoding="utf-8"))

    if seccion == "politicas":
        items = [{"tema": tema, "texto": texto} for tema, texto in datos["politicas"].items()]
    else:
        items = datos[seccion]

    palabras = [_normalizar(p) for p in re.findall(r"[\w-]+", consulta) if len(p) > 2]
    encontrados = [
        i for i in items
        if all(p in _normalizar(json.dumps(i, ensure_ascii=False)) for p in palabras)
    ]

    if not encontrados and seccion == "politicas":
        encontrados = items  # son solo 3, mejor devolverlas todas que nada
    if not encontrados:
        return f"Sin resultados en {seccion} para: {consulta!r}"

    if seccion == "productos":
        encontrados = [_enriquecer_producto(p) for p in encontrados]
    return json.dumps(encontrados, ensure_ascii=False)


@tool
def buscar_web(consulta: str) -> str:
    """Busca informacion publica y actual en la web con DuckDuckGo."""
    try:
        resultados = DDGS().text(consulta, max_results=3)
    except Exception as exc:
        return f"Error en la busqueda web: {exc}"
    if not resultados:
        return f"Sin resultados web para: {consulta!r}"
    return "\n\n".join(f"{r['title']}\n{r['href']}\n{r['body']}" for r in resultados)


@tool
def consultar_cuit(cuit: str) -> str:
    """Consulta datos fiscales (razon social, condicion impositiva, domicilio, actividades) de un CUIT de 11 digitos."""
    cuit = re.sub(r"\D", "", cuit)
    
    if len(cuit) != 11:
        _error("[CUIT ERROR] debe contener 11 digitos")

    try:
        table = os.getenv("SUPABASE_TABLE","cuit_simulado")
        client = api()
        resp = client.get(f"/{table}", params={"cuit": f"eq.{cuit}", "limit": 1})
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return _error(f"[FAIL]:{exc}")

    filas = resp.json()  # PostgREST devuelve una lista
    return json.dumps(filas[0], ensure_ascii=False) if filas else _error("[FAIL] CUIT no encontrado")

HERRAMIENTAS = [buscar_datos_internos, buscar_web, consultar_cuit]
TOOLS_POR_NOMBRE = {t.name: t for t in HERRAMIENTAS}
