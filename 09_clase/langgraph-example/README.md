# Clase 09 — Agentes con LangGraph + Gemini

Ejemplos prácticos de [`../agents.md`](../agents.md) sobre el dominio OrTelana (el mismo de las clases 07 y 08).

## De la clase 08 a la clase 09

`08_clase/langsmith-ejemplo/langsmith_eval.py` es una **cadena**: cada pregunta recorre siempre el mismo camino.

```text
pregunta -> recuperar_chunks (Chroma + rerank) -> prompt -> Gemini -> respuesta
```

Esa cadena no tiene router ni herramientas, y no usa LangGraph. El LLM nunca decide nada: solo redacta.
En esta carpeta el LLM **decide** qué herramienta usar, con qué argumentos y cuándo terminar.

| Script | Patrón | Qué muestra |
|---|---|---|
| `01_agente_react.py` | Un agente ReAct | `bind_tools`, `ToolNode`, arista condicional, varias tools en paralelo, memoria con `thread_id`, `recursion_limit` |
| `02_router_multiagente.py` | Router + subagentes | Clasificación con structured output, subgrafos como nodos, rama sin LLM para fuera de dominio |
| `03_eval_trayectoria.py` | Evaluación | Tool selection, tools prohibidas, pasos, quality gate con exit code |

## Archivos

```text
langgraph-example/
├── data/ortelana_db.json   # "base de datos": productos, stock por sucursal, pedidos, políticas
├── tools.py                # las 6 herramientas (@tool) con docstrings para el LLM
├── react.py                # LLM Gemini + constructor del grafo ReAct + impresión de trayectoria
├── 01_agente_react.py
├── 02_router_multiagente.py
└── 03_eval_trayectoria.py
```

## Herramientas

| Tool | Fuente | Tipo |
|---|---|---|
| `buscar_productos(categoria, solo_con_stock, precio_max_metro)` | JSON | lectura |
| `consultar_stock(producto_id, sucursal)` | JSON | lectura |
| `consultar_estado_pedido(numero_pedido)` | JSON | lectura, valida formato `PED-NNNN` |
| `crear_ticket_soporte(numero_pedido, motivo)` | memoria | **acción con efecto** |
| `buscar_politica_interna(tema)` | JSON | conocimiento documental ("RAG como tool") |
| `buscar_web(consulta, max_resultados)` | DuckDuckGo (`ddgs`) | externa, no requiere API key |

Decisiones de diseño (ver la sección "Cómo el modelo elige una herramienta" de `agents.md`):

- Las tools son **de dominio**, por ejemplo `consultar_estado_pedido(numero_pedido)`. No existe una tool genérica `ejecutar_query(query)`.
- Los docstrings dicen **cuándo usar** cada tool y **cuándo no usarla**.
- `Literal[...]` limita sucursales, categorías y temas a valores válidos.
- Cada tool devuelve JSON. Ante un error devuelve `{"error": ...}` con un mensaje accionable, así el agente puede corregir los argumentos.
- `buscar_web` marca su resultado como contenido externo no confiable. Es una defensa básica contra prompt injection.

## Setup

```bash
cd 09_clase/langgraph-example
cp .env.sample .env      # completar GOOGLE_API_KEY (la misma de la clase 08)
uv sync
```

## Ejecutar

```bash
# 1. Agente ReAct
uv run python 01_agente_react.py                 # preguntas demo + demo de memoria
uv run python 01_agente_react.py --pregunta "¿Qué linos tienen stock?"
uv run python 01_agente_react.py --chat          # conversación con memoria
uv run python 01_agente_react.py --grafo         # Mermaid, pegar en https://mermaid.live

# 2. Router + subagentes
uv run python 02_router_multiagente.py
uv run python 02_router_multiagente.py --grafo   # incluye los subgrafos (xray)

# 3. Evaluación de trayectoria
uv run python 03_eval_trayectoria.py
```

Ejemplo real de la salida de `01_agente_react.py`:

```text
USUARIO: ¿Hay frisa invisible en Buenos Aires? Si no, ¿dónde hay?
  (agente) [ACT]     buscar_productos({"solo_con_stock": false, "categoria": "punto"})
  (herramientas) [OBSERVE] buscar_productos -> {"productos": [... "TEL-006" ...]}
  (agente) [ACT]     consultar_stock({"producto_id": "TEL-006"})
  (herramientas) [OBSERVE] consultar_stock -> {"stock_metros": {"Buenos Aires": 0, "Córdoba": 25, "Rosario": 0}}
  (agente) [FINAL]   No hay stock en Buenos Aires. Hay 25 metros en Córdoba.
```

El agente no conocía el id `TEL-006`. Primero lo buscó y después lo usó: eso es el ciclo ReAct.

## Qué observar en clase

1. **Tools en paralelo.** La pregunta sobre devolución de `PED-1003` genera 2 `tool_calls` en el mismo `AIMessage`: `buscar_politica_interna` y `consultar_estado_pedido`. `ToolNode` ejecuta las dos.
2. **Dato faltante.** Con "¿Ya despacharon mi pedido?" el agente pide el número. No lo inventa.
3. **Memoria.** En el segundo turno, "ese pedido" se resuelve porque los dos turnos comparten `thread_id` en el `InMemorySaver`.
4. **Límite del router.** La pregunta mixta de `02` (precio en OrTelana y precio en la competencia) va a un solo subagente, así que una parte queda sin responder. Ese es el motivo del patrón orquestador-trabajadores.
5. **Fuera de dominio.** Esa rama no llama al LLM. Tiene costo cero y es determinista.

