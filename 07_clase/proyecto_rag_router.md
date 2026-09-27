# Ingestador RAG + Router (proyecto completo, con UI paso a paso)

## Estructura del proyecto

```
rag-inference-app/
├── app.py                # UI Streamlit (presenter del flujo compartido)
├── cli.py                # CLI Typer + Rich (presenter del flujo compartido)
├── config.toml           # única fuente de verdad de parámetros
├── pyproject.toml
└── src/
    ├── config.py
    ├── schemas.py
    ├── prompts.py
    ├── retrieval.py
    ├── router_chain.py
    ├── rag_chain.py
    ├── pipeline.py       # flujo paso a paso compartido (emite eventos)
    ├── mock_tools.py
    ├── guardrails.py
    └── services.py

```

`rag-inference-app/` **no copia** el paquete `ingester` del proyecto `rag-anydoc-app/`: lo importa directamente. De ahí saca dos piezas ya probadas y mantenidas en un solo lugar:

* `ingester/vectorstore.py` → `VectorStoreManager` (conexión + persistencia en ChromaDB).
* `ingester/embeddings.py` → `IEmbeddingProvider` y sus implementaciones (`HuggingFaceEmbeddingProvider`, `GeminiEmbeddingProvider`, `CohereEmbeddingProvider`).

De esta forma el ingestador (la app Streamlit de `rag-anydoc-app/app.py`) y el asistente de preguntas (`rag-inference-app/`) comparten **la misma configuración de vectorstore** (`config.toml`: `persist_dir` + `collection_name`) y no hay dos formas distintas de abrir Chroma.

## Documentación

## Refactor: Pydantic end-to-end y prompts centralizados

### Qué cambió

1. **`prompts.py` (nuevo)**: todos los prompts vivían hardcodeados dentro de `router_chain.py` y `rag_chain.py`. Ahora están en un solo lugar.
2. **`ConsultaProducto` (nuevo, en `schemas.py`)**: `consultar_stock` y `consultar_promociones` recibían un `str` crudo. Ahora reciben un modelo pydantic validado, con normalización (`strip().lower()`) centralizada en `.normalizado()` en vez de repetida en cada función.

Con esto, **toda entrada y salida del pipeline que cruza un límite de función/LLM es un modelo pydantic**: nada de dicts sueltos ni strings sin forma.

### Mapa de esquemas (`schemas.py`)

| Modelo | Dónde se usa | Rol |
| --- | --- | --- |
| `RouterDecision` | salida de `router_chain.py` | fuerza `intent` a uno de 4 valores válidos (enum), evita que el LLM invente una categoría |
| `ConsultaProducto` | entrada de `mock_tools.py` | valida y normaliza el nombre de producto antes de consultar |
| `StockAnswer` | salida de `consultar_stock` | disponibilidad + cantidad + mensaje |
| `PromoAnswer` | salida de `consultar_promociones` | lista de promociones + mensaje |
| `RagAnswer` | salida de `rag_chain.py` | `informacion_insuficiente: bool` obliga a declarar cuando el contexto no alcanza, en vez de vacilar |
| `FuenteCitada` | dentro de `RagAnswer.fuentes` | archivo + fragmento citado |

Todas las salidas de LLM pasan por `llm.with_structured_output(Modelo)` (function calling de Gemini), no por parseo de texto libre.

### `prompts.py`

```python
ROUTER_SYSTEM_PROMPT = "..."   # usado por router_chain.py
RAG_SYSTEM_PROMPT   = "..."    # usado por rag_chain.py
RAG_HUMAN_TEMPLATE  = "Contexto:\n{contexto}\n\nPregunta: {pregunta}"

```

`router_chain.py` y `rag_chain.py` ahora importan de acá en vez de tener el texto embebido en un `ChatPromptTemplate.from_messages([...])` inline.

### Flujo de datos actualizado

```
pregunta (str)
  -> router_chain -> RouterDecision (intent, producto, justificacion)
       intent = stock/promociones -> ConsultaProducto(producto=...)
                                        -> consultar_stock / consultar_promociones
                                        -> StockAnswer / PromoAnswer
       intent = tecnico -> rag_chain -> RagAnswer (respuesta, confianza, fuentes, informacion_insuficiente)

```

## Integración con `VectorStoreManager` (rag-anydoc-app)

### Qué cambió

Antes el CLI (`main.py`, hoy `cli.py`) construía los embeddings y el vectorstore a mano:

```python
embeddings = HuggingFaceEmbeddings(...)
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings, ...)

```

Ahora eso vive en `services.py`, que delega en el paquete `ingester`:

```python
VectorStoreManager(embedding_provider, persist_dir, collection_name).get_vectorstore()

```

### Por qué

