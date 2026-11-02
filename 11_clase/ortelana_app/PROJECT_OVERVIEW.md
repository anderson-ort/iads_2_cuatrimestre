# Ortelana App — Resumen del proyecto (legible por agentes)

Estado de `11_clase/ortelana_app/` al 2026-11-02. Objetivo: que cualquier agente de código entienda
qué existe, cómo se conecta y qué falta, sin releer todo el repositorio.
Fuente de la especificación: el PRD en `../README.md`. Diagrama de diseño: `../docs/ortelana-app-design.png`.
Notas conceptuales: `../docs/bm25.md`, `../docs/nemo_guardrails.md`, `../docs/searxng.md`.

## 1. Qué es

Asistente conversacional de nivel producción para **Ortelana Textil**, distribuidora mayorista de
telas en Argentina. Responde (en español) sobre catálogo, precios, stock, descuentos, promociones,
envíos, reglas de alta de distribuidores, validación de CUIT e información web actualizada.

Camino de una request:

```
Cliente -> FastAPI -> NeMo input rails -> Orquestador LangGraph -> NeMo output rails -> Cliente
```

Stack: Python 3.13, `uv`, FastAPI/uvicorn, LangGraph + `langchain`, ChromaDB, `rank-bm25`,
rerank de Cohere, LLMs Gemini (por defecto) o Cohere, MongoDB (catálogo + memoria de
conversación), Supabase REST (tabla de CUIT), SearXNG + DuckDuckGo (web), NeMo Guardrails,
RAGAS, LangSmith.

## 2. Estructura del repositorio

```
main.py                 Entrypoint + cableado de dependencias (argparse: ingest|search|ask|eval|serve)
config.toml             Toda la configuración no secreta (modelos, rutas, URLs, umbrales)
env.sample / .env       Solo secretos (.env está ignorado por git)
pyproject.toml, uv.lock Dependencias (package = false, sin build)
Dockerfile              python:3.13-slim + uv, usuario no root uid 1000, healthcheck en /health
docker-compose.yaml     searxng + api (la api usa host networking)
guardrails/             Config de NeMo: config.yml, rails.co (Colang), prompts.yml
searxng/settings.yml    Config de SearXNG (formato JSON habilitado, limiter apagado)
data/documents/         Documentos fuente: 2 PDF, 1 DOCX, 1 XLSX (promociones, descuentos, reglas de alta)
data/eval/              eval_ortelana_v1.json (dataset RAGAS: question + ground_truth)
data/chroma_db/         Lo crea `ingest` (no existe en un checkout limpio)
src/                    Módulos de la aplicación (~990 líneas), ver sección 3
```

No existe el directorio `tests/` (ver sección 7).

## 3. Componentes

### 3.1 `main.py` — raíz de composición y CLI
- `build_orchestrator(settings, retriever, checkpointer)` arma el grafo con el modelo `chat`,
  el `router` (modelo rápido), retriever, cliente CUIT, búsqueda web y checkpointer de MongoDB.
- Comandos: `ingest`, `search "<q>"`, `ask --session <id> "<msg>"`, `eval [dataset]`, `serve`.
- `serve` también construye los guardrails (modelo rápido) y el evaluador RAGAS, y levanta uvicorn.
- Nota: `ask` NO aplica guardrails; solo la API REST los aplica.

### 3.2 `src/config.py` — configuración tipada
- `load_settings()` combina `config.toml` (no secreto) con `.env` (secretos vía pydantic-settings).
- `Secrets`: `google_api_key` (opcional), `cohere_api_key`, `mongodb_uri`, `supabase_key`
  (obligatorias), `langsmith_api_key` (opcional).
- `Settings.collection_name` = `<chroma.collection>_<provider>`: cada provider tiene su propia
  colección de Chroma porque las dimensiones de embeddings difieren. Volver a correr `ingest`
  al cambiar `llm.provider`.
- `configure_tracing()` exporta variables de LangSmith; el tracing se desactiva solo si falta la clave.

### 3.3 `src/llm.py` — fábricas de modelos
- `chat_model(settings, fast=False)` y `embeddings(settings)` para provider `google` o `cohere`.
- Por defecto: chat `gemini-2.5-flash`, router/rápido `gemini-3.5-flash-lite`, embeddings
  `gemini-embedding-001` (768 dimensiones). Cohere: `command-a-03-2025`,
  `embed-multilingual-light-v3.0`.
- Los imports de cada provider son diferidos (lazy).

### 3.4 `src/ingest.py` — pipeline de indexación (`uv run main.py ingest`)
- Convierte cada archivo de `data/documents` a markdown con `anydoc` (pdf/docx/xlsx).
- Divide por encabezados markdown (h1–h3) y luego por tamaño (chunk 800, overlap 120). Ids de
  chunk: `<source>-<n>`; metadato `tipo="documento"`.
