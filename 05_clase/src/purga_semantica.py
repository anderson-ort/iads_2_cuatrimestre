"""
Purga semantica de casi-duplicados - Clase 5, Bloque 1, Paso 3.
Usa embeddings de gemini-embedding-001 para detectar registros cuya
descripcion es semanticamente identica aunque el texto literal sea
distinto (ej: "Denim pesado de 12 oz" vs "Jean grueso de 12 onzas").
"""

import json
from itertools import combinations

import numpy as np
from dotenv import load_dotenv
from google import genai
from utils.embedding_function import EmbeddingFunctionGemini

load_dotenv()
client = genai.Client()

UMBRAL_CASI_DUPLICADO = 0.05  # distancia coseno; mientras mas cerca de 0, mas identicos


def distancia_coseno(a: np.ndarray, b: np.ndarray) -> float:
    similitud = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return 1 - similitud


def detectar_casi_duplicados(
    super_catalogo: list[dict], embedder: EmbeddingFunctionGemini
) -> list[tuple[str, str, float]]:
    """
    Compara cada par de registros del catalogo y devuelve los pares
    cuya distancia este por debajo del umbral, usando el embedder inyectado.
    """

    descripciones = [r["descripcion_semantica"] for r in super_catalogo]
    ids = [r["id"] for r in super_catalogo]
    embeddings = np.array(embedder(descripciones))

    # Emparejamos cada ID con su correspondiente embedding
    items = list(zip(ids, embeddings))
    pares_duplicados = []

    # combinations(items, 2) genera automáticamente pares únicos de (item_a, item_b)
    # y desempaquetamos directamente sus IDs y vectores (embeddings)

    for (id_a, emb_a), (id_b, emb_b) in combinations(items, 2):
        dist = distancia_coseno(emb_a, emb_b)

        if dist < UMBRAL_CASI_DUPLICADO:
            pares_duplicados.append((id_a, id_b, float(dist)))

    return pares_duplicados


def purgar_duplicados(
    super_catalogo: list[dict], pares_duplicados: list[tuple[str, str, float]]
) -> list[dict]:
    """
    De un par duplicado, conserva el primero (por orden de carga) y descarta el segundo.
    """
    ids_a_eliminar = {par[1] for par in pares_duplicados}
    return [r for r in super_catalogo if r["id"] not in ids_a_eliminar]


if __name__ == "__main__":
    with open("super_catalogo_ortelana.json", "r", encoding="utf-8") as f:
        super_catalogo = json.load(f)

    print(f"Catalogo antes de la purga: {len(super_catalogo)} registros.\n")

    # Instanciamos la clase configurando específicamente la tarea de similitud semántica
    embedder_similitud = EmbeddingFunctionGemini(task_type="SEMANTIC_SIMILARITY")

    # Inyectamos el embedder a la función de detección
    pares_duplicados = detectar_casi_duplicados(super_catalogo, embedder_similitud)

    if not pares_duplicados:
        print(
            "No se detectaron casi-duplicados con el umbral actual "
            f"({UMBRAL_CASI_DUPLICADO}). Si esperabas encontrar alguno, "
            "probá subir el umbral o revisá que tus descripciones sean "
            "realmente equivalentes en significado."
        )
    else:
        print("Pares casi-duplicados detectados:")
        for id_a, id_b, dist in pares_duplicados:
            print(f"  {id_a} <-> {id_b}  (distancia: {dist:.4f})")

    catalogo_limpio = purgar_duplicados(super_catalogo, pares_duplicados)

    with open("super_catalogo_ortelana_limpio.json", "w", encoding="utf-8") as f:
        json.dump(catalogo_limpio, f, ensure_ascii=False, indent=2)

    print(f"\nCatalogo despues de la purga: {len(catalogo_limpio)} registros.")
    print("Guardado en super_catalogo_ortelana_limpio.json")
