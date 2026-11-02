# Cambio: ChromaDB local → MongoDB Atlas Vector Search

## Qué cambió

El índice vectorial dejó de ser una carpeta local (`data/chroma_db`, horneada en la imagen del
runtime) y pasó a una colección de MongoDB Atlas, el mismo cluster que ya guarda el catálogo y los
checkpoints de conversación.

| | Antes (ChromaDB) | Ahora (Atlas Vector Search) |
|---|---|---|
| Dónde vive el índice | `data/chroma_db/` (SQLite + binarios) | colección `knowledge_<provider>` en `ortelana-app-database` |
| Cómo llega al runtime | `COPY` dentro de la imagen | el runtime lo consulta por red |
| Actualizar el catálogo | `ingest` + rebuild de la imagen + redeploy | `ingest` + reinicio del servicio |
| Librería | `langchain-chroma` | `langchain-mongodb` (`MongoDBAtlasVectorSearch`) |
| Búsqueda léxica (BM25) | en memoria, desde Chroma | en memoria, desde la misma colección (sin cambios) |
| Fusión RRF + rerank Cohere | sin cambios | sin cambios |

## Por qué

1. **Un servicio de datos menos que operar.** Ya dependemos de MongoDB Atlas (catálogo y
   checkpoints). Chroma era un segundo almacén, con su propio ciclo de vida, solo para vectores.
2. **El runtime queda sin estado.** Con Chroma embebido, el índice era un archivo dentro del
   contenedor: Cloud Run no ofrece disco persistente, así que había que hornearlo en la imagen.
   Ahora la imagen no contiene datos y escala a N instancias sin copiar el índice.
3. **Reindexar sin redeploy.** Antes, cada cambio de catálogo exigía reconstruir y subir la imagen
   (cientos de MB). Ahora `ingest` escribe en Atlas y el runtime se reinicia.
4. **Imagen más liviana y cold start menor.** Se elimina `chromadb` y ~21 dependencias
   transitivas (`kubernetes`, `opentelemetry-*`, `pypika`, etc., según el `uv.lock`), y se
   quita la carpeta de datos de la imagen.
5. **Despliegue en un solo servicio.** Es coherente con la propuesta de monolito modular: el único
   servicio propio es `runtime`; los datos están en servicios administrados.

## Qué NO cambió (a propósito)

- **BM25 sigue en memoria.** Atlas Vector Search cubre la parte vectorial. Reemplazar BM25 por
  Atlas Search (léxico) sería otro rediseño. `build_retriever` lee los chunks de la colección al
  arrancar, sin el campo `embedding`.
- **Una colección por provider.** `knowledge_google` y `knowledge_cohere`, **ambos a 1024 dimensiones**
  (`gemini-embedding-001` con `embedding_dimensions = 1024`; Cohere `embed-multilingual-v3.0`, fija en 1024).
  Son espacios vectoriales distintos aunque compartan dimensión, por eso no se mezclan en una colección.
- Similitud **cosine**, igual que antes (`hnsw:space = cosine`).

## Archivos modificados (solo `12_clase/`)

- `config.toml`: la sección `[chroma]` se reemplaza por `[vectorstore]` (`database`, `collection`, `index`).
- `src/config.py`: `ChromaConfig` → `VectorStoreConfig`.
- `src/retrieval.py`: `open_vectorstore(settings, client)` usa `MongoDBAtlasVectorSearch`;
  `load_documents` lee los chunks para BM25; `build_retriever(settings, client)` recibe el cliente.
- `src/ingest.py`: crea el índice de Atlas si no existe (`ensure_vector_index`), vacía la colección
  (`delete_many`) y reinserta. Sigue siendo idempotente.
- `runtime/main.py`, `eval/main.py`: abren un `MongoClient` y lo pasan a `build_retriever`.
- `pyproject.toml` / `uv.lock`: `langchain-chroma` fuera; `langchain-mongodb` y `pymongo` en `core`.
- `runtime/Dockerfile`, `ingest/Dockerfile`, `eval/Dockerfile`, `.gitignore`, `env.sample` y los
  READMEs de cada etapa: ya no mencionan `data/chroma_db`.

## Requisitos en Atlas

- Cluster con Atlas Search habilitado (M0 gratuito incluido, hasta 3 índices de búsqueda).
- El usuario de `MONGODB_URI` necesita escribir en `ortelana-app-database` y crear índices de
  Atlas Search (rol `readWrite` más permiso de `createSearchIndexes`; `dbAdmin` lo cubre).
- La IP del runtime y del job `ingest` debe estar en el *Network Access* de Atlas.

Si el driver no puede crear el índice (por ejemplo, tier no compatible), crearlo a mano en
Atlas → Search → *Create Search Index* → *Atlas Vector Search* → JSON, sobre la colección
`knowledge_google` (usar `knowledge_cohere` para el provider Cohere; ambos son 1024):

```json
{
  "fields": [
    { "type": "vector", "path": "embedding", "numDimensions": 1024, "similarity": "cosine" }
  ]
}
```

El nombre del índice debe coincidir con `vectorstore.index` (`vector_index`).

## Ingesta local (paso a paso)

`ingest` es un job por lotes que se corre **desde tu máquina** (o CI), nunca como servicio. Lee
`data/documents/` y el catálogo de MongoDB, calcula embeddings y escribe en Atlas. Todos los
comandos se ejecutan desde `12_clase/`.