- Lee el catálogo de productos desde MongoDB (`ortelana-app-database.catalogo`) y mapea cada
  registro a un Document (`"<nombre>: <descripcion_semantica>"`, metadato `tipo="producto"`;
  los valores lista se unen en string porque Chroma solo acepta escalares).
- Reconstruye la colección desde cero (`reset_collection`): es idempotente.

### 3.5 `src/retrieval.py` — retriever híbrido
- `HybridRetriever.search(query)`: top-k de BM25 + top-k vectorial de Chroma (coseno) ->
  Reciprocal Rank Fusion (`k=60`) -> rerank de Cohere (`rerank-multilingual-v3.0`) -> `top_n=4`.
- `tokenize()` pasa a minúsculas y quita acentos (NFKD) para BM25.
- El índice BM25 se arma en memoria al arrancar, con todos los documentos guardados en Chroma
  (`build_retriever`); lanza `ValueError` si el índice está vacío.
- Documentos y productos comparten una colección y se distinguen por el metadato `tipo`.

### 3.6 `src/graph.py` — orquestador LangGraph
```
START -> router -> rag_direct  -> synthesizer -> END
                -> cuit_direct -> synthesizer -> END
                -> general     -> synthesizer -> END   (contexto vacío)
                -> react_agent ----------------> END
```
- Estado `AgentState(MessagesState)` agrega `route` y `context` (por turno; también lo usa eval).
- Router: modelo rápido con salida estructurada `RouteDecision` (`rag_direct | cuit_direct |
  react_agent | general`). Prompt en `src/prompts.py`.
- `rag_direct`: búsqueda híbrida con la última pregunta. `cuit_direct`: extrae un CUIT por regex
  (`\b\d{2}-?\d{8}-?\d\b`) y consulta Supabase; si no hay CUIT, el contexto pide que se lo den.
- `react_agent`: `langchain.agents.create_agent` con 3 tools, para consultas multi-intención,
  ambiguas o que requieren web.
- `recent()` recorta el historial a los últimos 10 mensajes empezando en uno humano (nunca separa
  pares tool call/result). `synthesize()` es compartida con la evaluación.
- Memoria: checkpointer `MongoDBSaver`, `thread_id = session_id`.

### 3.7 `src/tools.py` — tools del agente ReAct
`search_ortelana(query)`, `lookup_cuit(cuit)`, `search_web(query)`; envuelven las mismas funciones
que usan los nodos deterministas.

### 3.8 `src/cuit.py` — consulta de CUIT
- `CuitClient` consulta Supabase PostgREST (`cuit_simulado`, filtro `cuit=eq.<11 dígitos>`).
- `describe_cuit()` devuelve JSON o `{"error": ...}` (largo inválido, no encontrado, servicio
  caído) para que el LLM pueda explicar el fallo. Usar solo la clave **anon** de Supabase (RLS con
  SELECT público).

### 3.9 `src/web.py` — búsqueda web
Primero SearXNG (`localhost:8888`, API JSON); ante error HTTP o de parseo cae a DuckDuckGo
(`ddgs`). Devuelve lista título/url/snippet para el agente.

### 3.10 `src/guardrails.py` + `guardrails/` — capa de seguridad
- `Guardrails.check_input` / `check_output` envuelven `LLMRails.check_async` de NeMo y devuelven
  `Verdict(passed, message)`.
- Input rails: `check competitors` (flow Colang determinista que llama a la action Python
  `mentions_competitor`, insensible a acentos; nombres desde `config.toml [guardrails].competitors`)
  y luego `self check input` (LLM, modelo rápido). Output rail: `self check output` (LLM).
- `_GeminiSafeAdapter` traduce `max_tokens` de NeMo a `max_output_tokens` de Gemini.
- `rails.co` define las respuestas del bot (`refuse to respond`, `redirect to ortelana`) en español.
- Los `competitors` de `config.toml` son placeholders ("Textil Rival", "Telas del Norte").

### 3.11 `src/api.py` + `src/schemas.py` — API REST
- `GET /health`.
- `POST /api/v1/chat` `{user_id, session_id, message<=2000}` -> `{session_id, response,
  routing_used, guardrail_status: passed|blocked_input|blocked_output}`. Flujo: input rail ->
  grafo (en threadpool) -> output rail. Una salida bloqueada reemplaza el mensaje AI guardado en
  el checkpoint (mismo id), así los turnos siguientes no la ven. `user_id` viaja a LangSmith como
  metadata.
- `POST /api/v1/eval` `{dataset_name, metrics?}` -> `{status, samples_evaluated, scores,
  timestamp}`; 404 si el dataset no existe.

### 3.12 `src/evaluation.py` — evaluación RAGAS
- Evalúa solo el camino `rag_direct` (retrieval híbrido + sintetizador) sobre
  `data/eval/<name>.json`.
