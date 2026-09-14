# Guía Completa y Práctica de LangChain (Edición 2026)

## Parte 1: Marco Teórico

### 1.1 Introducción a LangChain y Necesidad en el Ecosistema Actual
LangChain es un framework de código abierto distribuido bajo la licencia MIT diseñado para simplificar la construcción de aplicaciones avanzadas basadas en grandes modelos de lenguaje (LLMs), pipelines de Recuperación Aumentada por Generación (RAG) y agentes autónomos de Inteligencia Artificial.

#### ¿Por qué es necesario utilizar LangChain?
1. **Abstracción de la Complejidad**: Integrar múltiples proveedores de modelos de lenguaje, gestionar el estado o memoria de las conversaciones, construir flujos de trabajo complejos y conectar herramientas externas resulta laborioso sin un estándar común. LangChain abstrae estas capas mediante componentes modulares reutilizables.
2. **Orquestación Cohesiva**: En arquitecturas RAG, el framework unifica la ingesta de información, la generación de embeddings, el almacenamiento vectorial, la recuperación de contexto relevante y el ensamblaje de prompts para la generación final.
3. **Estandarización mediante la Interfaz Runnable**: Todos los componentes fundamentales de LangChain implementan la interfaz `Runnable`, permitiendo una composición uniforme de tuberías de datos (pipelines) a través del operador pipe (`|`).
4. **Preparación para Entornos de Producción**: Incluye características nativas esenciales para sistemas distribuidos y de alta demanda, como soporte para streaming de respuestas, procesamiento en lote (*batching*), ejecución asíncrona no bloqueante y capacidad de observabilidad/monitoreo integrado a través de herramientas como LangSmith.

---

### 1.2 Arquitectura y LangChain Core (`langchain-core`)
A partir de la evolución modular del ecosistema, el núcleo del framework se concentra en el paquete `langchain-core`. Este paquete contiene las abstracciones fundamentales sin dependencias pesadas de terceros:
* **Prompts**: `PromptTemplate`, `ChatPromptTemplate` para la estructuración dinámica del contexto de entrada.
* **Modelos**: Interfaces base para LLMs y Chat Models (`BaseChatModel`, `BaseLanguageModel`).
* **Parsers de Salida**: `StrOutputParser`, `JsonOutputParser`, estructuración de la respuesta generada por el modelo.
* **Retrievers**: Interfaces estándar para la búsqueda y recuperación de documentos relevantes.
* **Interfaz Runnable**: Protocolo unificado de ejecución.

Los paquetes de integraciones específicas se instalan de forma independiente para mantener arquitecturas ligeras:
* `langchain-google-genai`: Integración con los modelos Gemini de Google.
* `langchain-huggingface`: Soporte para modelos y embeddings de Hugging Face.
* `langchain-chroma`: Conector para la base de datos vectorial Chroma DB.
* `langchain-community`: Componentes mantenidos por la comunidad.

---

### 1.3 Retrieval-Augmented Generation (RAG): Conceptos y Arquitectura
La Recuperación Aumentada por Generación (RAG) es una arquitectura utilizada para enriquecer las respuestas de un LLM mediante el suministro de contexto específico extraído de fuentes de datos privadas o externas, evitando alucinaciones y limitaciones de ventana de contexto del entrenamiento base.

#### Etapas del Flujo RAG:
1. **Carga de Documentos (Document Loading)**: Importación de datos desde diversas fuentes (archivos PDF, texto plano, base de datos, páginas web).
2. **División de Texto (Text Splitting / Chunking)**: Segmentación de documentos extensos en fragmentos más pequeños (*chunks*) para optimizar el límite de tokens y la precisión de la búsqueda semántica.
3. **Generación de Embeddings y Vector Store**: Conversión de cada fragmento de texto en vectores numéricos densos mediante un modelo de embeddings y su posterior almacenamiento en una base de datos vectorial (*Vector Store*).
4. **Creación del Retriever**: Abstracción que recibe una consulta en lenguaje natural y retorna los $k$ fragmentos más relevantes del vector store según métricas de similitud (ej. similitud coseno).
5. **Construcción de la Cadena RAG**: Ensamblado mediante LCEL donde la consulta del usuario se combina con los documentos recuperados dentro de una plantilla de prompt para que el LLM genere la respuesta final.

