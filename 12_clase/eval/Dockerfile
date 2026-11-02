# Eval stage: a batch job that scores the RAG path with RAGAS. Never deployed as a service.
# Build from the 12_clase/ folder:
#   docker build -f eval/Dockerfile -t ortelana-eval .
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --only-group eval --no-install-project


FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --uid 1000 --create-home app && mkdir /app && chown app /app
USER app
WORKDIR /app

COPY --from=builder --chown=app /app/.venv ./.venv

COPY --chown=app config.toml ./
COPY --chown=app src/__init__.py src/config.py src/llm.py src/retrieval.py src/prompts.py \
    src/cuit.py src/web.py src/tools.py src/graph.py src/evaluation.py ./src/
COPY --chown=app eval ./eval

RUN python -c "import eval.main"

# data/ is mounted for the golden sets in data/eval; the index is read from MongoDB Atlas (built by ingest). The dataset name is the container argument.
CMD ["python", "-m", "eval.main"]