* **Una sola fuente de verdad**: el ingestador y el asistente abren la misma colección con el mismo `persist_dir`/`collection_name` del `config.toml`.
* **Intercambio de embeddings sin tocar el pipeline**: los providers ya están encapsulados detrás de `IEmbeddingProvider`; el resto del código solo pide `get_vectorstore()`.
* **Reutilización de `get_stats()**` para diagnóstico (cantidad de chunks y archivos) desde la UI.

### Cómo se importa `ingester` (proyecto hermano)

`rag-inference-app/` está al lado de `rag-anydoc-app/`. En `services.py` se agrega la ruta del vecino a `sys.path` una vez (`services.py` vive en `src/`, por eso `parents[2]` sube hasta la carpeta que contiene a ambos proyectos):

```python
ANY_DOC_APP = Path(__file__).resolve().parents[2] / "rag-anydoc-app"
if str(ANY_DOC_APP) not in sys.path:
    sys.path.insert(0, str(ANY_DOC_APP))

```

Así `from ingester.vectorstore import VectorStoreManager` funciona sin instalar nada. El `config.toml` también se lee de `ANY_DOC_APP`, y el `persist_dir` relativo (`./database/chroma_db`) se resuelve contra esa carpeta, para que no dependa del directorio desde el que se lance Streamlit.

### Advertencia: dimensiones de embeddings

Chroma no admite vectores de distinta dimensión en una misma colección. Hay que usar **el mismo proveedor con el que se ingestaron** los documentos o la búsqueda de similitud falla (o devuelve basura). Por eso en la UI el selector de embeddings va acompañado de una nota, y el `GeminiEmbeddingProvider` / `CohereEmbeddingProvider` piden su API key.

## Capa de presentación didáctica (paso a paso)

El flujo ya **no** usa las cadenas compuestas (`router | rag_chain`) directamente para responder. Esa orquestación manual vive ahora en `src/pipeline.py` y la comparten los dos entrypoints: `app.py` (Streamlit) y `cli.py` (Typer + Rich). Cada uno es solo un *presenter* que traduce los mismos eventos a su medio (widgets en pantalla o paneles/tablas en la terminal). Las etapas que emite el flujo son:

1. **Embedding de la consulta**: se calcula el vector de la pregunta y se muestra su dimensión, los primeros valores y el tiempo que tardó.
2. **Router**: se muestra el `RouterDecision` completo (intención, producto detectado, justificación) antes de decidir qué rama seguir.
3. **Búsqueda por cercanía (bi-encoder)**: si la intención es `tecnico`, se listan los `k` candidatos recuperados de Chroma junto con su distancia y el archivo de origen.
4. **Reranking**: se muestra el nuevo orden de los `top_n` documentos finales, indicando de qué puesto salió cada uno, para que se vea claramente qué hizo el reranker.
5. **Generación de la respuesta**: se muestra el contexto final que recibe el LLM y la salida estructurada completa (`RagAnswer`: respuesta, confianza, fuentes, `informacion_insuficiente`).

Si la intención es `stock` o `promociones`, se muestra directamente el paso de `mock_tools` (sin búsqueda ni reranking, porque esas ramas no usan RAG).

En `app.py`, la barra lateral agrega dos controles nuevos, además de los que ya existían (proveedor de embeddings, keys, reranker):

* **Candidatos del bi-encoder (k)**: cuántos documentos trae la búsqueda por cercanía antes de rerankear.
* **Documentos finales tras el reranker (top_n)**: cuántos de esos candidatos llegan al LLM como contexto.
* **Mostrar el paso a paso interno**: checkbox para apagar la vista didáctica y usar la app en modo "solo la respuesta final" cuando ya no haga falta explicar el flujo.

`cli.py` expone los equivalentes por flags: `--k`, `--top-n`, `--provider`, `--reranker`, `--google-api-key`, `--embedding-api-key`, `--cohere-api-key` y `--mostrar-pasos/--no-mostrar-pasos` (todos con default tomado de `config.toml`, salvo las keys).

### Qué cambió en el código para soportar esto

* **`retrieval.py`**: se agregaron dos funciones nuevas (nada de lo existente se tocó):
* `biencoder_retrieve_with_scores(vectorstore, query, k)`: igual que `biencoder_retrieve`, pero conserva la distancia de similitud de Chroma para poder mostrarla en la UI o el CLI.
* `embed_query_for_display(vectorstore, query)`: devuelve el vector de la consulta, leyendo la función de embeddings del propio `vectorstore` (sin necesidad de guardar el `embedding_provider` aparte).


