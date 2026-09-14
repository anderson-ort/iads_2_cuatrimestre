import chromadb
from pprint import pprint



client = chromadb.PersistentClient(path="./granja_zenon")


    
collection = client.get_or_create_collection(
    name = "granja_default",
    metadata = {
        "hnsw:space": "cosine"
    }
)
    



def init_db():

    documentos = [
        "Perro doméstico que ladra",
        "Gato felino que maúlla",
        "Automóvil para transporte terrestre",
        "Bicicleta de dos ruedas",
        "Computadora portátil para programar",
        "Teléfono inteligente móvil",
        "Manzana roja y jugosa",
        "Pizza de queso y pepperoni",
        "Avión comercial de pasajeros",
        "Guitarra acústica de madera"
    ]
    
    metadatos = [
        {"categoria": "animal"},
        {"categoria": "animal"},
        {"categoria": "transporte"},
        {"categoria": "transporte"},
        {"categoria": "tecnologia"},
        {"categoria": "tecnologia"},
        {"categoria": "comida"},
        {"categoria": "comida"},
        {"categoria": "transporte"},
        {"categoria": "musica"}
    ]
    
    
    
    ids = [ f"id_{i}" for i in range(len(documentos))]
    
    
    
    
    
    
    collection.add(
        documents = documentos,
        metadatas = metadatos,
        ids=ids
    )
    
    

def query_search(query:str, top_k:int = 3):
    results = collection.query(
        query_texts = [query],
        n_results = top_k,
        include = ["embeddings","documents"]
    )     
    
    pprint(query)
    print("*" * 60)
    pprint(results)
    return     

if __name__ == '__main__':


    query_search("un transporte para volvar por el aire")


