# Etapa `ingest` — construir el índice

Job por lotes que **no se despliega**. Lee los documentos fuente y el catálogo de MongoDB y
deja listo el índice de ChromaDB (`data/chroma_db`) que consumen `runtime` y `eval`.

```
 data/documents/*.pdf|docx|xlsx ─┐
                                 ├─> chunks ─> embeddings ─> data/chroma_db ──> runtime / eval
 MongoDB (catalogo) ─────────────┘
```

## Qué hace

1. Convierte cada archivo de `data/documents` a markdown (`anydoc`).
2. Corta por encabezados (h1–h3) y luego por tamaño (`chunk_size=800`, `overlap=120`).
3. Lee el catálogo de MongoDB y lo mapea a documentos con `tipo="producto"`.
4. **Reconstruye la colección desde cero** (`reset_collection`): correrlo dos veces da el mismo resultado.

Código: `ingest/main.py` (entrypoint) + `src/ingest.py` (lógica).

## Dependencias (grupo `ingest`)

`core` (config, embeddings, Chroma, BM25) + `firecrawl-anydoc` + `langchain-text-splitters` + `pymongo`.
Sin FastAPI, sin NeMo, sin RAGAS. `anydoc` vive solo aquí: el runtime nunca lo necesita.

## Variables de entorno

Usa el `.env` de `12_clase/` (ver `env.sample`): `GOOGLE_API_KEY` (o `COHERE_API_KEY` si
`llm.provider = "cohere"`), `MONGODB_URI`. `SUPABASE_KEY` es exigida por `Settings` pero aquí no se usa.

## Ejecutar

Desde `12_clase/`.

```bash
# Local
uv sync --only-group ingest
uv run --only-group ingest python -m ingest.main

# Docker (el índice queda en ./data/chroma_db del host)
docker build -f ingest/Dockerfile -t ortelana-ingest .
docker run --rm --env-file .env -v "$PWD/data:/app/data" ortelana-ingest
```

## Salida

`data/chroma_db/` (ignorado por git). Es el **artefacto** que pasa a la siguiente etapa:
`runtime/Dockerfile` lo copia dentro de la imagen; `eval` lo lee montando `data/`.

## Cuándo volver a correrlo

- Cambió el catálogo en MongoDB o los documentos de `data/documents`.
- Cambió `llm.provider` (cada provider tiene su propia colección: dimensiones de embeddings distintas).
- Cambió `chunk_size` / `chunk_overlap`.

Después de correrlo hay que **reconstruir la imagen de `runtime`** (el índice va dentro).

## Límite conocido

Es una reconstrucción total, no incremental. El `upsert` por `content_hash` descrito en el
README de la clase (sección 6) sigue sin implementarse.
