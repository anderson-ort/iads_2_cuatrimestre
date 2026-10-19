# Clase 10: agentes con tools, memoria y API REST en container

Construimos, paso a paso, un asistente para un distribuidor mayorista de telas (Ortelana). El asistente responde sobre catálogo, stock, pedidos, datos fiscales (CUIT) e información de la web. Cada punto agrega una capa sobre el anterior:

| Punto | Tema | Documento | Código |
|---|---|---|---|
| 1 | Agente con tools y orquestador multiagente | [01_agents/01_agentes_inteligentes.md](01_agents/01_agentes_inteligentes.md) | `01_agent.py`, `src/tools.py`, `src/agent.py` |
| 2 | Memoria de corto y largo plazo | [02_memoria/02_nodos_memoria_langgraph.md](02_memoria/02_nodos_memoria_langgraph.md) | `02_agent_subagent_short_memory.py`, `02_agent_subagent_long_memory.py`, `src/memory.py` |
| 3 | API REST con FastAPI dentro de un container | [03_container_rest_api/03_container_rest_api.md](03_container_rest_api/03_container_rest_api.md) | `main.py`, `src/schemas.py`, `Dockerfile`, `compose.yaml` |

## Estructura

```
10_clase/
├── 01_agent.py                          # Punto 1: agente LCEL con bucle ReAct manual
├── 02_agent_subagent_short_memory.py    # Punto 2: orquestador + MemorySaver (RAM)
├── 02_agent_subagent_long_memory.py     # Punto 2: orquestador + SqliteSaver (disco)
├── main.py                              # Punto 3: API FastAPI
├── Dockerfile / .dockerignore / compose.yaml
├── src/
│   ├── config.py     # proveedor de LLM, cliente Supabase, contexto, recortar()
│   ├── tools.py      # buscar_datos_internos, buscar_web, consultar_cuit
│   ├── agent.py      # router + subagentes (fiscal, datos, web, general)
│   ├── memory.py     # checkpointers volatil y persistente
│   └── schemas.py    # modelos Pydantic de la API y de la ruta del router
├── tests/
│   └── test_query_memory.py   # pruebas de /query-memory con LLM falso
├── data/ortelana_db.json   # base interna simulada
└── supabase/               # SQL para crear la tabla cuit_simulado
```

## Preparación

1. Instalá las dependencias con `uv sync`.
2. Copiá `env.sample` a `.env` y completá las keys. `GOOGLE_API_KEY` es el proveedor principal (Gemini); `COHERE_API_KEY` se usa solo si no hay key de Google.
3. Creá la tabla de CUIT en Supabase con `supabase/init-sql-supabase.sql` (ver [supabase/README.md](supabase/README.md)) y completá `SUPABASE_URL`, `SUPABASE_KEY` y `SUPABASE_TABLE`.

## Punto 1: agente con tools y orquestador

Tres tools que el LLM puede invocar:

| Tool | Fuente de datos |
|---|---|
| `buscar_datos_internos` | `data/ortelana_db.json` (productos, clientes, pedidos, políticas) |
| `buscar_web` | DuckDuckGo (`ddgs`) |
| `consultar_cuit` | API REST de Supabase (PostgREST) |

Ideas clave:
- **Tool calling:** el modelo no ejecuta código. Pide una llamada estructurada, el runtime la ejecuta y devuelve un `ToolMessage`. El docstring de cada tool es parte del prompt.
- **`01_agent.py`:** cadena LCEL `prompt | llm.bind_tools(...)` con un bucle ReAct escrito a mano (máximo `MAX_PASOS = 4`). Sirve para ver qué hace un agente "por dentro".
- **`src/agent.py`:** grafo LangGraph con un nodo `router` (`with_structured_output(Ruta)`) que deriva a un subagente especializado, armado con `create_agent`:

```
START -> router -> fiscal  (buscar_datos_internos + consultar_cuit)
                -> datos   (buscar_datos_internos)
                -> web     (buscar_web + buscar_datos_internos)
                -> general (sin tools)
                      -> END
```

```bash
uv run python 01_agent.py
```

## Punto 2: memoria de corto y largo plazo

- **Corto plazo:** `MemorySaver` guarda el estado por `thread_id` en RAM. Se pierde al reiniciar.
- **Largo plazo:** `SqliteSaver` guarda el mismo estado en `data/agent.sqlite.db` (configurable con `DB_PATH`). Sobrevive reinicios.
- **Mismo grafo, distinto checkpointer:** `crear_orquestador(saver)` recibe el checkpointer. Los subagentes no llevan checkpointer propio; la memoria la maneja el grafo padre.
- **Ventana de 10 mensajes:** `recortar()` (en `src/config.py`) limita lo que ve el LLM, en el router y en cada subagente (middleware `ventana` con `wrap_model_call`). El historial completo queda en el checkpointer.

