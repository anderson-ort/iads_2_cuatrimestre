import numpy as np
import faiss
from google.genai import types
from src.config import client, MODELO_EMBEDDINGS, DIMENSION_EMBEDDINGS
from src.models import FiltrosConsultaSchema, TelaResultado

def buscar_y_filtrar(
    query_filtros: FiltrosConsultaSchema, 
    index: faiss.IndexFlatL2, 
    catalogo: list[dict], 
    top_k: int = 5
) -> list[TelaResultado]:
    
    res_vector = client.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=query_filtros.terminos_busqueda_semantica,
        config=types.EmbedContentConfig(output_dimensionality=DIMENSION_EMBEDDINGS)
    )
    vec_query = np.array([res_vector.embeddings[0].values], dtype=np.float32)
    
    distancias, indices = index.search(vec_query, top_k)
    resultados_filtrados: list[TelaResultado] = []

    for dist, idx in zip(distancias[0], indices[0]):
        item = catalogo[idx]
        meta = item["metadatos"]

        if query_filtros.linea_textil != "TODAS" and meta["linea_textil"] != query_filtros.linea_textil:
            continue
            
        if query_filtros.sucursal_preferida != "CUALQUIERA" and meta["sucursal_disponible"] != query_filtros.sucursal_preferida:
            continue

        if query_filtros.requiere_stock_inmediato and not meta["en_stock"]:
            continue

        resultados_filtrados.append(
            TelaResultado(
                id=item["id"],
                descripcion_semantica=item["descripcion_semantica"],
                linea_textil=meta["linea_textil"],
                sucursal=meta["sucursal_disponible"],
                en_stock=meta["en_stock"],
                distancia_l2=float(dist)
            )
        )

    return resultados_filtrados