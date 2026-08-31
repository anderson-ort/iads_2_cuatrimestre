import argparse
import os
from src.config import INDEX_FILE_PATH
from src.indexer import inicializar_o_cargar_indice
from src.retriever import buscar_y_filtrar
from src.rag_chain import extraer_intencion_y_filtros, generar_respuesta_final
from src.models import TelaResultado

def ejecutar_ingesta():
    """Etapa 1: Ingesta del catálogo y generación del índice FAISS."""
    print("\n--- ETAPA 1: INGESTA Y VECTORIZACIÓN ---")
    if os.path.exists(INDEX_FILE_PATH):
        os.remove(INDEX_FILE_PATH)
        print(f"Índice previo '{INDEX_FILE_PATH}' eliminado para forzar re-ingesta.")
    
    indice, catalogo = inicializar_o_cargar_indice()
    print(f"✓ Ingesta finalizada con éxito. {indice.ntotal} productos indexados.")

def ejecutar_busqueda(mensaje_cliente: str) -> tuple[list[TelaResultado], str]:
    """Etapa 2: Extracción de intención, vectorización y filtrado semántico."""
    print("\n--- ETAPA 2: PARSEO Y BÚSQUEDA SEMÁNTICA ---")
    print(f"Entrada cliente: '{mensaje_cliente}'")
    
    # 1. Cargar el índice binario previo
    indice, catalogo = inicializar_o_cargar_indice()

    # 2. Extraer intención y filtros duros con LLM
    filtros = extraer_intencion_y_filtros(mensaje_cliente)
    print("\n[PASO 1] Filtros e Intención Extraída:")
    print(f" - Línea textil: {filtros.linea_textil}")
    print(f" - Sucursal preferida: {filtros.sucursal_preferida}")
    print(f" - Requiere stock: {filtros.requiere_stock_inmediato}")
    print(f" - Términos semánticos: '{filtros.terminos_busqueda_semantica}'")

    # 3. Búsqueda vectorial + filtrado por metadatos
    articulos = buscar_y_filtrar(filtros, indice, catalogo, top_k=5)
    print(f"\n[PASO 2] Artículos recuperados ({len(articulos)}):")
    for a in articulos:
        print(f" - [{a.id}] (Distancia L2: {a.distancia_l2:.4f})")
        print(f"   Descripción: {a.descripcion_semantica}")
        print(f"   Ubicación: {a.sucursal} | Stock: {a.en_stock}\n")

    return articulos, mensaje_cliente

def ejecutar_rag(mensaje_cliente: str):
    """Etapa 3: Generación de respuesta comercial basada en contexto (RAG)."""
    # Ejecuta primero la etapa de búsqueda
    articulos, mensaje = ejecutar_busqueda(mensaje_cliente)
    
    print("\n--- ETAPA 3: GENERACIÓN RAG ---")
    respuesta_final = generar_respuesta_final(mensaje, articulos)
    
    print("\n[PASO 3] Respuesta Comercial Final:")
    print(f" Mensaje: {respuesta_final.mensaje_comercial}")
    print(f" Artículos recomendados: {respuesta_final.articulos_recomendados}")
    if respuesta_final.advertencia_stock:
        print(f" Advertencia: {respuesta_final.advertencia_stock}")

def main():
    parser = argparse.ArgumentParser(
        description="CLI para la arquitectura RAG de Ortelana Textil"
    )
    subparsers = parser.add_subparsers(dest="subcomando", help="Comando a ejecutar")

    # Comando 1: ingest
    subparsers.add_parser(
        "ingest", 
        help="Procesar catalogo.json y reconstruir el índice FAISS binario"
    )

    # Comando 2: search
    parser_search = subparsers.add_parser(
        "search", 
        help="Extraer filtros y buscar productos semánticamente en FAISS"
    )
    parser_search.add_argument("query", type=str, help="Consulta del cliente")

    # Comando 3: rag
    parser_rag = subparsers.add_parser(
        "rag", 
        help="Ejecutar la pipeline completa RAG (Búsqueda + Respuesta del LLM)"
    )
    parser_rag.add_argument("query", type=str, help="Consulta del cliente")

    args = parser.parse_args()

    if args.subcomando == "ingest":
        ejecutar_ingesta()
    elif args.subcomando == "search":
        ejecutar_busqueda(args.query)
    elif args.subcomando == "rag":
        ejecutar_rag(args.query)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()