import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# 1. Base de datos con palabras y conceptos reales
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

# 2. Cargar modelo multilingüe para generar embeddings
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# 3. Generar vectores (embeddings) para cada documento
embeddings = model.encode(documentos)
embeddings = np.array(embeddings).astype('float32')

# Normalizar vectores para calcular Similitud de Coseno
faiss.normalize_L2(embeddings)

# 4. Crear e inicializar el índice FAISS (IndexFlatIP = Inner Product)
dimension = embeddings.shape[1]  # 384 dimensiones en este modelo
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)

# 5. Definir la consulta (Query real en lenguaje natural)
query_text = "un transporte para volar por el aire"

# Generar y normalizar el vector de la consulta
query_embedding = model.encode([query_text]).astype('float32')
faiss.normalize_L2(query_embedding)

# 6. Buscar los 3 elementos más parecidos (Top K)
k = 3
similitudes, indices = index.search(query_embedding, k)

# 7. Mapear los índices devueltos por FAISS con las palabras originales
print(f"Búsqueda: '{query_text}'\n")
print("Resultados más similares:")
for posicion, idx in enumerate(indices[0]):
    score = similitudes[0][posicion]
    texto_original = documentos[idx]
    print(f"Top {posicion + 1}: [{score:.4f}] -> {texto_original} (ID: {idx})")