```bash
uv run python 02_agent_subagent_short_memory.py
uv run python 02_agent_subagent_long_memory.py   # correlo dos veces: recuerda la conversación anterior
```

## Punto 3: API REST en un container

FastAPI expone el orquestador con las dos memorias. La imagen se construye con `uv` y el SQLite vive en un volumen de Docker.

| Endpoint | Qué hace |
|---|---|
| `GET /health` | Estado y proveedor de LLM activo |
| `POST /query` | Consulta con memoria volátil |
| `POST /query-memory` | Consulta con memoria persistente; `thread_id` derivado del email |
| `GET /state?thread_id=...` o `?email=...` | Historial del hilo (últimos 10 mensajes); `memoria=volatil` para la RAM |

Correr local:

```bash
uv run uvicorn main:app --reload --port 8000
```

Correr en container:

```bash
docker compose up --build -d
docker compose ps        # STATUS debe mostrar (healthy)
```

Probar (igual en local o en container):

```bash
# 1. Health
curl http://localhost:8000/health

# 2. Volatil: la primera respuesta devuelve un thread_id; reutilizalo para mantener contexto
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "Que productos hay en stock?"}'

# 3. Persistente con email (el thread_id sale del hash del email, siempre el mismo)
curl -X POST http://localhost:8000/query-memory \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "Consulta el CUIT 30712345678", "email": "consultas@castelar.com"}'

# 4. Seguimiento en el mismo hilo (usa el thread_id devuelto, o el mismo email)
curl -X POST http://localhost:8000/query-memory \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "En que localidad esta esa empresa?", "email": "consultas@castelar.com"}'

# 5. Historial: por thread_id o por email (memoria persistente por defecto)
curl "http://localhost:8000/state?thread_id=<thread_id>"
curl "http://localhost:8000/state?email=consultas@castelar.com"
curl "http://localhost:8000/state?thread_id=<thread_id>&memoria=volatil"
```

La documentación interactiva queda en http://localhost:8000/docs.

## Tests

Los tests de `/query-memory` no llaman a ningún LLM real ni a la red, así que no necesitan keys en el `.env`:

- Un LLM falso reemplaza a `obtener_llm`. Responde `"[n] <pregunta>"`, donde `n` es la cantidad de mensajes humanos que vio. Si `n` sube en cada turno, el hilo conserva su historial.
- El router falso elige el agente por palabra clave: `cuit` va a `fiscal`, `stock` a `datos`, `internet` a `web` y el resto a `general`.
- Cada test usa un SQLite temporal, así que `data/agent.sqlite.db` no se modifica.

| Test | Qué verifica |
|---|---|
| `test_hilo_por_email_mantiene_ruta_y_llega_a_end` | 3 turnos con el mismo email: mismo `thread_id`, ruta esperada en cada turno, grafo termina en END y `/state` devuelve el historial |
| `test_thread_id_tiene_prioridad_sobre_email` | Si llegan `thread_id` y `email`, gana `thread_id` |
| `test_hilo_sobrevive_reinicio_de_la_app` | La memoria persistente sobrevive a reiniciar la app |
| `test_hilos_distintos_no_se_mezclan` | Emails distintos tienen historiales separados |

Correr los tests:

```bash
uv sync                                    # instala pytest (dependencia de desarrollo)
uv run pytest -q                           # todos los tests
uv run pytest -v tests/test_query_memory.py                                   # un archivo, con el nombre de cada test
uv run pytest -v -k test_hilo_por_email_mantiene_ruta_y_llega_a_end           # un solo test
```

## Notas finales

- Verificá los nombres de modelo (`gemini-2.5-flash`, `command-a-03-2025`) contra tu cuenta. Ambos se pueden sobrescribir con `GENAI_MODEL` y `COHERE_MODEL`.
- El `.env` nunca entra en la imagen (`.dockerignore`). Se pasa al correr con `env_file` o `--env-file`.
- `docker compose down -v` borra el volumen `memoria`, y con él toda la memoria persistente.
- Un hash de email como `thread_id` es predecible: quien conozca el email puede leer ese historial en `/state`. Si la API es pública, agregá autenticación o usá un UUID aleatorio.
