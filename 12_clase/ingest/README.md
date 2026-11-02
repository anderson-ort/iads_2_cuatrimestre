# Etapa `ingest` — construir el índice

Job por lotes que **no se despliega**. Lee los documentos fuente y el catálogo de MongoDB y
deja listo el índice de **MongoDB Atlas Vector Search** que consumen `runtime` y `eval`.

```
 data/documents/*.pdf|docx|xlsx ─┐
                                 ├─> chunks ─> embeddings ─> Atlas (knowledge_<provider>) ──> runtime / eval
 MongoDB (catalogo) ─────────────┘
```

## Qué hace

1. Convierte cada archivo de `data/documents` a markdown (`anydoc`).
2. Corta por encabezados (h1–h3) y luego por tamaño (`chunk_size=800`, `overlap=120`).
3. Lee el catálogo de MongoDB y lo mapea a documentos con `tipo="producto"`.
4. Crea el índice de Atlas Vector Search (`vector_index`) si no existe y espera a que esté listo.
5. **Reconstruye los documentos desde cero** (`delete_many` + `add_documents`): correrlo dos veces da el mismo resultado.

Código: `ingest/main.py` (entrypoint) + `src/ingest.py` (lógica).

## Dependencias (grupo `ingest`)

`core` (config, embeddings, `langchain-mongodb`, `pymongo`, BM25) + `firecrawl-anydoc` + `langchain-text-splitters`.
Sin FastAPI, sin NeMo, sin RAGAS. `anydoc` vive solo aquí: el runtime nunca lo necesita.

## Variables de entorno

Usa el `.env` de `12_clase/` (ver `env.sample`): `GOOGLE_API_KEY` (o `COHERE_API_KEY` si
`llm.provider = "cohere"`), `MONGODB_URI` (usuario con permiso de escritura y de crear índices de Atlas Search). `SUPABASE_KEY` es exigida por `Settings` pero aquí no se usa.

## Ejecutar

Desde `12_clase/`.

```bash
# Local
uv sync --only-group ingest
uv run --only-group ingest python -m ingest.main

# Docker (el índice se escribe en Atlas, no en el host)
docker build -f ingest/Dockerfile -t ortelana-ingest .
docker run --rm --env-file .env -v "$PWD/data:/app/data" ortelana-ingest
```

Guía completa de la ingesta local (preparación de Atlas, verificación y problemas frecuentes):
[`../ATLAS_VECTOR_SEARCH.md`](../ATLAS_VECTOR_SEARCH.md#ingesta-local-paso-a-paso).

## Salida

La colección `knowledge_<provider>` en la base `ortelana-app-database` y su índice `vector_index`
(ver `[vectorstore]` en `config.toml`). Es el **artefacto** que pasa a la siguiente etapa: `runtime`
y `eval` lo leen directo de Atlas. Ya no hay carpeta local ni copia dentro de la imagen.

## Cuándo volver a correrlo

- Cambió el catálogo en MongoDB o los documentos de `data/documents`.
- Cambió `llm.provider` (cada provider tiene su propia colección: dimensiones de embeddings distintas).
- Cambió `chunk_size` / `chunk_overlap`.

Después de correrlo basta **reiniciar `runtime`** (carga los chunks en memoria al arrancar para BM25); la imagen no cambia.

## Límite conocido

Es una reconstrucción total, no incremental. El `upsert` por `content_hash` descrito en el
README de la clase (sección 6) sigue sin implementarse.
