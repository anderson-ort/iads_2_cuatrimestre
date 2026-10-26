# Ortelana App

Production conversational assistant for Ortelana Textil, implementing the PRD in `../README.md`.

FastAPI → NeMo Guardrails → LangGraph router (`rag_direct`, `cuit_direct`, `react_agent`, `general`)
→ NeMo Guardrails. Hybrid RAG: BM25 + ChromaDB → RRF (k=60) → Cohere rerank.
Conversation memory in MongoDB (`MongoDBSaver`), traces in LangSmith, quality with RAGAS.

## Setup

```bash
uv sync
cp env.sample .env         # secrets only; everything else lives in config.toml
```

`.env` keys: `GOOGLE_API_KEY`, `COHERE_API_KEY`, `MONGODB_URI`, `SUPABASE_KEY`,
`LANGSMITH_API_KEY`, `SEARXNG_SECRET`.

Set the Supabase project URL and the real competitor names in `config.toml`.

## Commands

```bash
uv run main.py ingest                         # documents (data/documents) + Mongo catalog -> Chroma
uv run main.py search "tela térmica"          # hybrid search, prints reranked chunks
uv run main.py ask --session s1 "hola"        # one turn through the graph, persisted in Mongo
uv run main.py eval [eval_ortelana_v1]        # RAGAS over data/eval/<name>.json
uv run main.py serve                          # REST API on config.toml [api]
uv run pytest                                 # offline tests (fake LLMs and HTTP)
```

Run `ingest` again after changing `llm.provider`: each provider has its own collection.

## Docker

```bash
uv run main.py ingest      # the index in ./data is mounted into the API container
docker compose up -d --build
```

The API uses host networking so `localhost:8888` (SearXNG) works the same inside and outside Docker.

## Endpoints

- `POST /api/v1/chat` — `{user_id, session_id, message}` → `{session_id, response, routing_used, guardrail_status}`.
  `session_id` is the LangGraph `thread_id`; `user_id` is sent to LangSmith as metadata.
- `POST /api/v1/eval` — `{dataset_name, metrics?}` → `{status, samples_evaluated, scores, timestamp}`.
  Evaluates the `rag_direct` path. At most 2 metrics per run; default
  `["answer_relevance", "context_recall"]` (the cheapest pair). Judge LLM calls per sample:
  `context_recall` 1, `answer_relevance` 1, `faithfulness` 2, `context_precision` 1 per context (4).
- `GET /health`

## Cost per chat message (LLM calls)

Input rail 1 (fast model) + router 1 (fast model) + answer 1 (synthesizer) or N (ReAct loop)
+ output rail 1 (fast model) + Cohere rerank 1 when retrieval runs.