---

### 1.4 Generación de Embeddings con Sentence Transformers
Los embeddings son representaciones vectoriales numéricas que capturan el significado semántico del texto. LangChain permite integrar modelos locales de Sentence Transformers mediante el paquete `langchain-huggingface`.

#### Modelos Destacados de Sentence Transformers:
* **`all-MiniLM-L6-v2`**: Modelo ultrarrápido y liviano (384 dimensiones), ideal para entornos con recursos reducidos o aplicaciones de baja latencia.
* **`all-mpnet-base-v2`**: Modelo de alta calidad y precisión semántica (768 dimensiones), recomendado para RAG general en inglés.
* **`multilingual-e5-large`**: Modelo avanzado multilingüe optimizado para representaciones semánticas en español y múltiples idiomas.

---

### 1.5 Integración con Google Generative AI (Gemini)
LangChain proporciona soporte oficial para la familia de modelos Gemini a través del paquete `langchain-google-genai`. Existen dos modalidades principales de integración:

1. **Google AI Studio (API Key)**:
   * Orientado a prototipado rápido y aplicaciones estándar.
   * Requiere una API Key obtenida directamente desde Google AI Studio.
   * Modelos disponibles principales: `gemini-2.5-flash` (alta velocidad y bajo costo) y `gemini-2.5-pro` (máximo razonamiento y capacidad analítica).

2. **Vertex AI en Google Cloud Platform (GCP)**:
   * Orientado a entornos empresariales y de producción.
   * Utiliza la infraestructura de GCP con autenticación por IAM, parámetros de región y cumplimiento normativo.

---

### 1.6 LangChain Expression Language (LCEL)
LCEL es la sintaxis declarativa introducida para componer cadenas (*chains*) de manera transparente y modular mediante el operador tubería (`|`), inspirado en las tuberías de Unix.

#### Principio de Funcionalidad y la Interfaz Runnable
Todos los componentes de LCEL implementan la interfaz `Runnable`. Esto significa que comparten una firma de métodos estandarizada:
* `invoke()`: Ejecución síncrona para una sola entrada.
* `stream()`: Retorno de la respuesta en tiempo real por fragmentos (*streaming*).
* `batch()`: Procesamiento síncrono en lote para múltiples entradas.
* `ainvoke()`, `astream()`, `abatch()`: Variantes asíncronas para programación concurrente de alto rendimiento.

#### Tabla de Componentes Clave de LCEL:
| Componente | Función | Ejemplo de Uso |
| :--- | :--- | :--- |
| **`PromptTemplate` / `ChatPromptTemplate`** | Formatea la entrada recibida | `ChatPromptTemplate.from_template("...")` |
| **`ChatGoogleGenerativeAI`** | Modelo de lenguaje de chat (LLM) | `ChatGoogleGenerativeAI(model="gemini-2.5-flash")` |
| **`StrOutputParser` / `JsonOutputParser`** | Extrae y parsea la respuesta | `StrOutputParser()` |
| **`Retriever`** | Búsqueda semántica en base vectorial | `vectorstore.as_retriever()` |
| **`RunnablePassthrough`** | Transfiere la entrada sin modificar | `RunnablePassthrough()` |
| **`RunnableParallel`** | Ejecución paralela de tareas | `RunnableParallel(context=..., question=...)` |
| **`format_docs`** | Función de transformación custom | `lambda docs: "\n".join([d.page_content for d in docs])` |

#### Ventajas de LCEL sobre Legacy Chains:
* **Legibilidad y Mantenibilidad**: Flujo explícito paso a paso sin cajas negras.
* **Streaming Nativo**: La tubería completa hereda la capacidad de streaming sin configuración adicional.
* **Soporte Asíncrono Completo**: Preparado para servidores web modernos (FastAPI, AsyncIO).
* **Composición Modular**: Las sub-cadenas creadas con LCEL pueden reutilizarse como bloques en cadenas más complejas.

#### Diferencia entre LCEL y LangGraph:
* **Usar LCEL**: Para cadenas secuenciales, transformaciones de datos y pipelines RAG con flujo de control directo (DAGs lineales).
* **Usar LangGraph**: Para agentes de IA complejos con ciclos, estado persistente, toma de decisiones dinámica o razonamiento multinodal.

