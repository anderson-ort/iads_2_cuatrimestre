# Explicación del Código

El script implementa una canalización RAG (*Retrieval-Augmented Generation*) completa con interfaz web en Streamlit, un paquete de Python que nos permite generar interfaces de manera rápida, organizada en cinco componentes clave:

```bash
uv add torchvision streamlit sentence-transformers langchain-text-splitters langchain-huggingface langchain-google-genai langchain-core langchain-cohere langchain-chroma firecrawl-anydoc
```

#### 1. Proveedores de Embeddings (Patrón Strategy)

Define una interfaz genérica `IEmbeddingProvider` mediante la clase abstracta `ABC` para desacoplar el modelo de embeddings utilizado:

* **`HuggingFaceEmbeddingProvider`**: Ejecuta el modelo `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` de forma local en la CPU con vectores normalizados.
* **`GeminiEmbeddingProvider`**: Llama a la API de Google usando `models/gemini-embedding-001`.
* **`CohereEmbeddingProvider`**: Llama a la API de Cohere utilizando el modelo `embed-multilingual-light-v3.0` (el problema con estos modelos es si no coinciden con la dimensión de 768 dims de la base).

#### 2. Servicio de Parseo (`AnyDocParserService`)

Toma archivos binarios (PDF, DOCX, XLSX, PPTX, etc.) y los procesa mediante la biblioteca `anydoc` para extraer texto en formato Markdown plano. Devuelve un objeto `Document` de LangChain preservando el nombre del archivo original en los metadatos.

#### 3. Chunker Híbrido (`HybridChunker`)

Divide los documentos procesados utilizando una estrategia en dos niveles:

1. **Nivel Semántico**: `MarkdownHeaderTextSplitter` divide el texto según las jerarquías de títulos Markdown (`#`, `##`, `###`, `####`), conservando la relación entre secciones.
2. **Nivel Estructural**: `RecursiveCharacterTextSplitter` toma las secciones resultantes y las subdivide en trozos (*chunks*) con un límite de tamaño (`chunk_size`) y solapamiento (`chunk_overlap`) para no perder contexto entre divisiones.

#### 4. Gestor de Base de Datos Vectorial (`VectorStoreManager`)

Administra la conexión y persistencia en **ChromaDB** en la ruta local:

* **`add_documents`**: Inserta los chunks convertidos a vectores.
* **`get_stats`**: Consulta la base de datos mediante la API pública `vs.get()` para obtener el conteo total de trozos e identificar la lista de archivos únicos indexados.

#### 5. Interfaz de Usuario (`Streamlit`)

Organiza la interacción a través de una barra lateral de configuración y tres pestañas principales:

* **Barra Lateral**: Selección del proveedor de embeddings, claves API, ajuste de parámetros del chunker (tamaño y traslape) y categoría del documento.
* **Pestaña "Carga de Archivos"**: Sube documentos, genera archivos temporales, procesa con AnyDoc, fragmenta e indexa en ChromaDB.
* **Pestaña "Test de Retrieval"**: Permite realizar búsquedas por similitud vectorial (`similarity_search_with_score`), devolviendo los fragmentos más relevantes, su puntuación de distancia y metadatos.
* **Pestaña "Metadatos"**: Visualiza el total de chunks, archivos procesados y nombres de documentos en la base de datos.
