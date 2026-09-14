import chromadb
from pymongo import MongoClient


MONGO_URI = "mongodb+srv://andru-ort:Ander1234@ort-cluster-db.egfwx29.mongodb.net/ortelana-app-database?appName=ort-cluster-db"

mongo_client = MongoClient(MONGO_URI)
db_mongo = mongo_client["ortelana-app-database"]
coleccion_mongo = db_mongo["catalogo"]

# chroma_client = chromadb.PersistentClient(path="./ortelana_db")
chroma_client = chromadb.HttpClient(
    host = '127.0.0.1',
    port = '8000'
)

coleccion_chroma = chroma_client.get_or_create_collection(
    name="catalogo", metadata={"hnsw:space": "cosine"}
)



def migracion_mongo_chroma():
    ids = []
    documents = []
    metadatas = []
    documentos_mongo =  list(coleccion_mongo.find({}))
    
    for doc in documentos_mongo:
        # A) ID
        ids.append(doc["id"])

        # B) Texto semántico (Combinar nombre y descripción enriquece la búsqueda)
        texto_a_vectorizar = f"{doc['nombre']}: {doc['descripcion_semantica']}"
        
        documents.append(texto_a_vectorizar)

        # C) Metadatos (Aplanar tipos no primitivos)
        meta = doc["metadatos"].copy()
        if "tags_regionales" in meta and isinstance(
            meta["tags_regionales"], list
        ):
            meta["tags_regionales"] = ", ".join(meta["tags_regionales"])

        metadatas.append(meta)
        
    coleccion_chroma.add(
        ids=ids, documents=documents, metadatas=metadatas
        )


    print(f"ETL realizado {len(ids)} completados")
    
def generar_prompt_usuario(query: str , top_k:int = 4) -> str:
    resultados = coleccion_chroma.query(
        query_texts = query,
        n_results = top_k,
        where = {
            "en_stock": True
        }
    )


    metadatos_encontrados = resultados["metadatas"][0]
    documentos_encontrados = resultados["documents"][0]

    if not metadatos_encontrados:
        return "Lo siento, actualmente no tenemos telas disponibles que coincidan con tu búsqueda."

    # C. Construimos el "Contexto" formateado
    contexto_texto = ""
    for meta, doc in zip(metadatos_encontrados, documentos_encontrados):
#- Producto: {meta['nombre']}
        contexto_texto += f"""
  Detalle: {doc}
  Precio por metro: ${meta['precio_metro']}
  Sucursal: {meta['sucursal_disponible']}
  Línea: {meta['linea_textil']}
"""

    # D. Diseñamos el Prompt final para el LLM
    prompt_final = f"""
ROL: Eres un asistente virtual de ventas de una tienda de telas. 
Responde a la pregunta del cliente de manera amable, clara y concisa utilizando ÚNICAMENTE la siguiente información de inventario disponible.

[INVENTARIO ENCONTRADO]
{contexto_texto}

[PREGUNTA DEL CLIENTE]
{query}

[RESPUESTA]
"""

    return prompt_final
    


if __name__ == "__main__":
    #migracion_mongo_chroma()
    prompt_retrieval = generar_prompt_usuario("Tienen tela para buzos de egresado?")
    print(prompt_retrieval)

