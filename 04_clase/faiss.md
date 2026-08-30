# FAISS (*Facebook AI Similarity Search*)
> es una librería de código abierto desarrollada por Meta optimizada para realizar búsquedas hiperrápidas de similitud y agrupamiento (*clustering*) de vectores densos.

**Flujo de Trabajo (Basado en la Imagen)**

1. **Generación de Embeddings:** Los datos originales (documentos, imágenes o textos) se convierten mediante un modelo de IA (*Embedding Generator*, como un *Transformer*) en **vectores densos** de longitud fija.
2. **Almacenamiento e Indexación (Vector Store):** FAISS recibe estos vectores y los organiza en memoria dentro de una estructura de datos optimizada llamada *Index*.
3. **Procesamiento de la Consulta (Search Query):** Cuando ingresas una consulta de búsqueda, esta pasa por el mismo modelo de embeddings para convertirse en un vector de consulta.
4. **Búsqueda (ENN o ANN):** FAISS evalúa la distancia entre el vector de consulta y el *Vector Store* ejecutando una búsqueda exacta (*ENN - Exact Nearest Neighbor*) o aproximada (*ANN - Approximate Nearest Neighbor*).
5. **Retorno de Resultados:** El índice devuelve los vectores o documentos con mayor grado de similitud.

**Especificaciones Técnicas de FAISS**

| Parámetro | Especificación |
| --- | --- |
| **Lenguaje Base** | Escrito en **C++** nativo para rendimiento extremo, con wrappers de alto nivel para **Python**. |
| **Tipos de Datos** | Estándar en vectores flotantes de 32 bits (`float32`), con soporte para `float16` y vectores binarios. |
| **Aceleración por Hardware** | Multihilo mediante OpenMP/BLAS en CPU y soporte acelerado por GPU mediante NVIDIA CUDA. |
| **Métricas de Distancia** | Distancia Euclidiana ($L_2$), Producto Interno ($\text{IP}$) y Coseno (con vectores normalizados). |
| **Escalabilidad** | Diseñado para operar sobre conjuntos desde miles hasta miles de millones de vectores en RAM/VRAM. |

**Principales Estrategias de Índices**

* **IndexFlat (Búsqueda Exacta / ENN):** Comparación brutal y exhaustiva contra el $100\%$ de la base de datos. Ofrece precisión perfecta con complejidad de tiempo $O(N)$.
* **IndexIVF (Inverted File Index):** Aplica *K-Means* para dividir el espacio vectorial en zonas (celdas Voronoi). En la búsqueda, solo examina las celdas más próximas a la consulta, aumentando enormemente la velocidad.
* **IndexPQ (Product Quantization):** Comprime los vectores de alta dimensión reduciendo de forma significativa el uso de memoria RAM a cambio de una pérdida ligera de precisión.
* **IndexHNSW (Hierarchical Navigable Small World):** Organiza los datos en grafos multicapa. Es uno de los algoritmos de búsqueda aproximada (ANN) más rápidos en memoria RAM, aunque consume más espacio de almacenamiento.

---

## Algo de ejercitacion simple para entender que es lo que hace ete motorcito (Recomendacion en Colab)

Este ejercicio básico demuestra cómo crear un índice en FAISS, cargar vectores aleatorios y realizar una búsqueda de los vectores más cercanos.

**Ejercicio Práctico en Python**

Para ejecutar este script solo necesitas instalar las dependencias con `uv add  faiss-cpu sentence-transformers huggingface_hub numpy`

```python
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
```


---

### Claves de funcionamiento de este código

* **Mapeo de Metadatos:** FAISS únicamente retorna posiciones numéricas (`[8, 2, 0]`). Para recuperar el texto real, se utiliza el array `documentos` como diccionario posicional usando `documentos[idx]`.
* **Similitud semántica real:** Aunque la consulta *"un transporte para volar por el aire"* no contiene literalmente la palabra *"Avión"*, el modelo de embeddings entiende el significado y FAISS encuentra *"Avión comercial de pasajeros"* en primer lugar.
* **Normalización $L_2$ + `IndexFlatIP`:** Al normalizar los vectores con `faiss.normalize_L2`, el cálculo del producto interno se convierte matemáticamente en la **Similitud de Coseno**. Esto produce puntuaciones de similitud entre $0.0$ (diferentes) y $1.0$ (idénticos).

---

**Uso de FAISS en Proyectos Masivos**

En producción con cientos de millones o miles de millones de vectores (sistemas RAG para LLMs, recomendadores en e-commerce o plataformas tipo Spotify):

* **Índices Compuestos (`IndexIVFPQ`):** No se usa búsqueda exacta. Se combina *Inverted File System* (IVF) para segmentar el espacio de búsqueda y *Product Quantization* (PQ) para comprimir el tamaño de los vectores en RAM (pueden reducir el consumo de memoria hasta en un $90\%$).
* **Aceleración por Hardware:** Los índices se migran a GPUs NVIDIA mediante `faiss.index_cpu_to_gpu`, permitiendo procesar miles de consultas por segundo en milisegundos.
* **Motor Subyacente:** Rara vez se usa FAISS de forma aislada en producción a gran escala; suele utilizarse como el motor algorítmico interno de bases de datos vectoriales distribuidas (como Milvus o Vespa).

---

**Principales Problemas y Limitaciones**

* **No es una base de datos completa:** FAISS es una **librería de indexación**, no un motor de base de datos. No gestiona metadatos (como nombres de usuarios, textos o URLs de imágenes) ni ofrece persistencia en disco de forma nativa e integrada.
* **Dificultad en operaciones CRUD:** Eliminar, actualizar o modificar un único vector dentro de índices comprimidos o en grafos (como `IndexHNSW`) es extremadamente costoso o ineficiente.
* **Alto consumo de Memoria (RAM/VRAM):** Los índices de FAISS deben residir en memoria volátil para mantener su velocidad extrema. A medida que la base de datos crece a miles de millones de elementos, el costo de infraestructura en RAM se eleva considerablemente.
* **Pérdida de exactitud (Compromiso ANN):** Para ganar velocidad en escenarios masivos, se debe sacrificar un porcentaje de exactitud ($Recall$), lo que significa que no siempre devolverá el vecino más cercano teórico.

---