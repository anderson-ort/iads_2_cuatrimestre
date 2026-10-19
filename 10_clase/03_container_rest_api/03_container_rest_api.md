# API REST del orquestador dentro de un container

### 3.1 La API (`main.py`)

**Qué se hace:** FastAPI expone el orquestador del punto 2 con dos memorias distintas.

| Endpoint | Memoria | Cómo se elige el `thread_id` |
|---|---|---|
| `GET /health` | - | - (devuelve el proveedor de LLM activo) |
| `POST /query` | Volátil (`MemorySaver`) | El que mandes, o uno aleatorio nuevo |
| `POST /query-memory` | Persistente (`SqliteSaver`) | `thread_id` > hash del `email` > uno nuevo |
| `GET /state/{thread_id}?memoria=...` | La que indiques (default `persistente`) | El de la URL |

**Teoría:**
- `lifespan` construye los dos grafos **una sola vez** al arrancar y los guarda en `app.state`. Compilar el grafo y crear el LLM en cada request sería lento.
- Los endpoints son `def` (sync). FastAPI los corre en un threadpool, así la llamada bloqueante al LLM no frena el event loop. Por eso SQLite se abre con `check_same_thread=False`.
- Los esquemas de `src/schemas.py` validan la entrada (`pregunta` no vacía, `email` válido con `EmailStr`) y documentan la API en `/docs`.
- Un error del agente se traduce a `502 Bad Gateway`: el problema está en un servicio de afuera (LLM, Supabase), no en el request del cliente.

### 3.2 La imagen (`Dockerfile`)

**Qué se hace:** se empaqueta la API con sus dependencias en una imagen reproducible.

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev        # capa de dependencias

COPY src ./src                        # capa de codigo
COPY data/ortelana_db.json ./data/
COPY main.py ./

USER app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Teoría:**
- **Orden de capas:** Docker cachea cada instrucción. Primero se copian `pyproject.toml` y `uv.lock` y se instalan las dependencias; después el código. Si solo cambia `main.py`, el `uv sync` no se vuelve a ejecutar.
- **`--frozen`:** instala exactamente lo que dice `uv.lock`. La imagen tiene las mismas versiones que tu máquina.
- **`--host 0.0.0.0`:** dentro del container, `127.0.0.1` solo es accesible desde el propio container. Hay que escuchar en todas las interfaces para que el `-p 8000:8000` funcione.
- **`USER app`:** el proceso no corre como root. Si alguien explota la API, tiene menos permisos.
- **`HEALTHCHECK`:** Docker consulta `/health` cada 30 s y marca el container como `healthy` o `unhealthy`. Se usa `python -c` porque la imagen `slim` no trae `curl`.

### 3.3 Qué NO entra en la imagen (`.dockerignore`)

`.env`, `.venv`, `__pycache__`, `*.db` y `.git` quedan afuera:
- **`.env`:** los secretos nunca se hornean en la imagen. Cualquiera con la imagen podría leerlos con `docker history` o abriendo las capas. Se inyectan al correr (`--env-file` o `env_file` en compose).
- **`.venv`:** está compilado para tu sistema operativo; el container arma el suyo.
- **`*.db`:** el estado no es parte de la imagen, vive en un volumen (ver 3.4).

### 3.4 Persistencia con volúmenes (`compose.yaml`)

**Qué se hace:** la memoria persistente (SQLite) se guarda fuera del container.

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - memoria:/app/state
volumes:
  memoria:
```

**Teoría:** el filesystem de un container es descartable: `docker rm` borra todo lo que se escribió adentro. El volumen `memoria` se monta en `/app/state` y `DB_PATH=/app/state/agent.sqlite.db` (variable de entorno, leída en `src/memory.py`) hace que SQLite escriba ahí. Así el historial de `/query-memory` sobrevive a reinicios y a reconstruir la imagen. La memoria volátil (`/query`) se pierde siempre que se reinicia el proceso, con o sin container.

### 3.5 Cómo correrlo

```bash
# Con compose (recomendado)
docker compose up --build -d
docker compose ps            # columna STATUS: (healthy)
docker compose logs -f api

# Sin compose
docker build -t agentes-api .
docker run --rm -p 8000:8000 --env-file .env -v memoria:/app/state agentes-api
```

Prueba de persistencia:
1. Hacé un `POST /query-memory` con un `email`.
2. Corré `docker compose down` y después `docker compose up -d` (sin `-v`: `down -v` borra el volumen).
3. Consultá `GET /state/<thread_id>`. El historial sigue ahí.

### 3.6 Para seguir explorando

- Reemplazar SQLite por un servicio `mongo` o `postgres` en el mismo `compose.yaml` y usar el checkpointer correspondiente (ver la alternativa MongoDB del punto 2).
- Agregar autenticación (API key en un header) antes de exponer la API. Hoy cualquiera que conozca un email puede leer su `/state`.
- Correr con varios workers (`uvicorn --workers 2`). Con `MemorySaver` cada worker tiene su propia RAM: un `thread_id` puede "olvidarse" si el request cae en otro worker. Es un buen ejemplo de por qué la memoria compartida va en una base externa.
