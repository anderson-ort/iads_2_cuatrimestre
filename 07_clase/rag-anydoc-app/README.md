# Ingester RAG (Powered by AnyDoc)

Está pensada para quien recién arranca con RAG y quiere entender **qué es un ingester**, **cómo está armado por dentro** y **cómo se
levanta la aplicación**.

> Esta app es **solo la etapa de ingesta**. No genera respuestas con un LLM: su trabajo termina cuando los documentos quedaron convertidos en vectores dentro de una base de datos vectorial (ChromaDB). Esa base es lo que después consumiría un sistema RAG completo.

---

## 1. ¿Qué es un "ingester" y por qué existe?

Un modelo de lenguaje (LLM) no "conoce" tus archivos. Solo sabe lo que aprendió
durante su entrenamiento. Si querés que responda preguntas sobre **tus** PDFs,
docs, planillas, etc., primero tenés que darle una forma de **buscarlos**.

Para eso se construye un **RAG** (_Retrieval-Augmented Generation_): antes de
responder, el sistema **busca** los fragmentos relevantes de tus documentos y se
los pasa al LLM como contexto.

El **ingester** es la parte que prepara esos documentos. Convierte archivos
crudos en algo que se puede **buscar por significado**. El pipeline es:

```
Archivo (PDF, DOCX, XLSX, ...)
        │
        ▼
   1. PARSE      → convertir cualquier formato a texto (Markdown)
        │
        ▼
   2. CHUNK      → partir el texto en fragmentos manejables
        │
        ▼
   3. EMBED      → convertir cada fragmento en un vector numérico
        │
        ▼
   4. STORE      → guardar los vectores en una base de datos vectorial
```

Cada etapa se explica abajo, junto con el archivo que la implementa.

---

## 2. Mapa de archivos

| Archivo | Responsabilidad |
| --- | --- |
| `app.py` | Interfaz Streamlit (presenter). Muestra las 3 pestañas consumiendo los eventos del pipeline. |
| `cli.py` | CLI con Typer + Rich. Mismos eventos que `app.py`, renderizados en la terminal (`ingest`/`query`/`stats`). |
| `.env.sample` | Plantilla de variables de entorno. Copiala a `.env` y completá las API keys. |
| `config.toml` | Configuración central (modelos, tamaños de chunk, ruta de la DB). |
| `pyproject.toml` | Dependencias del proyecto. |
| `ingester/config.py` | Carga el `config.toml` y el `.env`; expone `get_api_key()`. |
| `ingester/pipeline.py` | Flujo agnóstico de UI: emite eventos de parse/chunk/embed/store, retrieval y stats. |
| `ingester/services.py` | Fábricas: resuelve el proveedor y arma el `VectorStoreManager`. |
| `ingester/parser.py` | **Etapa 1 – Parse:** AnyDoc transforma el archivo a Markdown. |
| `ingester/chunker.py` | **Etapa 2 – Chunk:** parte el texto en fragmentos. |
| `ingester/embeddings.py` | **Etapa 3 – Embed:** proveedores de embeddings (HuggingFace/Gemini/Cohere). |
| `ingester/vectorstore.py` | **Etapa 4 – Store:** guarda y consulta vectores en ChromaDB. |


---

## 3. Las partes que lo componen

### 3.1 Configuración — `config.toml` + `ingester/config.py`

Toda la configuración vive en **un solo archivo** (`config.toml`) para no tener
valores "mágicos" repartidos por el código.

```toml
[app]
title = "Ingestador RAG (Powered by AnyDoc)"
categories = ["promociones", "técnico", "general"]

[chunking]
default_size = 800
default_overlap = 120
min_size = 200
max_size = 2000

[gemini]
model_name = "gemini-embedding-001"

[cohere]
model_name = "embed-multilingual-v3.0"

[huggingface]
model_name = "sentence-transformers/all-MiniLM-L6-v2"

[vectorstore]
persist_dir = "../database/chroma_db"
collection_name = "anydoc_collection"
```

`ingester/config.py` solo se encarga de leerlo:

```python
def load_config(path: Path) -> dict:
    ...
    with open(path, "rb") as f:
        return tomllib.load(f)
```

- Si estás en **Python 3.11+** usa `tomllib` (viene incluido).
- Si no, cae a `tomli`.

Así, cambiar el modelo de embeddings o el tamaño de chunk **no requiere tocar
código**, solo el `.toml`. Este es un principio importante: *configuración
afuera, lógica adentro*.

---

### 3.2 Etapa 1 – Parse — `ingester/parser.py`

**Problema:** cada formato de archivo (PDF, Word, Excel, PowerPoint, EPUB, CSV…)
tiene su propia estructura interna. Necesitamos texto plano y uniforme.

