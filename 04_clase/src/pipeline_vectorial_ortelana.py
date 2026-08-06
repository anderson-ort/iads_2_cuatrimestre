"""
Pipeline de busqueda semantica para el catalogo de Ortelana Textil.
Genera embeddings con Google GenAI (gemini-embedding-001), indexa con
FAISS IndexFlatL2, y persiste en disco para evitar reprocesar (y
repagar) los mismos vectores en cada ejecucion.

Cambio de proveedor respecto al PDF original: se reemplaza OpenAI
text-embedding-3-small por Google GenAI gemini-embedding-001, porque
es el proveedor que el proyecto va a usar de forma consistente.
"""

import os

import faiss
import numpy as np
from catalogo_telas import CATALOGO_ORTELANA
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()  # lee GEMINI_API_KEY del entorno automaticamente

MODELO_EMBEDDING = os.getenv("GEMINI_MODELO_EMBEDDING", "gemini-embedding-001")
DIMENSION = int(os.getenv("GEMINI_MODELO_EMBEDDING_DIMENSION", "768"))

# 1. Leemos la ruta desde el .env. Si no existe, usa el nombre por defecto en la raiz.
INDEX_FILE = os.getenv("FAISS_INDEX_PATH", "ortelana_telas.index")


def obtener_embeddings_documentos(textos: list[str]) -> list[list[float]]:
    """Embeddings para CONTENIDO QUE SE INDEXA (el catalogo)."""
    response = client.models.embed_content(
        model=MODELO_EMBEDDING,
        contents=textos,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=DIMENSION,
        ),
    )
    return [emb.values for emb in response.embeddings]


def obtener_embedding_consulta(texto: str) -> list[float]:
    """Embedding para una CONSULTA DE BUSQUEDA."""
    response = client.models.embed_content(
        model=MODELO_EMBEDDING,
        contents=[texto],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=DIMENSION,
        ),
    )
    return response.embeddings[0].values


def construir_o_cargar_indice() -> faiss.IndexFlatL2:
    """
    Garantia de persistencia: si el indice ya existe en la ruta indicada, lo carga.
    Si no existe, crea la estructura de carpetas necesaria, genera los vectores y lo guarda.
    """
    if not os.path.exists(INDEX_FILE):
        print(f"No se encontro indice en '{INDEX_FILE}'. Generando embeddings...")

        # 2. EXTRAER Y CREAR LA CARPETA SI NO EXISTE
        directorio_contenedor = os.path.dirname(INDEX_FILE)
        if directorio_contenedor and not os.path.exists(directorio_contenedor):
            print(f"Creando directorio contenedor: '{directorio_contenedor}'")
            # exist_ok=True evita errores si la carpeta se creo en un microsegundo en paralelo
            os.makedirs(directorio_contenedor, exist_ok=True)

        vectores = obtener_embeddings_documentos(CATALOGO_ORTELANA)
        vectores_np = np.array(vectores).astype("float32")

        index = faiss.IndexFlatL2(DIMENSION)
        index.add(vectores_np)

        # Ahora FAISS puede escribir seguro de que la ruta existe
        faiss.write_index(index, INDEX_FILE)
        print(f"Indice guardado exitosamente en '{INDEX_FILE}'.")
    else:
        print(f"Cargando indice persistente desde '{INDEX_FILE}'...")
        index = faiss.read_index(INDEX_FILE)

    return index


def buscar(consulta: str, index: faiss.IndexFlatL2, k: int = 3) -> list[dict]:
    """Busca las k telas mas cercanas semanticamente a la consulta."""
    vector_consulta = obtener_embedding_consulta(consulta)
    vector_consulta_np = np.array([vector_consulta]).astype("float32")

    distancias, indices = index.search(vector_consulta_np, k)

    resultados = []
    for dist, idx in zip(distancias[0], indices[0]):
        if idx >= 0:
            resultados.append(
                {
                    "id_catalogo": int(idx),
                    "contenido": CATALOGO_ORTELANA[idx],
                    "distancia_l2": float(dist),
                }
            )
    return resultados


if __name__ == "__main__":
    index = construir_o_cargar_indice()

    consultas_de_prueba = [
        "Necesito comprar una tela abrigada y gruesa para hacer camperas de invierno de alta gama",
    ]

    for consulta in consultas_de_prueba:
        print(f"\n{'-' * 60}")
        print(f"Consulta: '{consulta}'")
        resultados = buscar(consulta, index, k=1)
        for r in resultados:
            print(f"  [ID {r['id_catalogo']}] Distancia L2: {r['distancia_l2']:.4f}")
            print(f"    {r['contenido'][:100]}...")
