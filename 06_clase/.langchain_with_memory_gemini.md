# Guía Integral de LangChain, LCEL, Tools y Memory con Gemini 2.5 Flash

Esta guía unifica todos los conceptos fundamentales del ecosistema LangChain y **LCEL (LangChain Expression Language)**, integrando ejemplos prácticos ejecutados con el modelo **Gemini 2.5 Flash** a través del SDK oficial de Google y la capa gratuita.

---

## Parte 1: Conceptos Fundamentales

LangChain modulariza el desarrollo con modelos de lenguaje mediante sintaxis declarativa, optimizando desde la gestión de contextos hasta el uso de herramientas externas.

### 1. LangChain

Framework para construir aplicaciones orientadas a datos y agentes basados en LLMs sin gestionar peticiones HTTP manuales.

* **Abstracción:** Estandariza la interfaz de proveedores (Google Gemini, OpenAI, Anthropic, Ollama) y bases de datos vectoriales.
* **Componentes Clave:** Prompts, LLMs, Retrievers, Tools y Parsers de salida.

### 2. LCEL (LangChain Expression Language) y la Interfaz `Runnable`

Es el lenguaje declarativo que conecta componentes mediante el operador tubería (`|`). Reemplaza las cadenas heredadas (`LLMChain`) unificando todo bajo el protocolo estándar **`Runnable`**.

#### Métodos del protocolo `Runnable`:

| Método | Tipo | Descripción |
| --- | --- | --- |
| **`invoke(input)`** | Sincrónico | Procesa una única entrada y retorna el resultado. |
| **`ainvoke(input)`** | Asincrónico | Versión asíncrona de `invoke` para servidores de alto rendimiento. |
| **`stream(input)`** | Sincrónico | Transmite la respuesta en tiempo real (*chunks*) a medida que se genera. |
| **`astream(input)`** | Asincrónico | Transmisión asíncrona de tokens. |
| **`batch(inputs)`** | Sincrónico | Procesa una lista de entradas de forma concurrente. |
| **`abatch(inputs)`** | Asincrónico | Procesamiento por lotes asíncrono. |

### 3. Tools (Herramientas)

Funciones Python que el LLM puede decidir ejecutar cuando necesita capacidades externas (cálculos matemáticos, búsquedas web, APIs).

* **Mecanismo:** La descripción y la firma de la función se convierten en un esquema JSON que el modelo analiza para decidir si invoca la herramienta.

### 4. Memory (Memoria)

Gestión del historial conversacional dentro del flujo LCEL. Se implementa envolviendo la cadena básica en un manejador de historial como `RunnableWithMessageHistory`.

---

## Parte 2: Profundización en LCEL

### Capacidades y Posibilidades Clave

1. **Streaming Nativo ("First-Token Latency"):** Transmite respuestas directamente al usuario token por token sin esperar a que finalice toda la tubería.
2. **Ejecución Paralela Autogestionada:** Los pasos independientes dentro del flujo se ejecutan en paralelo automáticamente.
3. **Manejo de Errores y Redundancia (Fallbacks):** Permite definir modelos o cadenas secundarias en caso de fallos de red, límites de cuota o timeouts.
4. **Configuración Dinámica (`bind` y `configurable`):** Modifica parámetros en tiempo de ejecución (como `temperature` o `stop_sequences`) sin reconstruir la tubería.
5. **Observabilidad Autenticada:** Integración nativa con LangSmith para trazar latencia, tokens, entradas y salidas de cada nodo.

### Primitivas Clave de LCEL

* **`RunnablePassthrough`**: Transmite la entrada intacta al siguiente paso (esencial en RAG para conservar la pregunta original).
* **`RunnableLambda`**: Convierte cualquier función Python regular en un nodo ejecutable de LCEL.
* **`RunnableParallel`**: Ejecuta un mapa de funciones en paralelo y combina las salidas en un diccionario.
* **`.with_fallbacks()`**: Agrega mecanismos de conmutación por error a cualquier `Runnable`.

### Pros y Contras de LCEL

* **Ventajas:** Sintaxis declarativa y limpia, rendimiento optimizado, modularidad tipo "Lego" y consistencia de métodos entre llamadas síncronas, asíncronas y lotes.
* **Desventajas:** Curva de aprendizaje al pensar en flujos de datos entre diccionarios, y dificultad para representar bucles cíclicos complejos.

### ¿Cuándo usar LCEL vs. LangGraph?

* **Usa LCEL cuando:** Necesites cadenas lineales o paralelizadas, flujos RAG, transformación de datos o pipelines acíclicos dirigidos (DAGs).
* **Usa LangGraph cuando:** Necesites **agentes con estado (*Stateful Agents*)**, bucles de retroalimentación donde el modelo reintente el uso de herramientas, o arquitecturas multi-agente.

---

## Parte 3: Ejercicios Prácticos con Gemini 2.5 Flash

