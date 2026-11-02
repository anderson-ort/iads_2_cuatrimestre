# Runtime stage: the only image that goes to production.
# Build from the 12_clase/ folder, after the ingest stage produced data/chroma_db:
#   docker build -f runtime/Dockerfile -t ortelana-runtime .
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --only-group runtime --no-install-project


FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Same uid as the host user, so a mounted data/ stays writable.
RUN useradd --uid 1000 --create-home app && mkdir /app && chown app /app
USER app
WORKDIR /app

# Only the virtualenv: no uv, no ragas, no anydoc.
COPY --from=builder --chown=app /app/.venv ./.venv

COPY --chown=app config.toml ./
COPY --chown=app guardrails ./guardrails
COPY --chown=app src/__init__.py src/config.py src/llm.py src/retrieval.py src/prompts.py \
    src/cuit.py src/web.py src/tools.py src/graph.py src/guardrails.py src/schemas.py \
    src/api.py ./src/
COPY --chown=app runtime ./runtime
# Read-only index built by the ingest stage, baked into the image. Mount a volume on
# /app/data to override it without rebuilding.
COPY --chown=app data/chroma_db ./data/chroma_db

# Fail the build, not the first request, if a module is missing from the COPY list above.
RUN python -c "import runtime.main"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "-m", "runtime.main", "serve"]