## Ejercicios propuestos

- Quitar del docstring de `buscar_web` la frase "NO usar para stock". Correr `03_eval_trayectoria.py` y comparar `sin_prohibidas`.
- Bajar `RECURSION_LIMIT=2` en `.env` y observar el corte seguro (`GraphRecursionError`).
- Pedir confirmación humana antes de `crear_ticket_soporte`. Usar `interrupt()` de LangGraph o `interrupt_before=["herramientas"]` en `compile`.
- Agregar la ruta `mixta` al router con un nodo que llame a los dos subagentes y consolide las respuestas.
- Reemplazar `buscar_politica_interna` por el retriever de Chroma de la clase 08. El resultado es un RAG real usado como tool.
- Activar `LANGSMITH_TRACING=true` y ver en LangSmith el árbol `agente -> herramientas -> agente` de cada pregunta.
- Cambiar Gemini por Ollama en `crear_llm()` (`ChatOllama(model="llama3.2")`). Medir con `03` si un modelo chico elige peor las tools.

## Otros detalles sobre LangGraph

Además del patrón **ReAct** (el bucle clásico de *Modelo ➔ Herramienta ➔ Modelo*), en LangGraph y LangChain puedes construir y coordinar múltiples **patrones de diseño de agentes**, clasificados según su lógica de razonamiento o su arquitectura de colaboración.

---

## Patrones de Agente Único (*Single-Agent Patterns*)

* **Plan-and-Execute (Planificación y Ejecución):** Un agente que primero genera un plan de varios pasos antes de actuar. A medida que ejecuta las herramientas para cada paso, un nodo planificador evalúa el progreso y reajusta el plan dinámicamente si algo falla o cambia el contexto.
* **Reflection / Self-Correction (Reflexión y Autocorrección):** Utilizado en patrones como *Reflexion*, *Self-RAG* o *CRAG*. Un nodo genera la respuesta o código, mientras que un nodo "crítico" (o evaluador) audita el resultado buscando alucinaciones o errores. Si detecta fallos, el estado regresa al generador con retroalimentación para corregirlo antes de responder.
* **LLM Compiler (Llamadas en Paralelo):** Un patrón donde el modelo analiza la consulta y planifica todas las llamadas a herramientas que se pueden realizar de forma simultánea en lugar de ejecutarlas en secuencia, optimizando enormemente la latencia.
* **Human-in-the-Loop (Con Aprobación Humana):** Agentes que pausan la ejecución del grafo (mediante `interrupt_before` o middlewares) justo antes de realizar una acción destructiva o sensible (como modificar una base de datos o enviar un correo) para esperar la confirmación o corrección de un usuario.

---

## Arquitecturas Multi-Agente (*Multi-Agent Systems*)

LangGraph destaca por su capacidad de conectar múltiples agentes especializados como nodos dentro del mismo grafo:

* **Supervisor (Orquestador y Especialistas):** Un agente "mánager" recibe la solicitud inicial y decide a qué agente especialista delegar el trabajo (`AgenteInvestigador`, `AgenteRedactor`, `AgenteCodificador`). Cada sub-agente ejecuta sus herramientas y devuelve la respuesta al supervisor para consolidar o redirigir.
* **Handoffs / Swarm (Transferencia Directa):** Los agentes se pasan el control el uno al otro directamente según el contexto, sin necesidad de un supervisor central. Por ejemplo, un agente de atención al cliente puede realizar un *handoff* directo al agente de ventas si detecta intención de compra.
* **Colaboración / Red (*Peer-to-Peer*):** Dos o más agentes interactúan entre sí en un bucle cerrado (por ejemplo, un programador y un tester que revisa el código en un ciclo hasta que pase los tests) antes de devolver el resultado al usuario.
* **Jerárquico (*Hierarchical Agent Systems*):** Estructura en árbol donde un supervisor principal coordina a supervisores de departamento, y cada uno maneja su propio equipo de agentes especializados.

---

## Ampliación mediante Middleware (*Deep Agents*)

Con la función `create_agent` de LangChain (construida sobre la infraestructura de LangGraph), puedes tomar el bucle estándar y extender sus capacidades agregando **Middlewares** sin cambiar la estructura del grafo:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, SummarizationMiddleware

agente_avanzado = create_agent(
    model="gemini-2.0-flash",
    tools=[herramientas_sensibles],
    system_prompt="Sos un asistente administrativo.",
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on=["transferir_fondos"]),  # Pausa previa a la herramienta
        SummarizationMiddleware(max_tokens=4000),                      # Resume automáticamente el historial
    ],
    checkpointer=memory
)

```

En resumen: **ReAct** es la pieza básica para usar herramientas, pero con LangGraph puedes combinar esos bloques para construir sistemas con memoria profunda, auto-evaluación y redes de sub-agentes especializados.