### Requisitos Previos

Instala las librerías necesarias ejecutando:

```bash
pip install langchain-core langchain-google-genai langchain-community

```

Obtén tu API Key gratuita desde [Google AI Studio](https://aistudio.google.com/) y configúrala como variable de entorno o directamente en la variable `GOOGLE_API_KEY`.

---

### Ejercicio 1: Pipeline LCEL Completo (Tools + Memoria con Gemini 2.5 Flash)

Este script combina una herramienta personalizada (`tool`), historial por sesión (`memory`) y la invocación declarativa del modelo **Gemini 2.5 Flash**.

```python
import os
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI

# Configuración de la API Key de Google (Capa Gratuita)
os.environ["GOOGLE_API_KEY"] = "TU_API_KEY_DE_GOOGLE"

# 1. TOOL: Definición de herramienta personalizada
@tool
def multiplicar(a: float, b: float) -> float:
    """Multiplica dos números float y retorna el resultado."""
    return a * b

tools = [multiplicar]

# 2. MODELO CON GEMINI 2.5 FLASH + BIND DE HERRAMIENTAS
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
llm_with_tools = llm.bind_tools(tools)

# 3. PROMPT CON PLACEHOLDER DE MEMORIA
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres un asistente analítico preciso."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# 4. PIPELINE LCEL
chain = prompt | llm_with_tools

# 5. MEMORIA: Almacén conversacional por sesión
store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

app = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history"
)

# EJECUCIÓN CON TRAZABILIDAD
config = {"configurable": {"session_id": "sesion_demo"}}

# Turno 1: Guarda contexto en la memoria de la sesión
res1 = app.invoke({"input": "Hola, mi presupuesto base es 500 dólares."}, config=config)
print("Respuesta 1:", res1.content)

# Turno 2: Recupera el contexto de memoria e identifica la herramienta a usar
res2 = app.invoke({"input": "¿Cuánto sería mi presupuesto si lo multiplico por 3.5?"}, config=config)

if res2.tool_calls:
    print("\nHerramienta detectada por Gemini 2.5 Flash:", res2.tool_calls[0]["name"])
    print("Argumentos extraídos:", res2.tool_calls[0]["args"])
else:
    print("\nRespuesta 2:", res2.content)

```

---

### Ejercicio 2: Flujo Avanzado de LCEL (Paralelización, Lambda, Fallbacks y Streaming)

Demostración de capacidades avanzadas de LCEL utilizando Gemini 2.5 Flash con respuesta transmitida en tiempo real (*streaming*).

```python
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_google_genai import ChatGoogleGenerativeAI

os.environ["GOOGLE_API_KEY"] = "TU_API_KEY_DE_GOOGLE"

# 1. MODELO PRINCIPAL Y MODELO DE RESPALDO (FALLBACK)
primary_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
fallback_model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

model_with_fallback = primary_model.with_fallbacks([fallback_model])

# 2. FUNCION CUSTOM (RunnableLambda)
def contar_palabras(texto: str) -> int:
    """Función Python regular integrada en el pipeline LCEL."""
    return len(texto.split())

nodo_contador = RunnableLambda(contar_palabras)

# 3. PROMPTS
prompt_resumen = ChatPromptTemplate.from_template(
    "Haz un resumen conciso del siguiente texto en 2 oraciones:\n\n{texto}"
)

prompt_final = ChatPromptTemplate.from_template(
    "Texto Original (Largo): {longitud_original} palabras.\n"
    "Resumen: {resumen}\n\n"
    "Escribe un breve comentario analítico sobre el resumen anterior."
)

parser = StrOutputParser()

# 4. CONSTRUCCIÓN DEL PIPELINE LCEL
cadena_resumen = prompt_resumen | model_with_fallback | parser

# Ejecución en Paralelo
preparacion_datos = RunnableParallel(
    {
        "resumen": cadena_resumen,
        "longitud_original": nodo_contador
    }
)

# Ensamblado Final
cadena_completa = preparacion_datos | prompt_final | model_with_fallback | parser

# 5. EJECUCIÓN CON STREAMING
texto_ejemplo = """
La inteligencia artificial generativa ha experimentado un avance acelerado en los últimos años.
Los modelos de lenguaje de gran tamaño (LLM) han demostrado capacidades sorprendentes en tareas de
procesamiento de lenguaje natural, razonamiento lógico y generación de código. Sin embargo, su integración
en entornos de producción exige arquitecturas sólidas que garanticen latencia controlada, observabilidad
y tolerancia a fallos ante caídas de proveedores externas.
"""

print("--- EJECUTANDO CADENA LCEL CON GEMINI 2.5 FLASH (STREAMING) ---\n")

for chunk in cadena_completa.stream(texto_ejemplo):
    print(chunk, end="", flush=True)

print("\n\n--- FIN DE LA EJECUCIÓN ---")

```