- Métricas: `faithfulness`, `answer_relevance`, `context_precision`, `context_recall`.
  **Máximo 2 por corrida** (`MAX_METRICS`), por defecto `["answer_relevance", "context_recall"]`,
  para cuidar la cuota gratuita del juez.
- El juez es siempre Gemini (vía endpoint compatible con OpenAI; RAGAS 0.4 tiene problemas con el
  cliente async de genai), incluso con `llm.provider = cohere`. Reintenta ante
  429/503/RESOURCE_EXHAUSTED (3 intentos, 30 s de espera).
- El nombre del dataset se valida con la regex `^[A-Za-z0-9_-]+$` (defensa contra path traversal).

### 3.13 Infraestructura
- `Dockerfile`: `uv sync` congelado, copia `config.toml`, `main.py`, `src`, `guardrails`; ejecuta
  `serve`. `data/` se monta como volumen (el índice Chroma se construye en el host con `ingest`).
- `docker-compose.yaml`: `searxng` (puerto 8888->8080, requiere `SEARXNG_SECRET`) y `api`
  (host network, `.env`, volumen `./data`).

## 4. Servicios externos requeridos

| Servicio | Uso | Secreto |
|---|---|---|
| Google Gemini | chat, router, embeddings, guardrails, juez RAGAS | `GOOGLE_API_KEY` |
| Cohere | rerank (siempre); LLM/embeddings si provider=cohere | `COHERE_API_KEY` |
| MongoDB (Atlas) | origen del catálogo + checkpoints | `MONGODB_URI` |
| Supabase | tabla de CUIT `cuit_simulado` (URL en `config.toml`) | `SUPABASE_KEY` |
| LangSmith | tracing (opcional) | `LANGSMITH_API_KEY` |
| SearXNG | búsqueda web (docker) | `SEARXNG_SECRET` |

## 5. Qué se desarrolló hasta ahora

Hecho, según código y configuración:
- Pipeline completo ingest -> retrieval híbrido -> reranking.
- Router LangGraph con 4 rutas, nodos deterministas, agente ReAct y sintetizador.
- Memoria de conversación persistente (MongoDB) con recorte de historial.
- Guardrails NeMo de entrada/salida con filtro de competidores y fix de adaptador para Gemini.
- API REST con endpoints de chat, eval y health, más contratos Pydantic.
- Evaluación RAGAS con límites de cuota y reintentos.
- Cambio de provider LLM (Google/Cohere) con colección Chroma por provider.
- Búsqueda web con SearXNG primario y DuckDuckGo como fallback.
- Imagen Docker y stack compose, `env.sample` con guía por variable.
- Documentación de apoyo en `../docs/` (BM25, NeMo Guardrails, SearXNG) y diagrama de diseño.

## 6. Cómo ejecutarlo

```bash
uv sync && cp env.sample .env          # completar secretos; poner competidores reales en config.toml
uv run main.py ingest                  # construye data/chroma_db
uv run main.py search "tela térmica"
uv run main.py ask --session s1 "hola"
uv run main.py eval eval_ortelana_v1
uv run main.py serve                   # o: docker compose up -d --build
```

El subcomando es `serve`, no `server`; un nombre desconocido produce un error de argparse.

## 7. Brechas y riesgos conocidos (verificar antes de depender de ellos)

1. **No hay tests.** `pyproject.toml` define `testpaths = ["tests"]` y el README menciona
   `uv run pytest` ("tests offline"), pero `tests/` no existe.
2. `[guardrails].competitors` en `config.toml` tiene nombres de ejemplo.
3. Los comandos CLI `ask` y `search` no pasan por guardrails.
4. El índice BM25 se reconstruye en memoria en cada arranque desde todos los documentos de Chroma;
   no escala a catálogos grandes y requiere reiniciar el proceso tras `ingest`.
5. `eval` cubre solo el camino RAG, no CUIT, ReAct, web ni guardrails.
6. `docker-compose.yaml` usa `searxng/searxng:latest` (el tag fijo está comentado).
7. `data/chroma_db` no está versionado; el contenedor API falla con "Empty index" hasta que se
   ejecute `ingest` en el host.
8. La URL del proyecto Supabase está fija en `config.toml` (no secreta, pero específica del entorno).
9. El `README.md` de esta carpeta es más corto que el PRD de `../README.md`; el PRD es la
   especificación de referencia.

## 8. Convenciones para agentes que editen este repo

- Secretos solo en `.env`; el resto en `config.toml` con modelos tipados en `src/config.py`.
- Prompts en `src/prompts.py`, orquestación en `src/graph.py`, clientes de I/O en módulos propios
  (`cuit.py`, `web.py`), cableado de dependencias solo en `main.py`.
- Reutilizar `synthesize()` y `describe_cuit()`: los comparten nodos del grafo, tools y evaluación.
- Código y docs en inglés; el texto del bot hacia el usuario en español.
- Si cambiás un comando CLI, opción o endpoint: actualizar `README.md` y este archivo.
