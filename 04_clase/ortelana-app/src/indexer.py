import json
import os
import faiss
import numpy as np
from google.genai import types
from src.config import client, MODELO_EMBEDDINGS, DIMENSION_EMBEDDINGS, INDEX_FILE_PATH, CATALOGO_JSON_PATH

def cargar_catalogo_json() -> list[dict]:
    with open(CATALOGO_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def obtener_embeddings_lote(textos: list[str]) -> np.ndarray:
    response = client.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=textos,
        config=types.EmbedContentConfig(output_dimensionality=DIMENSION_EMBEDDINGS)
    )
    
    vectores = [item.values for item in response.embeddings]
    
    return np.array(vectores, dtype=np.float32)

def inicializar_o_cargar_indice() -> tuple[faiss.IndexFlatL2, list[dict]]:
    catalogo = cargar_catalogo_json()
    textos = [item["descripcion_semantica"] for item in catalogo]

    if not os.path.exists(INDEX_FILE_PATH):
        print(f"Construyendo índice FAISS con {MODELO_EMBEDDINGS} ({DIMENSION_EMBEDDINGS} dim)...")
        matriz = obtener_embeddings_lote(textos)
        index = faiss.IndexFlatL2(DIMENSION_EMBEDDINGS)
        index.add(matriz)
        faiss.write_index(index, INDEX_FILE_PATH)
        print(f"Índice binario guardado en '{INDEX_FILE_PATH}'.")
    else:
        index = faiss.read_index(INDEX_FILE_PATH)
        print(f"Índice binario cargado desde '{INDEX_FILE_PATH}'.")

    return index, catalogo