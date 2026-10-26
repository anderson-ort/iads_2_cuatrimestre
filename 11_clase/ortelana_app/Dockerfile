FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1

# Same uid as the host user, so the mounted data/ (Chroma index) stays writable.
# Created before installing so files are owned by it without a costly `chown -R` layer.
RUN useradd --uid 1000 --create-home app && mkdir /app && chown app /app
USER app
WORKDIR /app

COPY --chown=app pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY --chown=app config.toml main.py ./
COPY --chown=app src ./src
COPY --chown=app guardrails ./guardrails

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uv", "run", "--no-sync", "main.py", "serve"]
