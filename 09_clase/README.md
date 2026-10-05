# Clase 9: Agentes Inteligentes — Tool Use, Function Calling y LangGraph

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial

**Objetivo Técnico:** Comprender la diferencia entre una cadena RAG y un agente inteligente, comprender la arquitectura del patrón ReAct con LangGraph dotando al agente de herramientas, y analizar cómo el LLM decide qué herramienta usar y cuándo.

---
## Bloque 1: De la Cadena al Agente

### El límite del RAG para casos complejos

Un sistema RAG tradicional recupera fragmentos de documentos estáticos mediante búsqueda semántica y genera una respuesta directa. Sin embargo, no puede ejecutar acciones en tiempo real ni interactuar con sistemas externos (bases de datos SQL, API institucionales, inventarios dinámicos).

**Diferencia clave de comportamiento:**

* **Cadena (Chain):** Ejecuta una secuencia fija y predefinida de pasos en un orden estático (ej: Consulta -> VectorDB -> Prompt -> LLM).
* **Agente:** Un sistema en el que el LLM actúa como un motor de razonamiento que decide dinámicamente en tiempo de ejecución qué acciones tomar, en qué orden y con qué parámetros, basándose en la observación continua del entorno.

```
Cadena:  [Entrada] ───► [Paso 1] ───► [Paso 2] ───► [Salida]

Agente:  [Entrada] ───► [LLM Razona] ───► [Decide Acción] ───► [Observa Resultado]
                            ▲                                          │
                            └──────────────────────────────────────────┘

```

---

### El patrón ReAct — Reason, Act, Observe

El ciclo ReAct (Reasoning + Acting) formaliza la ejecución de un agente a través de tres pasos iterativos:

1. **Reason (Pensamiento):** El modelo evalúa la consulta actual y los resultados previos para determinar qué información falta.
2. **Act (Acción):** Selecciona una herramienta específica y genera los parámetros de entrada estructurados para invocarla.
3. **Observe (Observación):** Recibe y analiza el resultado retornado por la ejecución de la herramienta.

```
┌─────────────────────────────────────────────┐
│                CICLO ReAct                  │
│                                             │
│  Thought: "¿Qué necesito para responder?"  │
│      │                                      │
│      ▼                                      │
│  Action: elegir herramienta + parámetros   │
│      │                                      │
│      ▼                                      │
│  Observation: resultado de la herramienta  │
│      │                                      │
│      ▼                                      │
│  ¿Tengo suficiente info? ──No──► volver    │
│      │ Sí                                   │
│      ▼                                      │
│  Final Answer: respuesta al usuario        │
└─────────────────────────────────────────────┘

```

**Control de Ejecución:** Para evitar bucles infinitos causados por herramientas que devuelven respuestas ambiguas o errores no manejados, los entornos de producción deben configurar un límite estricto de iteraciones (`recursion_limit` o `max_iterations`) y condiciones de parada explícitas.

---

## Bloque 2: Tool Use y Function Calling

### Cómo el LLM decide qué herramienta usar

El LLM no ejecuta código fuente de manera directa. En su lugar, mediante *Function Calling*, genera un objeto JSON o diccionario estructurado con el nombre de la función y las claves/valores correspondientes a sus argumentos.

El orquestador intercepta esta intención, ejecuta la función real en el entorno de aplicación y retorna el resultado en un mensaje de tipo herramienta (`ToolMessage`) al modelo.

```
[LLM] ──(Genera JSON de llamada)──► [Orquestador/LangGraph]
                                           │
                                     (Ejecuta función)
                                           │
[LLM] ◄──(Recibe resultado real)─── [Código Python]

```

---

### La importancia de la interfaz de la Tool

La selección correcta de herramientas depende fundamentalmente de la **firma de la función** y la calidad de su **docstring**. El LLM evalúa las descripciones textuales para determinar la aplicabilidad de la herramienta según la consulta del usuario.

**Estructura técnica de una definición de Tool:**

```python
from langchain_core.tools import tool

@tool
def nombre_herramienta(parametro_a: str, parametro_b: str = "valor_defecto") -> str:
    """
    Descripción clara e inequívoca de la función de la herramienta.
    Expresa explícitamente cuándo debe y no debe ser utilizada por el modelo.

    Args:
        parametro_a: Explicación y formato esperado del parámetro.
        parametro_b: Explicación del parámetro opcional.

    Returns:
        Descripción de la estructura y tipo de información devuelta.
    """
    # Lógica interna de ejecución
    ...

```

---

## Bloque 3: Arquitectura del Agente con LangGraph

LangGraph modela el comportamiento del agente mediante un **Grafo Acíclico Dirigido con Ciclos (DAG/Graph)**, compuesto por tres elementos esenciales:

1. **Estado (`State`):** Estructura de datos centralizada que se transmite entre los nodos y acumula el historial de mensajes e información contextualmente relevante.
2. **Nodos (`Nodes`):** Funciones o ejecutores que reciben el estado actual, realizan transformaciones y devuelven un estado actualizado.
3. **Aristas (`Edges`):** Reglas que conectan los nodos. Pueden ser directas o condicionales (enrutamiento dinámico).

