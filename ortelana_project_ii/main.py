
import argparse
from src.indexer import inicializar_o_cargar_indices

def ejecutar_ingesta(): 
    index, catalogo = inicializar_o_cargar_indices()
    print( f"Success :)   -> {index.ntotal} productos ingestados")

def ejecutar_busqueda(query): ...

def ejecutar_rag(query): ...

def main():
    parser = argparse.ArgumentParser(
        description = "CLI para ortelana"
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
    
    # subcomandos a pedir

    if args.subcomando == "ingest":    
        ejecutar_ingesta()
        return
    
    if args.subcomando == "search":    
        ejecutar_search(args.query)
        return
    
    if args.subcomando == "rag":
        ejecutar_rag(args.query)
        return
    
    parser.print_help()
    
    

if __name__ == "__main__":
    main()