### 1. Preparar el `.env`

```bash
cp env.sample .env      # si todavía no existe
```

Completar en `12_clase/.env`:

| Variable | Para qué en `ingest` |
|---|---|
| `MONGODB_URI` | Leer el catálogo y escribir el índice en Atlas. **No hay variable nueva** para Atlas. |
| `GOOGLE_API_KEY` | Embeddings si `llm.provider = "google"` (valor por defecto). |
| `COHERE_API_KEY` | Obligatoria (la exige `Settings`); también embeddings si `llm.provider = "cohere"`. |
| `SUPABASE_KEY` | Obligatoria por `Settings`, aunque `ingest` no la usa. |

### 2. Preparar Atlas

- Tu IP actual figura en *Network Access*.
- El usuario de `MONGODB_URI` puede escribir en `ortelana-app-database` y crear índices de Atlas Search.
- Si ya corriste una versión anterior con otra dimensión (por ejemplo 768), borrar `vector_index`
  en Atlas → Search antes de seguir: `ingest` no actualiza un índice existente.

### 3. Correr la ingesta

```bash
uv sync --only-group ingest
uv run --only-group ingest python -m ingest.main
```

Qué hace, en orden:

1. Convierte `data/documents/*` a markdown y lo parte en chunks (`chunk_size=800`, `overlap=120`).
2. Lee el catálogo (`ortelana-app-database.catalogo`) y lo convierte en documentos `tipo="producto"`.
3. Crea el índice `vector_index` en `knowledge_<provider>` si no existe y espera hasta 120 s.
4. Vacía `knowledge_<provider>` y reinserta todo con sus embeddings.

Salida esperada:

```
INFO src.ingest: Indexed 120 chunks (35 products)
```

(las cifras dependen de tus datos).

Variante con Docker, equivalente:

```bash
docker build -f ingest/Dockerfile -t ortelana-ingest .
docker run --rm --env-file .env -v "$PWD/data:/app/data" ortelana-ingest
```

### 4. Verificar

```bash
# Atlas: el índice debe figurar como READY (Atlas → Search), y la colección tener documentos.
uv sync --only-group runtime
uv run --only-group runtime python -m runtime.main search "tela térmica"
```

Debe imprimir líneas `[score] <id> (<tipo>): <texto>`. Si el índice recién se creó y aún no está
`READY`, o los datos recién se cargaron, esperar unos segundos y repetir.

### 5. Cuándo repetirlo

Volver a correr el mismo comando (es idempotente) cuando:

- Cambió el catálogo en MongoDB o los archivos de `data/documents/`.
- Cambió `llm.provider`, el modelo de embeddings o `embedding_dimensions` (usa otra colección;
  si cambia la dimensión del mismo provider, borrar antes el índice).
- Cambió `chunk_size` o `chunk_overlap`.

Después **reiniciar `runtime`**, porque arma BM25 en memoria al arrancar. No hace falta reconstruir
la imagen.

### Problemas frecuentes

- **`Empty index: run ingest first`** al arrancar `runtime` o al buscar: la colección está vacía o
  apunta a otro provider. Revisar `llm.provider` y que `ingest` terminó sin error.
- **Timeout al crear el índice** (120 s): crearlo a mano en Atlas con el JSON de arriba, mismo
  nombre `vector_index`, y volver a correr `ingest`.
- **Búsqueda vacía justo después de `ingest`**: el índice indexa de forma asíncrona. Esperar y reintentar.
- **Error de autenticación o de red**: revisar `MONGODB_URI` y *Network Access*.
- **Falta una variable**: `Settings` exige `COHERE_API_KEY`, `MONGODB_URI` y `SUPABASE_KEY`.

## Cómo migrar desde Chroma

1. Seguir la sección *Ingesta local*: crea índice y carga los chunks en Atlas.
2. Verificar con `runtime.main search`.
3. Reconstruir la imagen del runtime una única vez (ya no copia `data/chroma_db`) y desplegar.
4. Opcional: borrar la carpeta local `data/chroma_db/`, que ya nada lee.

## Tradeoffs y riesgos

- **Latencia por consulta.** La búsqueda vectorial ahora cruza la red hacia Atlas, en lugar de
  leer disco local. Es un costo por request, no por arranque.
- **Consistencia eventual del índice.** Atlas indexa de forma asíncrona: tras `ingest`, los datos
  nuevos tardan segundos en ser buscables. Por eso `ingest` espera la creación del índice.
- **Ventana de reindexado.** `ingest` vacía la colección antes de reinsertar; durante ese lapso las
  búsquedas devuelven poco o nada. Aceptable para la demo. Si molesta, el siguiente paso es
  `upsert` por `content_hash` (sección 6 del README de la clase), que además evita re-embeber.
- **Acoplamiento a Atlas.** Se pierde la portabilidad de correr todo local sin cuenta. El código
  sigue aislado en `src/retrieval.py` e `src/ingest.py`, así que volver atrás es acotado.
- **Cuota.** Los índices de búsqueda cuentan contra el límite del tier (3 en M0): uno por provider.

## Estado de verificación

Verificado: `uv lock` resuelve, la configuración carga (`knowledge_google` / `vector_index`),
`load_documents` y `HybridRetriever.search` funcionan con una colección simulada. **No verificado**:
conexión real a Atlas, creación del índice y `ingest`/`runtime` de punta a punta; requieren
`MONGODB_URI` y claves reales.
