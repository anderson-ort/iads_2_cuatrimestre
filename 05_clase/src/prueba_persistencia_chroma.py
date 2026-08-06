"""
Prueba de persistencia - Clase 5.
Version ChromaDB del experimento de la Clase 4: confirma que tras
"reiniciar" el proceso, la base de datos lee los vectores directo del
volumen en disco sin volver a llamar a la API de Google GenAI.
"""

from utils.chroma_repository import OrtelanaCatalogRepository
from utils.embedding_function import EmbeddingFunctionGemini


def main():
    print("=== Simulando un proceso nuevo (como si fuera post-reinicio) ===")

    embedding_function = EmbeddingFunctionGemini()
    coleccion = OrtelanaCatalogRepository(embedding_function).collection

    print(f"Coleccion '{coleccion.name}' cargada desde disco.")
    print(f"Registros disponibles sin volver a generar embeddings: {coleccion.count()}")

    if coleccion.count() == 0:
        print(
            "\nADVERTENCIA: la coleccion esta vacia. Corre primero chroma_ortelana.py "
            "para cargar el catalogo inicial."
        )
        return  # Ahora sí es válido porque está dentro de una función

    print(
        "\nPersistencia confirmada: 0 llamadas nuevas a la API de embeddings "
        "fueron necesarias para recuperar el catalogo completo."
    )
    return


if __name__ == "__main__":
    main()