**Solución:** [AnyDoc](https://github.com/firecrawl/anydoc) convierte **casi
cualquier formato a Markdown** con una sola llamada.

```python
class AnyDocParserService:
    def parse(self, file_path: str, filename: str) -> List[Document]:
        markdown_content = anydoc.to_markdown(file_path)
        return [
            Document(
                page_content=markdown_content,
                metadata={"filename": filename, "parser": "firecrawl-anydoc"},
            )
        ]
```

Puntos clave:

- **`Document`** es la unidad estándar de LangChain: un `page_content` (el texto)
  + `metadata` (información extra: de qué archivo vino, con qué parser, etc.).
  Los metadatos viajarán con el documento por todo el pipeline y son la base
  para **filtrar** resultados después.
- Se devuelve **una lista** de `Document` (acá uno solo) para mantener una
  interfaz uniforme.
- El `except` avisa que si el PDF es un **escaneo** (imagen sin texto), AnyDoc no
  puede extraer texto sin OCR y hay que procesarlo antes con un servicio de OCR.

> **¿Por qué Markdown y no texto plano?** Markdown conserva la estructura
> (títulos, listas, tablas). Esa estructura la va a aprovechar la próxima etapa
> para cortar el texto en lugares con sentido.

---

### 3.3 Etapa 2 – Chunk — `ingester/chunker.py`

**Problema:** el texto completo puede ser larguísimo. Un embedding de un
documento entero "diluye" el significado: no podés buscar una frase puntual si
todo está mezclado. Además, los modelos tienen un límite de tokens.

**Solución:** partir el texto en **chunks** (fragmentos) más chicos. Acá se usa
un enfoque **híbrido**: primero por estructura, después por tamaño.

```python
class HybridChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3"), ("####", "H4")]
        )
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
```

El `split_documents` aplica dos cortes en secuencia:

1. **`MarkdownHeaderTextSplitter`** → corta por **títulos** (`#`, `##`, …). Cada
   sección queda con su encabezado en los metadatos. Esto respeta la semántica
   del documento: no partimos una sección al medio sin necesidad.
2. **`RecursiveCharacterTextSplitter`** → si una sección sigue siendo más grande
   que `chunk_size`, la corta recursivamente probando separadores en orden:
   primero párrafos (`\n\n`), luego líneas (`\n`), luego oraciones (`. `),
   luego palabras (`" "`), y como último recurso carácter por carácter.

**Conceptos clave:**

- **`chunk_size` (ej. 800):** cuántos caracteres como máximo tiene cada chunk.
- **`chunk_overlap` (ej. 120):** cuántos caracteres se **repiten** entre un
  chunk y el siguiente. ¿Por qué repetir? Porque si una idea queda justo en el
  borde entre dos chunks y los cortamos limpio, la perdemos. El overlap da
  continuidad para que el contexto no se rompa.
- Los **metadatos del documento original se copian a cada chunk**
  (`split.metadata.update(doc.metadata)`), así cada fragmento sabe de qué
  archivo y categoría viene.

Si el texto no tiene estructura Markdown, el splitter devuelve vacío y se cae al
`else`, aplicando directamente el corte recursivo sobre el documento completo.

---

### 3.4 Etapa 3 – Embed — `ingester/embeddings.py`

**Problema:** una computadora no entiende texto, entiende números. Y para
"buscar por significado" (no por palabra exacta) necesitamos representar el
significado como números.

**Solución:** un **embedding** transforma cada chunk en un **vector** (una lista
de números, ej. 384 o 768 dimensiones). Chunks con significado parecido quedan
**cerca** en ese espacio vectorial. Así se puede buscar por similitud.

El archivo define una **interfaz** y tres implementaciones intercambiables
(patrón *Strategy*):

```python
class IEmbeddingProvider(ABC):
    @abstractmethod
    def get_embeddings(self) -> Embeddings:
        pass
```

| Provider | Clase | ¿Necesita API Key? | Notas |
| --- | --- | --- | --- |
| HuggingFace | `HuggingFaceEmbeddingProvider` | No | Corre **local** en CPU, multilingüe, gratis. Ideal para empezar. |
| Google Gemini | `GeminiEmbeddingProvider` | Sí | Servicio en la nube de Google. |
| Cohere | `CohereEmbeddingProvider` | Sí | Servicio en la nube, multilingüe. |

Cada implementación devuelve un objeto `Embeddings` de LangChain:

```python
class HuggingFaceEmbeddingProvider(IEmbeddingProvider):
    def get_embeddings(self) -> Embeddings:
        return HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
```

- **`normalize_embeddings=True`**: normaliza los vectores a longitud 1. Así la
  comparación por similitud coseno es más limpia y comparable.
- La interfaz `IEmbeddingProvider` permite que el resto del código **no sepa**
  qué proveedor concreto se está usando. Mañana agregás otro provider sin tocar
  nada más: ese es el punto de la abstracción.

> **Importante:** el **mismo** modelo de embeddings debe usarse para *indexar*
> (ingesta) y para *buscar* (retrieval). Si los vectores se generan con modelos
> distintos, las distancias no son comparables.

---

### 3.5 Etapa 4 – Store — `ingester/vectorstore.py`

**Problema:** guardar vectores en un `.json` o en memoria no escala ni permite
búsquedas rápidas por similitud.

**Solución:** una **base de datos vectorial**. Acá se usa **ChromaDB** vía
`langchain-chroma`.

```python
class VectorStoreManager:
    def __init__(self, embedding_provider, persist_dir, collection_name):
        self.embeddings = embedding_provider.get_embeddings()
        self.persist_dir = persist_dir
        self.collection_name = collection_name

    def get_vectorstore(self) -> Chroma:
        return Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
        )

    def add_documents(self, documents: List[Document]) -> int:
        vs = self.get_vectorstore()
        vs.add_documents(documents)
        return len(documents)
```

- **`persist_directory`**: dónde se guarda la base **en disco**. Al persistir,
  los datos sobreviven entre ejecuciones (no se pierden al cerrar la app).
- **`collection_name`**: es como una "tabla" dentro de la base. Podés tener
  varias colecciones separadas.
- **`add_documents`**: Chroma se encarga de llamar al `embedding_function` para
  vectorizar cada chunk y guardarlo. Fijate que el manager **no** vectoriza a
  mano: delega en Chroma + el provider configurado.

También expone `get_stats()`, que cuenta cuántos chunks hay indexados y cuántos
archivos únicos, leyendo los metadatos de la colección.

---

### 3.6 Las interfaces — `app.py` (Streamlit) y `cli.py` (Typer + Rich)

La orquestación vive en `ingester/pipeline.py`, que **no conoce ninguna UI**:
ejecuta el flujo y **emite eventos** (`StepStart`, `FileStart`, `Parsed`,
`Chunked`, `Stored`, `FileError`, `Retrieval`, `Stats`, `Final`). Cada interfaz
los traduce a su propia representación:

- `app.py` → widgets de Streamlit (`st.status`, tablas, métricas).
- `cli.py` → terminal con Rich (`console.rule`, `Panel`, `Table`).

Este es el punto de la separación: el **flujo es uno solo** y las UIs son
intercambiables. `ingester/services.py` arma las piezas (proveedor +
ChromaDB) para que ambas interfaces las compartan.

Además, `ingester/config.py` carga el `.env` con `python-dotenv`, así que las
API keys no se escriben en el código ni en la UI: `get_api_key("gemini")` lee
`GEMINI_API_KEY` y `get_api_key("cohere")` lee `COHERE_API_KEY`.

`app.py` se organiza así:

- **Barra lateral (sidebar):**
  1. **Inyección de Embeddings** → elegís el modelo (HuggingFace / Gemini /
     Cohere). Si el provider requiere API key, aparece un campo de contraseña
     **prellenado desde el `.env`** (y editable desde la UI).
  2. **Opciones de Chunking** → sliders de `chunk_size` y `chunk_overlap`.
  3. **Categoría de los documentos** → etiqueta que se guarda en los metadatos.

- **Tres pestañas:**
  1. **Carga de Archivos** → subís uno o varios archivos y se ejecuta el
     pipeline completo (parse → chunk → embed → store).
  2. **Test de Retrieval** → escribís una consulta y ves los chunks más
     parecidos con su distancia. Sirve para **verificar que la ingesta quedó
     bien**: si buscás algo y no aparecen los chunks esperados, algo falló.
  3. **Metadatos** → estadísticas de la base (total de chunks, archivos únicos).

Dos detalles técnicos importantes:

- **`@st.cache_resource`**: Streamlit re-ejecuta `app.py` entero en cada
  interacción. Cargar un modelo de embeddings o reconectar a Chroma es caro, así
  que se **cachean** para no repetirlo. Por eso `get_vector_manager(...)` está
  decorado: es un objeto "pesado y de larga vida" que queremos instanciar una
  sola vez.
- **`tempfile` + `os.remove`**: el `file_uploader` de Streamlit entrega los
  archivos en memoria, pero AnyDoc necesita una **ruta en disco**. Por eso cada
  archivo se escribe a un temporal, se pasa al pipeline como `(ruta, nombre)` y
  se borra en el `finally` (siempre, incluso si falla).

El botón "Procesar e Ingestar" no implementa nada: delega en `ingester/pipeline.py`
y va mostrando los eventos que este emite. El flujo interno es:

```python
# dentro de ejecutar_ingesta(...) en ingester/pipeline.py
parsed_docs = parser_service.parse(path, filename)   # 1. PARSE   -> Evento Parsed
chunks = chunker.split_documents(parsed_docs)        # 2. CHUNK   -> Evento Chunked
stored = vector_manager.add_documents(chunks)        # 3. EMBED + 4. STORE -> Evento Stored
```

Cada etapa emite su evento (`StepStart`/`StepEnd` + detalle), y el presenter de
turno decide cómo mostrarlo.

---

## 4. Flujo end-to-end

Ejemplo: subís `manual.pdf` con la categoría `técnico`.

```
manual.pdf
   │  (1) parser.py  → anydoc.to_markdown()
   ▼
Document(page_content="# Manual\n...", metadata={filename: "manual.pdf"})
   │  el pipeline agrega category = "técnico"
   ▼
   │  (2) chunker.py → MarkdownHeader + Recursive
   ▼
[chunk1, chunk2, chunk3, ...]   ← cada uno con filename + category en metadata
   │  (3) Chroma llama al embedding_function
   ▼
[{vector, texto, metadata}, ...]
   │  (4) vectorstore.py → Chroma(persist_directory=...)
   ▼
ChromaDB en disco  →  listo para retrieval
```

---

## 5. Cómo se arranca

### Requisitos

- **Python 3.13** (ver `.python-version`).
- **uv** (gestor de entornos/dependencias del proyecto).
- Para HuggingFace (local) no hace falta API key. Para Gemini/Cohere sí.

### Configurar las API keys

Copiá la plantilla y completá las claves reales:

```bash
cp .env.sample .env
# editar .env y pegar GEMINI_API_KEY / COHERE_API_KEY
```

El `.env` no se versiona (está en el `.gitignore` raíz). `ingester/config.py`
lo carga automáticamente con `python-dotenv`.

### Instalar dependencias

```bash
uv sync
```

### Opción A — UI web (Streamlit)

```bash
uv run streamlit run app.py
```

Streamlit levanta un servidor local y abre el navegador (por defecto en
`http://localhost:8501`).

### Opción B — CLI (Typer + Rich)

```bash
uv run python cli.py --help
uv run python cli.py ingest documentos/manual.pdf --category tecnico
uv run python cli.py query "como se aplica el descuento" --k 3
uv run python cli.py stats
```

Ambas interfaces ejecutan el **mismo pipeline** (`ingester/pipeline.py`); el CLI
solo cambia cómo muestra los eventos. Si no querés usar `.env`, podés pasar la
key por flag (`--gemini-api-key`, `--cohere-api-key`).

### Sobre la ruta de la base

En `config.toml`:

```toml
[vectorstore]
persist_dir = "../database/chroma_db"
```

Es una ruta **relativa al directorio desde donde ejecutás el comando**, no al
`config.toml`. Si corrés `uv run streamlit run app.py` (o `uv run python cli.py`)
desde la raíz del proyecto, la base se crea en `../database/chroma_db` (es decir,
un nivel arriba). Si la corrés desde otro lugar, la base se crea **en otro lado**.
Tenelo en cuenta cuando no encuentres los datos que ingestaste.

---

## 6. Conceptos clave para llevarte

- **Embedding:** representación numérica del significado de un texto. Chunks
  parecidos → vectores cercanos.
- **Chunk:** fragmento de texto. Unidad de trabajo del RAG.
- **Overlap:** solapamiento entre chunks, para no perder ideas en los bordes.
- **Metadata:** datos extra que viajan con cada chunk (archivo, categoría).
  Habilitan el filtrado.
- **Vector store:** base de datos que busca por similitud entre vectores.
- **Distancia:** qué tan lejos están dos vectores. Distancia **menor** =
  **más** parecido. Por eso en la pestaña de retrieval se ordena de menor a mayor.
- **Estrategia/abstracción (`IEmbeddingProvider`):** el resto del código depende
  de la interfaz, no del proveedor concreto. Cambiar de modelo no rompe nada.

---

## 7. Resumen en una frase

El ingester toma documentos de cualquier formato, los convierte a texto
(**parse**), los corta en fragmentos (**chunk**), los transforma en vectores
(**embed**) y los guarda en ChromaDB (**store**). Todo eso vive en
`ingester/pipeline.py` y emite eventos, que consumen dos interfaces
intercambiables: la web de Streamlit (`app.py`) y el CLI de Typer + Rich
(`cli.py`) — dejando lista la base vectorial que un RAG completo usaría para
recuperar contexto.
