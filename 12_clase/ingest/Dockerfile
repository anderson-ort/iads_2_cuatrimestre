# Ingest stage: a batch job that builds the Atlas Vector Search index. Never deployed as a service.
# Build from the 12_clase/ folder:
#   docker build -f ingest/Dockerfile -t ortelana-ingest .
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --only-group ingest --no-install-project


FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --uid 1000 --create-home app && mkdir /app && chown app /app
USER app
WORKDIR /app

COPY --from=builder --chown=app /app/.venv ./.venv

COPY --chown=app config.toml ./
COPY --chown=app src/__init__.py src/config.py src/llm.py src/retrieval.py src/ingest.py ./src/
COPY --chown=app ingest ./ingest

RUN python -c "import ingest.main"

# data/ is mounted: documents are read from data/documents; the index is written to MongoDB Atlas.
CMD ["python", "-m", "ingest.main"]
