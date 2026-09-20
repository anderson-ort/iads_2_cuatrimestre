### Explicación del Código

El script implementa una canalización RAG (*Retrieval-Augmented Generation*) completa con interfaz web en Streamlit, otro package de python que nos permite generar interfaces de manera rapida, organizada en cinco componentes clave:

#### 1. Proveedores de Embeddings (Patrón Strategy)

Define una interfaz genérica `IEmbeddingProvider` mediante la clase abstracta `ABC` para desacoplar el modelo de embeddings utilizado:

* **`HuggingFaceEmbeddingProvider`**: Ejecuta el modelo `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` de forma local en la CPU con vectores normalizados. 
* **`GeminiEmbeddingProvider`**: Llama a la API de Google usando `models/gemini-embedding-001`.
* **`CohereEmbeddingProvider`**: Llama a la API de Cohere utilizando el modelo: `embed-multilingual-light-v3.0` el problema con estos modelos es que no aceptan 786 dims.

#### 2. Servicio de Parseo (`AnyDocParserService`)

Toma archivos binarios (PDF, DOCX, XLSX, PPTX, etc.) y los procesa mediante la biblioteca `anydoc` para extraer texto en formato Markdown plano. Devuelve un objeto `Document` de LangChain preservando el nombre del archivo original en los metadatos.

#### 3. Chunker Híbrido (`HybridChunker`)

Divide los documentos procesados utilizando una estrategia en dos niveles:

1. **Nivel Semántico**: `MarkdownHeaderTextSplitter` divide el texto según las jerarquías de títulos Markdown (`#`, `##`, `###`, `####`), conservando la relación entre secciones.
2. **Nivel Estructural**: `RecursiveCharacterTextSplitter` toma las secciones resultantes y las sub-divide en trozos (*chunks*) con un límite de tamaño (`chunk_size`) y solapamiento (`chunk_overlap`) para no perder contexto entre divisiones.

#### 4. Gestor de Base de Datos Vectorial (`VectorStoreManager`)

Administra la conexión y persistencia en **ChromaDB** en la ruta local `./chroma_db`:

* **`add_documents`**: Inserta los chunks convertidos a vectores.
* **`get_stats`**: Consulta la base de datos mediante la API pública `vs.get()` para obtener el conteo total de trozos e identificar la lista de archivos únicos indexados.

#### 5. Interfaz de Usuario (`Streamlit`)

Organiza la interacción a través de una barra lateral de configuración y tres pestañas principales:

* **Barra Lateral**: Selección del proveedor de embeddings, claves API, ajuste de parámetros del chunker (tamaño y traslape) y categoría del documento.
* **Pestaña "Carga de Archivos"**: Sube documentos, genera archivos temporales, procesa con AnyDoc, fragmenta e indexa en ChromaDB.
* **Pestaña "Test de Retrieval"**: Permite realizar búsquedas por similitud vectorial (`similarity_search_with_score`), devolviendo los fragmentos más relevantes, su puntuación de distancia y metadatos.
* **Pestaña "Metadatos"**: Visualiza el total de chunks, archivos procesados y nombres de documentos en la base de datos.

---

### Esquema de Directorios Recomendado

```text
rag_anydoc_project/
│
├── app.py                     # Script principal de la aplicación Streamlit
├── requirements.txt           # Dependencias del proyecto
│
├── chroma_db/                 # Carpeta auto-generada donde ChromaDB guarda la BD
│   ├── chroma.sqlite3
│   └── <uuid-collections>/
│
├── temp/                      # Carpeta temporal (opcional si se maneja en disco)
└── data_ejemplo/              # Archivos de prueba (PDFs, DOCX, XLSX)

```

#### Archivo `requirements.txt` recomendado:

```text
streamlit
pandas
langchain-core
langchain-text-splitters
langchain-chroma
langchain-huggingface
langchain-google-genai
langchain-cohere
firecrawl-anydoc
sentence-transformers

```

---

### Ejemplo de Salida en Markdown (Visualización en la App)

Cuando el script procesa un archivo (por ejemplo, una política interna en PDF o Word) y se ejecuta una consulta en la pestaña **Test de Retrieval**, el sistema genera los trozos procesados y sus metadatos asociados.

#### 1. Salida generada por AnyDoc y el Chunker Híbrido

Dado un documento de origen, AnyDoc convierte el archivo a Markdown estructurado:

```markdown
# Política de Descuentos Comerciales

## 1. Promociones de Temporada
Los clientes con cuenta corporativa activa tienen acceso a un **15% de descuento** directo en compras superiores a $1,000 USD durante el primer trimestre.

### Excepciones
* No aplica para productos en liquidación.
* No acumulable con el descuento de membresía VIP.

```

#### 2. Resultado de búsqueda por similitud (Retrieval Test)

Al buscar `"¿Cuál es el descuento para clientes corporativos?"`, la interfaz muestra los resultados dentro del componente desplegable (`st.expander`):

**Resultado #1 | Distancia: 0.2145 | Archivo: Politica_Comercial_2026.pdf**

* **Contenido del Chunk (`doc.page_content`):**

```markdown
H1: Política de Descuentos Comerciales
H2: 1. Promociones de Temporada

Los clientes con cuenta corporativa activa tienen acceso a un 15% de descuento directo en compras superiores a $1,000 USD durante el primer trimestre.

```

* **Metadatos Extraídos (`doc.metadata` en formato JSON):**

```json
{
  "filename": "Politica_Comercial_2026.pdf",
  "parser": "firecrawl-anydoc",
  "category": "promociones",
  "H1": "Política de Descuentos Comerciales",
  "H2": "1. Promociones de Temporada"
}

```
