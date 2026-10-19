FROM python:3.13-slim

# uv como binario estatico, copiado desde su imagen oficial
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DB_PATH=/app/state/agent.sqlite.db

# 1) Dependencias primero: esta capa se cachea mientras no cambie el lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 2) Codigo de la app (cambia seguido, va despues)
COPY src ./src
COPY data/ortelana_db.json ./data/
COPY main.py ./

# Usuario sin privilegios; /app/state es el punto de montaje del volumen SQLite
RUN useradd --create-home app && mkdir -p /app/state && chown app /app/state
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