* **`services.py`**: `build_components(...)` arma `vectorstore`, `reranker`, `router` y el LLM estructurado del RAG **sueltos** (sin componerlos en una cadena), para que el flujo pueda invocar cada pieza por separado. `build_pipeline(...)` (versión compuesta) quedó tal cual, pero ya no lo usan los entrypoints: hoy `app.py` y `cli.py` van por `build_components()` + `pipeline.py`.
* **`src/pipeline.py` (nuevo)**: la orquestación paso a paso, escrita una sola vez, como generador de eventos. No conoce Streamlit ni Rich.
* **`app.py`**: la ex UI (`src/streamlit_app.py`) movida a la raíz. Ya no orquesta el flujo a mano: consume los eventos de `pipeline.py` y los dibuja con `st.status(...)` por cada paso.
* **`cli.py` (nuevo)**: CLI con Typer (comando + opciones) y Rich (paneles/tablas), que consume los mismos eventos que `app.py`. Corre en REPL (o con una pregunta puntual como argumento).

### Flujo de datos actualizado (compartido por `app.py` y `cli.py`)

```
pregunta (str)
  -> embed_query_for_display(vectorstore, pregunta)      [Paso 1: solo se muestra]
  -> router.invoke({"pregunta": pregunta})               [Paso 2]
       intent = stock/promociones
           -> ConsultaProducto -> mock_tools -> respuesta [Paso 3 (único)]
       intent = tecnico
           -> biencoder_retrieve_with_scores(k)            [Paso 3]
           -> reranker.rerank(top_n)                       [Paso 4]
           -> format_context + RAG_PROMPT + rag_structured_llm.invoke  [Paso 5]
           -> RagAnswer (respuesta, confianza, fuentes, informacion_insuficiente)

```

### Modelo de eventos (`pipeline.py`)

`ejecutar_pipeline(pregunta, componentes, k_candidatos, top_n_rerank)` es un generador que emite un evento por etapa y termina con `Final(texto)`, la respuesta en texto plano que ambos entrypoints usan para el historial:

| Evento | Cuándo se emite | Qué lleva |
| --- | --- | --- |
| `StepStart(numero, titulo)` / `StepEnd(numero, label, state)` | abre/cierra cada paso | `state` es `complete` o `error` |
| `Embedding(vector, elapsed)` / `EmbeddingError(mensaje)` | paso 1 | vector de la consulta (o el error si no se pudo calcular) |
| `Router(decision)` | paso 2 | `RouterDecision` completo |
| `Tool(tipo, respuesta)` | ramas `stock` / `promociones` | `StockAnswer` / `PromoAnswer` |
| `Retrieval(candidatos, k)` | paso 3 (`tecnico`) | pares `(Document, distancia)` |
| `Rerank(top_docs, posiciones, top_n)` | paso 4 | docs reordenados + de qué puesto salió cada uno |
| `Generation(contexto, respuesta)` | paso 5 | contexto enviado al LLM + `RagAnswer` |
| `Final(texto)` | cierre | respuesta final en texto plano |

La decisión de mostrar u ocultar los pasos es del *presenter* (el método `handle(evento)`), no del flujo: `pipeline.py` **siempre** emite todos los eventos. Así el comportamiento es idéntico entre `app.py` y `cli.py`, y tanto `--no-mostrar-pasos` como destildar el checkbox solo cambian la representación, no la lógica.

### Notas de empaquetado

`app.py` y `cli.py` viven en la raíz, mientras que los módulos están en `src/`. Ambos entrypoints agregan `src/` a `sys.path` al inicio (los módulos de `src/` se importan "planos": `from config import ...`). El `pyproject.toml` declara ahora `typer`, `rich` y `streamlit` y usa `[tool.uv] package = false`, porque la app son scripts planos y no un paquete instalable.

## Cómo ejecutar

```bash
# 1) Ingestar documentos (app Streamlit de rag-anydoc-app)
cd rag-anydoc-app
uv run start            # o: streamlit run app.py

# 2) Asistente de preguntas, modo paso a paso (UI Streamlit)
cd ../rag-inference-app
streamlit run app.py    # o: uv run streamlit run app.py

# 3) Alternativa CLI (Typer + Rich), mismo flujo paso a paso
GOOGLE_API_KEY=... uv run python cli.py                     # REPL (salir para terminar)
GOOGLE_API_KEY=... uv run python cli.py "cuanto stock hay de notebook"
GOOGLE_API_KEY=... uv run python cli.py "como funciona el router" --no-mostrar-pasos

```

## Pendiente / siguiente paso natural

* Guardrails reales: hoy `guardrail_check()` solo valida que la pregunta no esté vacía. El hook ya está listo para enchufar NeMo Guardrails / Llama Guard o patrones prohibidos sobre `RagAnswer.respuesta` antes de mostrarla.
* Historial conversacional con memoria (hoy cada pregunta es independiente).
* Cuando se migre a FastAPI, `ConsultaProducto` y `RouterDecision` sirven tal cual como modelos de request/response de los endpoints.
* Si en algún momento se quiere volver a la versión "solo respuesta final" sin tocar nada, alcanza con dejar destildado "Mostrar el paso a paso interno" en la barra lateral (o usar `--no-mostrar-pasos` en el CLI): el pipeline se ejecuta igual, solo cambia que no se despliegan los `st.status` de cada etapa.
