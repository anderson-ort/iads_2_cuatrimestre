# Etapa `runtime` — el servicio en producción

Es la **única etapa que se despliega**. Sirve la API REST del asistente de Ortelana.

```
Cliente -> FastAPI -> NeMo input rails -> Orquestador LangGraph -> NeMo output rails -> Cliente
                                           |-- rag_direct   (BM25 + Atlas Vector Search + RRF + rerank)
                                           |-- cuit_direct  (Supabase)
                                           |-- react_agent  (RAG + CUIT + web)
                                           `-- general
```

Memoria de conversación en MongoDB (`thread_id = session_id`), trazas en LangSmith.

## Endpoints

| Método | Ruta | Uso |
|---|---|---|
| GET | `/health` | Healthcheck |
| POST | `/api/v1/chat` | `{user_id, session_id, message}` → `{session_id, response, routing_used, guardrail_status}` |

**No expone `/api/v1/eval`** (movido a la etapa `eval`).

## Dependencias (grupo `runtime`)

`core` (incluye `langchain-mongodb` y `pymongo`) + `agent` + `fastapi` + `uvicorn` + `nemoguardrails` + `langgraph-checkpoint-mongodb`.
No incluye `ragas`, `openai`, `langchain-community` ni `anydoc`.

Medido con `uv sync` + Docker: **146 paquetes** y venv de **537 MB**, contra 168 paquetes y 940 MB
del proyecto original; imagen de **1,11 GB** contra 1,88 GB.

## Requisito previo: el índice

El índice vectorial vive en **MongoDB Atlas** (colección `knowledge_<provider>`), construido por
la etapa `ingest`. La imagen ya **no** lo incluye: el contenedor lo lee al arrancar (también arma
BM25 en memoria con esos chunks). Para actualizar el catálogo: correr `ingest` y **reiniciar** el
servicio; no hace falta reconstruir la imagen. Si el índice está vacío, el arranque falla con
`Empty index: run ingest first`. Detalle y motivo: [`../ATLAS_VECTOR_SEARCH.md`](../ATLAS_VECTOR_SEARCH.md).

## Ejecutar

Desde `12_clase/`.

```bash
# Local
uv sync --only-group runtime
uv run --only-group runtime python -m runtime.main serve
uv run --only-group runtime python -m runtime.main search "tela térmica"
uv run --only-group runtime python -m runtime.main ask --session s1 "hola"   # sin guardrails

# Docker (imagen sola)
docker build -f runtime/Dockerfile -t ortelana-runtime .
docker run --rm -p 8000:8000 --env-file .env ortelana-runtime

# Docker Compose (API + SearXNG), desde 12_clase/runtime/
docker compose up -d --build
```

## Variables de entorno

`.env` de `12_clase/` (ver `env.sample`): `GOOGLE_API_KEY`, `COHERE_API_KEY`, `MONGODB_URI`,
`SUPABASE_KEY`, opcional `LANGSMITH_API_KEY`. En producción usar el secret manager del host,
no un archivo `.env`.

## Qué falta antes de exponerlo (ver análisis previo)

- **Autenticación y rate limit** en `/api/v1/chat`: hoy cualquiera puede consumir la cuota de Gemini.
- Los `competitors` de `config.toml` son de ejemplo.
- `searxng_url` apunta a `localhost:8888`: en Cloud Run no hay host networking; SearXNG necesita
  su propio servicio, o se apoya solo en el fallback DuckDuckGo.
- Sin tests ni CI.

## Las tres etapas

| Etapa | Rol | Se despliega | Grupo |
|---|---|---|---|
| `ingest` | Construye el índice en Atlas | No (job) | `ingest` |
| `runtime` | Sirve `/api/v1/chat` | **Sí** | `runtime` |
| `eval` | Puntúa el RAG con RAGAS | No (job) | `eval` |
