# ChromaDB (*The Open-Source AI Application Database*)

> es una base de datos vectorial de código abierto diseñada para simplificar el desarrollo de aplicaciones basadas en Inteligencia Artificial y Modelos de Lenguaje (LLM). Permite almacenar, gestionar y buscar sobre vectores densos junto con sus documentos originales y metadatos asociados.

**Flujo de Trabajo (Basado en la Arquitectura)**

1. **Ingreso de Datos y Generación de Embeddings:** Recibe los textos, documentos o imágenes. A diferencia de FAISS, ChromaDB integra funciones automáticas de embeddings (usando modelos como `all-MiniLM-L6-v2`) o permite conectar modelos externos (OpenAI, Cohere, Sentence-Transformers).

2. **Almacenamiento e Indexación (Vector + Metadata Store):** Organiza los datos dentro de una **Colección** (*Collection*). Guarda simultáneamente el vector, el texto original, un ID único y sus metadatos en un almacén estructurado (basado en SQLite/disco o memoria).

3. **Procesamiento de la Consulta (Search Query):** Permite realizar consultas directamente enviando texto en lenguaje natural o vectores ya calculados. Se pueden aplicar filtros por metadatos (`where`) o filtros sobre el contenido del documento (`where_document`).

4. **Búsqueda e Indización (HNSW):** Ejecuta la búsqueda de los vecinos más cercanos aproximados (*ANN*) utilizando por defecto algoritmos basados en grafos como **HNSW** (*Hierarchical Navigable Small World*).

5. **Retorno de Resultados Enriquecidos:** No devuelve solo números o posiciones; retorna un objeto completo con los documentos más similares, sus metadatos, sus IDs y la distancia/puntuación de similitud.

**Especificaciones Técnicas de ChromaDB**

| Parámetro | Especificación |
| --- | --- |
| **Lenguaje Base** | Desarrollado en **Python** y **Rust** (core), con SDKs oficiales para Python y JavaScript/TypeScript. |
| **Modos de Despliegue** | **Efímero** (en RAM), **Persistente Local** (guardado en disco con SQLite) y **Cliente/Servidor** (Docker/Cloud). |
| **Almacenamiento Integrado** | Guarda vectores, documentos de texto crudo, metadatos en formato JSON e identificadores en una sola entidad. |
| **Métricas de Distancia** | Distancia Euclidiana al cuadrado (`l2`), Producto Interno (`ip`) y Coseno (`cosine`, configurada por defecto). |
| **Motor de Búsqueda Subyacente** | Implementa algoritmos **HNSW** para la indexación rápida en memoria/disco. |

**Principales Abstracciones y Conceptos**

* **Colecciones (Collections):** Equivalentes a las tablas en bases de datos relacionales o índices en bases no relacionales. Agrupan vectores, documentos y metadatos bajo una misma métrica de distancia.
* **Integración de Embedding Functions:** Abstracción que convierte automáticamente cualquier texto a vectores sin que el usuario tenga que manejar librerías adicionales manualmente.
* **Filtrado Híbrido (`where` & `where_document`):** Permite acotar el espacio de búsqueda vectorial aplicando reglas booleanas sobre los metadatos (ej. `donde categoria == 'transporte'`) o palabras clave en el texto.
* **Gestión CRUD Nativa:** A diferencia de las librerías puras de indexación, soporta operaciones de adición (`add`), actualización (`update`), inserción/actualización (`upsert`), obtención por ID (`get`) y eliminación (`delete`).

---

## Lo que siempre guarda como `Record` de este tipo de motor:

```sqlite3
{
	embedding vector
	document
	metadata
	IDs
}

```


## Algo de ejercitación simple para entender qué hace este motorcito (Recomendación en Colab)

Este ejercicio demuestra cómo crear una colección en ChromaDB, insertar documentos con metadatos y realizar una búsqueda semántica con filtrado opcional.

**Ejercicio Práctico en Python**

Para ejecutar este script solo necesitas instalar la dependencia ejecutando `uv add chromadb` o `pip install chromadb`.