---

### 1.7 Resumen y Recomendaciones de Stack Tecnológico (2026)
Para perfiles con experiencia en Node.js, Python, GCP y Backend Engineering:
* **Lenguaje**: Python 3.11+ para desarrollo de modelos y pipelines RAG en backend.
* **Core Framework**: `langchain-core` desacoplado.
* **Embeddings**: `HuggingFaceEmbeddings` con `all-mpnet-base-v2` o `multilingual-e5-large`.
* **LLM Engine**: `ChatGoogleGenerativeAI` (`gemini-2.5-flash` / `gemini-2.5-pro`).
* **Vector Store**: Chroma DB para entornos locales/desarrollo; BigQuery Vector Search o Vertex AI Vector Search para producción en GCP.
* **Orquestación**: LCEL para pipelines RAG y servicios deterministas; LangGraph para sistemas agénticos con estado.

## Parte 2: Guía Práctica y Ejercicios de Código

En esta sección se presentan ejemplos prácticos en Python desarrollados según los estándares de 2026. Cada ejercicio referencia directamente los conceptos teóricos abordados en la Parte 1.

---

### Requisitos Previos e Instalación de Dependencias
```bash
pip install langchain-core langchain-google-genai langchain-huggingface langchain-chroma sentence-transformers
```

---

### Ejercicio 1: Configuración Inicial e Integración Mínima con Gemini
*(Referencia Teórica: Sección 1.2 y Sección 1.5)*

En este ejercicio se muestra cómo inicializar el modelo `gemini-2.5-flash` usando `langchain-google-genai` e interactuar mediante tipos de mensajes estructurados (`SystemMessage` y `HumanMessage`).

```python
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# Configuración de API Key (se recomienda mediante variable de entorno GOOGLE_API_KEY)
API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")

# Inicialización del LLM (Sección 1.5)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=API_KEY,
    temperature=0.3
)

# Definición de mensajes estructurados (Sección 1.2)
messages = [
    SystemMessage(content="Eres un asistente especializado en arquitectura de software en la nube."),
    HumanMessage(content="¿Cuáles son las ventajas de desincorporar monolitos a microservicios?")
]

# Invocación directa del modelo
response = llm.invoke(messages)

print("--- Respuesta de Gemini 2.5 Flash ---")
print(response.content)
```

---

### Ejercicio 2: Generación de Embeddings con Sentence Transformers
*(Referencia Teórica: Sección 1.4)*

Demostración de la inicialización y uso de modelos de Sentence Transformers mediante `HuggingFaceEmbeddings` para obtener representaciones vectoriales densas.

```python
from langchain_huggingface import HuggingFaceEmbeddings

# Configuración del modelo de embeddings (Sección 1.4)
embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2",
    model_kwargs={"device": "cpu"},  # Cambiar a 'cuda' si se dispone de GPU
    encode_kwargs={"normalize_embeddings": True}
)

# Generación de vector para una consulta
texto_ejemplo = "LangChain permite orquestar pipelines de Inteligencia Artificial."
vector_resultado = embeddings_model.embed_query(texto_ejemplo)

print(f"Texto analizado: '{texto_ejemplo}'")
print(f"Dimensión del vector generado: {len(vector_resultado)}")
print(f"Muestra de los primeros 5 valores: {vector_resultado[:5]}")
```

---

### Ejercicio 3: Pipeline RAG Completo con LCEL
*(Referencia Teórica: Sección 1.3, 1.4, 1.5 y 1.6)*

Construcción de una tubería de Retrieval-Augmented Generation unificando fragmentación de documentos, base de datos vectorial Chroma, embeddings de Hugging Face, modelo Gemini y la sintaxis LCEL con el operador `|`.

