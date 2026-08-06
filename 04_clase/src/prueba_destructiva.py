"""Prueba Destructiva en Caliente - Clase 4
Simula la caida del servidor: libera el indice de la memoria del
proceso actual y demuestra que el conocimiento sobrevive en el
archivo .index, sin importar que proveedor de embeddings se uso
para construirlo originalmente.
"""

import gc
import os

import faiss

INDEX_FILE = "ortelana_telas.index"


def simular_caida_y_recuperacion():
    if not os.path.exists(INDEX_FILE):
        print(
            f"ERROR: no existe '{INDEX_FILE}'. Corre primero "
            f"pipeline_vectorial_ortelana.py para generarlo."
        )
        return

    print("--- ESTADO ANTES DE LA CAIDA ---")
    index = faiss.read_index(INDEX_FILE)
    print(f"Indice cargado en memoria. Vectores disponibles: {index.ntotal}")

    print("\n--- SIMULANDO CAIDA DEL SERVIDOR (liberando memoria) ---")
    del index
    gc.collect()
    print("Variable 'index' eliminada de la RAM. El proceso 'olvido' el catalogo.")

    print("\n--- RECUPERACION POST-CAIDA (leyendo desde disco) ---")
    index_recuperado = faiss.read_index(INDEX_FILE)
    print(
        f"Indice recuperado desde '{INDEX_FILE}'. Vectores disponibles: "
        f"{index_recuperado.ntotal}"
    )
    print("Costo de la recuperacion: 0 llamadas a la API de Google GenAI.")


if __name__ == "__main__":
    simular_caida_y_recuperacion()