```python
import chromadb

# 1. Base de datos con palabras, conceptos reales y metadatos
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

ids = [f"id_{i}" for i in range(len(documentos))]

# 2. Inicializar cliente efímero de ChromaDB (en memoria)
client = chromadb.Client()

# 3. Crear una colección especificando la métrica de Coseno
collection = client.create_collection(
    name="ejemplo_busqueda",
    metadata={"hnsw:space": "cosine"}
)

# 4. Cargar datos en la colección
# Chroma genera automáticamente los embeddings si no se proveen vectores expresos
collection.add(
    documents=documentos,
    metadatas=metadatos,
    ids=ids
)

# 5. Definir la consulta en lenguaje natural
query_text = "un transporte para volar por el aire"

# 6. Buscar los 3 elementos más parecidos (Top K)
k = 3
resultados = collection.query(
    query_texts=[query_text],
    n_results=k
    # where={"categoria": "transporte"} # Opcional: Filtro por metadatos
)

# 7. Mostrar resultados retornados por ChromaDB
print(f"Búsqueda: '{query_text}'\n")
print("Resultados más similares:")
for i in range(len(resultados["ids"][0])):
    doc_id = resultados["ids"][0][i]
    texto = resultados["documents"][0][i]
    distancia = resultados["distances"][0][i]
    meta = resultados["metadatas"][0][i]
    
    # En distancia de coseno de Chroma: similitud ≈ 1 - distancia
    score = 1 - distancia
    print(f"Top {i + 1}: [{score:.4f}] -> {texto} (ID: {doc_id}, Categoría: {meta['categoria']})")

```

---

### Claves de funcionamiento de este código

* **Gestión Integrada de Metadatos y Documentos:** No requiere mapear manualmente un array de Python o diccionario externo (`documentos[idx]`). Chroma mantiene sincronizados en el backend el ID, el vector, el documento original y sus metadatos.
* **Embeddings "Battery-Included":** No es obligatorio instanciar un modelo de `sentence-transformers` ni pasar matrices NumPy. Si pasas texto plano a `collection.add()` y `collection.query()`, Chroma se encarga de vectorizar los textos internamente.
* **Métrica de Distancia vs. Similitud:** Chroma retorna **distancias** (donde menor valor significa mayor cercanía). Para la métrica `cosine`, la conversión intuitiva a una puntuación de similitud entre $0.0$ y $1.0$ es $Score = 1 - \text{distancia}$.

---

**Uso de ChromaDB en Proyectos Masivos**

En escenarios de producción e integración con LLMs (sistemas RAG, asistentes virtuales con memoria o agentes autónomos):

* **Arquitectura Cliente/Servidor y Cloud:** Se despliega el servidor de ChromaDB en infraestructura aislada (mediante Docker o Chroma Cloud), permitiendo atender peticiones HTTP/gRPC de múltiples servicios de forma concurrente.
* **Filtrado por Permisos o Inquilinos (Multi-tenancy):** Mediante las cláusulas `where`, es posible realizar búsquedas restringidas por usuario, fecha o departamento antes de aplicar el cálculo semántico.
* **Ecosistema RAG Directo:** Es una de las bases de datos vectoriales estándar integradas de manera nativa en frameworks como **LangChain**, **LlamaIndex**, AutoGEN y CrewAI.

---

**Principales Problemas y Limitaciones**

* **Mayor Overhead que un Motor de Índices Puro (como FAISS):** Al incorporar persistencia en SQLite/disco, gestión de metadatos y abstracciones HTTP/Python, tiene mayor latencia y consumo extra de recursos que ejecutar un índice C++ directo en RAM/GPU.
* **Crecimiento de Memoria en Índices HNSW:** Los algoritmos HNSW no suelen liberar físicamente la memoria RAM cuando se borran registros individuales dentro de una colección activa (requiere recrear o re-indexar la colección para liberar espacio).
* **Límite en el Tamaño de Procesamiento Lote (*Batching*):** Al insertar volúmenes masivos de datos (decenas de miles de documentos), es obligatorio enviar la información fragmentada en lotes (*batches*) para evitar límites de tamaño en el buffer o la memoria.
* **Menor Grano de Control Algorítmico:** A diferencia de FAISS (donde puedes combinar cuantización `IndexPQ`, listas invertidas `IndexIVF` y aceleración GPU nativa manual), Chroma abstrae la configuración interna de la estructura del índice.
