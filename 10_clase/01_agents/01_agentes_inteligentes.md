# Agente con tools y orquestador

### 1.1 Las tres tools (`tools.py`)

**Qué se hace:** se definen tres funciones que el LLM puede invocar:

| Tool | Fuente de datos |
|---|---|
| `buscar_datos_internos` | Archivo `datos.json` (base simulada) |
| `buscar_web` | DuckDuckGo |
| `consultar_cuit` | API REST de Supabase (tabla de CUIT) |

**Teoría:** el *tool calling* funciona así:

1. El modelo no ejecuta código. Recibe la descripción de cada tool (nombre, docstring y parámetros) y, si le sirve una, responde con una llamada estructurada: "usá `consultar_cuit` con `cuit=3071...`".
2. El runtime ejecuta la función de verdad.
3. El resultado vuelve al modelo como un mensaje de tipo `ToolMessage`.
4. El modelo lo lee y redacta la respuesta final.

Por eso el **docstring es parte del prompt**: es lo que el modelo usa para decidir cuándo llamar a cada tool. Las tools devuelven errores como texto en lugar de lanzar excepciones, para que el modelo pueda explicarlos al usuario sin romper el flujo.

### 1.2 Agente individual (`crear_agente_simple`)

**Qué se hace:** un único agente que tiene las tres tools y decide cuál usar.

**Teoría:** `create_react_agent` implementa el patrón **ReAct** (Reason + Act), un ciclo que se repite hasta tener la respuesta:

```
Pensar -> ¿necesito una tool? -> Sí: ejecutarla -> observar el resultado -> volver a pensar
                              -> No: responder
```

Es un grafo de dos nodos, el LLM y el ejecutor de tools, con una arista condicional entre ellos. Es simple, pero un solo agente con muchas tools tiende a confundirse a medida que crece.

### 1.3 Orquestador multiagente (`crear_orquestador`)

**Qué se hace:** un nodo **router** lee la consulta y la deriva a uno de cuatro destinos. Tres son subagentes especializados, cada uno con una sola tool, y el cuarto es un nodo `general` para saludos.

```
START -> router -> fiscal  (consultar_cuit)
                -> datos   (buscar_datos_internos)
                -> web     (buscar_web)
                -> general (sin tools)
                      -> END
```

**Teoría:**
- Es el patrón **router / supervisor**. Separar responsabilidades da prompts más cortos, menos tools por agente y menos errores de selección.
- `with_structured_output(Ruta)` obliga al LLM a responder con un esquema Pydantic (`Literal["fiscal", "datos", "web", "general"]`). Es más robusto que parsear texto libre con `if "fiscal" in respuesta`.
- `add_conditional_edges` es la arista que lee `estado["ruta"]` y decide el siguiente nodo.
- El estado hereda de `MessagesState`, que acumula mensajes con el reducer `add_messages`. Ese reducer agrega mensajes sin duplicarlos por ID.