```python
import os
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")

# 1. Preparación de Documentos (Sección 1.3 - Etapa 1)
documentos_base = [
    Document(page_content="LangChain Core contiene las abstracciones fundamentales como Runnable, Prompts y Parsers."),
    Document(page_content="RAG (Retrieval-Augmented Generation) combina la búsqueda semántica en vector stores con la generación de LLMs."),
    Document(page_content="LCEL (LangChain Expression Language) utiliza el operador pipe | para encadenar componentes de forma declarativa."),
    Document(page_content="Sentence Transformers provee modelos locales para transformar texto en vectores numéricos densos de alta calidad.")
]

# 2. Chunking / División de Texto (Sección 1.3 - Etapa 2)
splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
docs_divididos = splitter.split_documents(documentos_base)

# 3. Creación de Vector Store y Embeddings (Sección 1.3 - Etapa 3 y Sección 1.4)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
vectorstore = Chroma.from_documents(documents=docs_divididos, embedding=embeddings)

# 4. Creación del Retriever (Sección 1.3 - Etapa 4)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 5. Definición de Prompt Template (Sección 1.2 y 1.6)
template_rag = """Responde únicamente basándote en el contexto proveído a continuación.
Si la información no se encuentra en el contexto, responde: 'No dispongo de suficiente información en los documentos.'

Contexto:
{context}

Pregunta: {question}

Respuesta:"""

prompt = ChatPromptTemplate.from_template(template_rag)

# 6. Inicialización del LLM (Sección 1.5)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=API_KEY,
    temperature=0.1
)

# 7. Construcción de la Cadena RAG con LCEL (Sección 1.6)
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 8. Invocación de la Cadena
pregunta = "¿Cómo se conectan los componentes en LCEL?"
respuesta = rag_chain.invoke(pregunta)

print(f"Pregunta: {pregunta}\n")
print(f"Respuesta Generada:\n{respuesta}")
```

---

### Ejercicio 4: LCEL Avanzado con `RunnableParallel` y Formateo Personalizado
*(Referencia Teórica: Sección 1.6)*

Demostración de composición avanzada utilizando `RunnableParallel` para procesar contextos recuperados y mantener la pregunta original en paralelo, además del uso de un formateador de documentos customizado.

```python
import os
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")

# Función de transformación custom para unir documentos recuperados
def format_docs(docs):
    return "\n---\n".join([doc.page_content for doc in docs])

# Asumiendo retriever configurado previamente
# Construcción del pipeline con RunnableParallel (Sección 1.6)
mapa_entradas = RunnableParallel(
    context=retriever | format_docs,
    question=RunnablePassthrough()
)

prompt_avanzado = ChatPromptTemplate.from_template(
    "Contexto Informativo:\n{context}\n\nConsulta del Usuario: {question}\n\nRespuesta Analítica:"
)

llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=API_KEY, temperature=0.2)

# Ensamblado LCEL completo
cadena_avanzada = mapa_entradas | prompt_avanzado | llm | StrOutputParser()

# Invocación con streaming (Sección 1.6)
print("--- Streaming de Respuesta ---")
for chunk in cadena_avanzada.stream("¿Qué función cumplen los Sentence Transformers?"):
    print(chunk, end="", flush=True)
print("\n")
```


**Diferencias  entre el [lanchain 03](./code-sample/03_langchain.py) y [lanchain 03](./code-sample/03_langchain.py)**

| Característica | Script 1 (Avanzado / Streaming) | Script 2 (Estándar / Batch) |
| --- | --- | --- |
| **Formateo de Contexto** | Aplica una función custom `format_docs` para concatenar el contenido de los documentos con separadores (`---`). | Pasa el `retriever` directamente en el diccionario, dejando que LangChain convierta automáticamente los objetos `Document` a texto. |
| **Construcción LCEL** | Utiliza `RunnableParallel` de forma explícita para estructurar el flujo de datos en paralelo. | Utiliza sintaxis de diccionario nativo `{"context": ..., "question": ...}` (que LCEL convierte internamente a `RunnableParallel`). |
| **Generación de Salida** | Usa **`stream()`**: imprime la respuesta token por token a medida que el LLM la genera. | Usa **`invoke()`**: espera a que el modelo termine de generar la respuesta completa para mostrarla de golpe. |
| **Temperatura del LLM** | `0.2` (da un margen mínimo de variabilidad/creatividad en la redacción). | `0.1` (focalizado en respuestas deterministas y de menor variación). |
| **Enfoque del Prompt** | Solicita una respuesta analítica sin restricciones estrictas de respuesta vacía. | Restringe fuertemente al modelo a responder un texto por defecto si la información no está presente. |



---