---

### Componentes Técnicos de un Grafo ReAct

#### 1. Definición del Estado

El estado debe permitir la acumulación continua del historial conversacional mediante operadores de agregación (por ejemplo, `operator.add`).

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class EstadoAgente(TypedDict):
    # Acumula los mensajes a lo largo de las iteraciones del grafo
    messages: Annotated[Sequence[BaseMessage], operator.add]

```

#### 2. Definición de Nodos

* **Nodo Agente:** Vincula el modelo de lenguaje con la lista de herramientas permitidas (`bind_tools`) e invoca al LLM pasando el historial.
* **Nodo Herramientas:** Instancia preseteada (`ToolNode`) encargada de ejecutar las llamadas a las funciones requeridas por el modelo.

#### 3. Aristas Condicionales (Toma de Decisiones)

La función condicional evalúa si el último mensaje emitido por el LLM incluye solicitudes de herramientas (`tool_calls`). Si existen, redirige el flujo al nodo de herramientas; si no, finaliza el proceso (`END`).

```python
from langgraph.graph import END

def debe_continuar(estado: EstadoAgente) -> str:
    ultimo_mensaje = estado["messages"][-1]
    if hasattr(ultimo_mensaje, "tool_calls") and ultimo_mensaje.tool_calls:
        return "usar_herramienta"
    return END

```

#### 4. Diagrama de Ensamblado del Grafo

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# Inicialización con el esquema de estado
grafo = StateGraph(EstadoAgente)

# Configuración de Nodos
grafo.add_node("agente", nodo_agente)
grafo.add_node("herramientas", ToolNode(TOOLS))

# Definición de Flujos y Aristas
grafo.set_entry_point("agente")

grafo.add_conditional_edges(
    "agente",
    debe_continuar,
    {
        "usar_herramienta": "herramientas",
        END: END
    }
)

# Retorno automático tras la observación
grafo.add_edge("herramientas", "agente")

# Compilación de la aplicación ejecutable
agente_compilado = grafo.compile()

```

---

## Bloque 4: Multiagente y Ollama

### Arquitectura Multiagente

Cuando un dominio operativo escala, incluir demasiadas herramientas dentro de un único agente degrada el rendimiento de selección del LLM. La solución consiste en fragmentar el sistema en subagentes especializados bajo la coordinación de un **Orquestador (Router)**.

```
                    ┌─────────────────┐
    Consulta ──────►│   Orquestador   │
                    │  (Router LLM)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │ Subagente A  │ │Subagente │ │ Subagente C  │
    │  (Dominio 1) │ │ B (Dom.2)│ │  (Dominio 3) │
    └──────────────┘ └──────────┘ └──────────────┘

```

* **Subagentes Especializados:** Poseen un conjunto reducido y coherente de herramientas específicas.
* **Orquestador:** Analiza la solicitud general, clasifica la intención primaria, redirige el flujo hacia el subagente correspondiente y consolida la respuesta final.

---

### Inferencia Local con Ollama

El uso de un runtime local de LLMs como **Ollama** permite desacoplar la lógica del agente respecto a proveedores en la nube.

* **Compatibilidad:** Se integra como reemplazo del modelo en la inicialización, conservando la totalidad de la estructura del grafo LangGraph y la firma de las herramientas.
* **Ventajas Técnicas:** Privacidad de datos en red local, ausencia de costos por volumen de tokens y desarrollo offline.

```python
from langchain_ollama import ChatOllama

# Sustitución transparente del modelo mantención de bind_tools
llm_local = ChatOllama(model="llama3.2", temperature=0)
llm_local_con_tools = llm_local.bind_tools(TOOLS)

```

---

## Resumen Conceptual y Cierre

1. **Diferenciación Cadena vs. Agente:** Las cadenas tienen flujos deterministas; los agentes deciden dinámicamente sus pasos mediante el ciclo ReAct (Reason, Act, Observe).
2. **Sistemas de Herramientas:** Las descripciones detalladas (docstrings) de las herramientas definen el comportamiento de selección del LLM.
3. **Modelado en LangGraph:** Los agentes se estructuran mediante grafos de estado donde los nodos procesan información, las herramientas devuelven observaciones y las aristas condicionales dirigen el control de flujo.
4. **Evolución Arquitectónica:** Proyectos complejos requieren segmentación en arquitecturas multiagente y memoria de estado persistente entre sesiones conversacionales.

---

## Bibliografía

* **Yao, S., et al. (2022).** *ReAct: Synergizing Reasoning and Acting in Language Models.* arXiv:2210.03629.
* **LangGraph Documentation.** *Graphs, Nodes, Edges and State Management.* langchain-ai.github.io/langgraph
* **Russell, S., & Norvig, P. (2021).** *Artificial Intelligence: A Modern Approach.* (4th ed.). Capítulo 2: Intelligent Agents.
