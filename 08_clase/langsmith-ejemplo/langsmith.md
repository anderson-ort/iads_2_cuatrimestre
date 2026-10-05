# Qué es LangSmith

LangSmith es una plataforma de **observabilidad, evaluación y depuración** para aplicaciones basadas en LLMs, RAGs y agentes. Su función principal no es ejecutar tu RAG ni almacenar los embeddings: registra y visualiza qué ocurrió dentro de cada petición.

Una traza típica de un pipeline RAG puede verse así:

```text
Pregunta del usuario
        │
        ▼
Query enhancement / reescritura
        │
        ▼
Retriever vectorial o híbrido
        │
        ├── chunks recuperados
        ├── scores
        └── metadatos
        ▼
Reranker
        │
        ▼
Construcción del prompt
        │
        ├── system prompt
        ├── contexto final
        └── pregunta
        ▼
LLM
        │
        ├── modelo
        ├── tokens
        ├── latencia
        └── respuesta
        ▼
Respuesta al usuario
```

En LangSmith, una solicitud completa queda representada como un **trace**. Dentro del trace hay ejecuciones anidadas —*runs* o *spans*— para cada paso: recuperación, llamada al modelo, herramienta, reranking, etc.

Esto permite responder preguntas de ingeniería muy concretas:

- “¿Qué chunks recibió el LLM cuando dio esta respuesta incorrecta?”
- “¿El fallo ocurrió en la búsqueda, el reranker o el prompt?”
- “¿Qué modelo consumió más tokens?”
- “¿Cuál es la latencia promedio y cuál es el cuello de botella?”
- “¿Este cambio de prompt empeoró las respuestas de producción?”
- “¿Qué consultas tienen baja fidelidad según RAGAS?”

La documentación oficial describe LangSmith como una herramienta de visibilidad *end-to-end*: captura el registro completo de los pasos ejecutados, desde los inputs hasta la salida final. [docs.langchain](https://docs.langchain.com/langsmith/observability-quickstart)

## Plan gratuito de LangSmith

Actualmente, LangSmith dispone de un plan **Developer** sin costo mensual para una persona. [langchain](https://www.langchain.com/pricing)

| Aspecto | Developer gratuito |
|---|---|
| Precio | USD 0 por usuario/mes |
| Usuarios | 1 |
| Traces incluidos | Hasta 5.000 *base traces* al mes |
| Retención de base traces | 14 días |
| Uso recomendado | Aprendizaje, demos, pruebas locales y prototipos |
| Soporte | Comunidad |
| Hosting | Cloud administrado por LangChain |
| Funciones principales | Tracing, evaluaciones, datasets, monitoreo, prompt hub/playground y exportación |

Un **trace** no equivale necesariamente a una llamada al LLM. En la definición de LangSmith, un trace representa una ejecución completa de la aplicación: por ejemplo, una pregunta de usuario que dispara búsqueda, reranking, armado de prompt y generación. Dentro puede contener múltiples eventos anidados. [langchain](https://www.langchain.com/pricing)

Para una clase, un TP o un RAG de bajo tráfico, 5.000 ejecuciones al mes suele ser más que suficiente. Si ejecutaras 10 preguntas por día durante un mes, generarías aproximadamente 300 traces; aun si probaras 100 preguntas al día, estarías cerca de 3.000.

### Límites y precauciones

- La retención del plan gratuito es corta: 14 días para los base traces. No lo usaría como única fuente histórica de auditoría.
- No confundir el costo de LangSmith con el costo del LLM: aunque LangSmith sea gratuito dentro de su cuota, OpenAI, Anthropic, Gemini o cualquier proveedor que uses pueden cobrar por tokens.
- Antes de enviar trazas, revisá si incluyen PII, secretos, credenciales, documentos internos, datos de clientes o información regulada.
- Para producción con datos sensibles, necesitás definir redacción de datos, minimización de payload, política de retención y controles de acceso. El autoalojamiento en LangSmith está asociado a planes Enterprise, no al plan Developer. [langchain](https://www.langchain.com/pricing)

## Cómo armar algo simple

Para aprender, evitaría empezar con agentes o arquitecturas complejas. Armá primero un RAG mínimo y trazable con cuatro componentes:

```text
Documentos técnicos
        │
        ▼
Chunking + embeddings
        │
        ▼
ChromaDB local
        │
        ▼
Retriever top-k
        │
        ▼
LLM + prompt con grounding
        │
        ▼
LangSmith registra toda la ejecución
        │
        ▼
RAGAS evalúa un dataset pequeño
```

Para tu enfoque de Python y `uv`, una primera versión podría tener esta estructura:

```text
rag-observability/
├── app/
│   ├── ingest.py          # Lee, limpia, fragmenta e indexa documentos
│   ├── retriever.py       # Recupera chunks y metadatos
│   ├── rag.py             # Orquesta retrieval + prompt + LLM
│   └── eval.py            # Ejecuta RAGAS sobre un dataset
├── data/
│   ├── raw/
│   └── eval/
│       └── golden_set.jsonl
├── tests/
│   └── test_regression.py
├── .env.example
├── pyproject.toml
└── README.md
```

### Dependencias mínimas

Si usás LangChain, ChromaDB, OpenAI y LangSmith:

```bash
uv init rag-observability
cd rag-observability

uv add langchain langchain-openai langchain-chroma chromadb langsmith ragas datasets python-dotenv
```

Para habilitar tracing, configurás las variables de entorno:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="tu_api_key"
export LANGSMITH_PROJECT="rag-clase-dev"

export OPENAI_API_KEY="tu_openai_api_key"
```

La configuración oficial utiliza `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY` y, opcionalmente, `LANGSMITH_PROJECT` para enviar las trazas a un proyecto determinado. Si no configurás el proyecto, LangSmith crea o usa el proyecto de trazabilidad por defecto. [docs.langchain](https://docs.langchain.com/langsmith/observability-quickstart)

### RAG mínimo con LangChain

Con LangChain, el tracing puede ser prácticamente automático si las variables están definidas. El siguiente ejemplo se centra en hacer visible la cadena completa, incluidos retrieval y generación.

```python
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vectorstore = Chroma(
    collection_name="documentacion",
    embedding_function=embeddings,
    persist_directory="./chroma_db",
)

retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4},
)

prompt = ChatPromptTemplate.from_template("""
Sos un asistente especializado en documentación técnica.

Respondé únicamente con base en el contexto provisto.
Si el contexto no contiene evidencia suficiente, respondé:
"No tengo información suficiente en la base documental."

Contexto:
{context}

Pregunta:
{question}
""")

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0,
)

def format_docs(documents):
    return "\n\n---\n\n".join(
        f"[Fuente: {doc.metadata.get('source', 'desconocida')}]\n{doc.page_content}"
        for doc in documents
    )

rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke(
    "¿Cuál es el período de retención de los logs de auditoría?"
)

print(answer)
```

Al ejecutar esto con tracing activado, LangSmith debería permitirte inspeccionar:

- La pregunta original.
- La salida del retriever.
- Los chunks que llegaron al prompt.
- El prompt final con contexto.
- El modelo y sus parámetros.
- La respuesta generada.
- Latencia y consumo de tokens, según integración y proveedor.

Con LangChain o LangGraph, la documentación oficial indica que se puede habilitar el tracing con una variable de entorno. También admite instrumentación explícita con decoradores como `@traceable`, útil cuando querés observar funciones propias que no pasan automáticamente por el framework. [docs.langchain](https://docs.langchain.com/langsmith/observability-quickstart)

### Trazar funciones propias

Para un RAG profesional, no dependas exclusivamente de trazas automáticas. Instrumentá explícitamente los puntos críticos del pipeline:

```python
from langsmith import traceable

@traceable(run_type="retriever", name="retrieve_documents")
def retrieve_documents(question: str):
    return retriever.invoke(question)

@traceable(run_type="chain", name="generate_grounded_answer")
def generate_answer(question: str) -> str:
    documents = retrieve_documents(question)
    context = format_docs(documents)

    return (
        prompt
        | llm
        | StrOutputParser()
    ).invoke({
        "context": context,
        "question": question,
    })
```

Esto es especialmente útil si implementás:

- Query rewriting.
- Filtros de metadatos.
- Hybrid retrieval con BM25 y vectores.
- Reciprocal Rank Fusion.
- Reranking.
- Cache semántico.
- Guardrails.
- Lógica de abstención.
- Herramientas o agentes.

## LangSmith + RAGAS

La combinación más útil para tu materia es esta:

| Herramienta | Función | Pregunta que responde |
|---|---|---|
| LangSmith | Observabilidad y debugging | “¿Qué ocurrió dentro del pipeline?” |
| RAGAS | Evaluación cuantitativa de calidad | “¿Qué tan bueno fue el resultado?” |
| Pytest | Quality gates en CI/CD | “¿Este cambio rompe un comportamiento esperado?” |
| GitHub Actions | Automatización | “¿Podemos bloquear un merge o deploy si hay regresión?” |

El flujo sería:

```text
Cambio en prompt, chunking, embeddings o modelo
        │
        ▼
Ejecutar golden dataset
        │
        ▼
LangSmith registra cada corrida:
- contextos
- prompts
- latencia
- tokens
- respuesta
        │
        ▼
RAGAS calcula:
- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall
        │
        ▼
Comparar contra baseline
        │
        ├── Métricas estables o mejores → merge/deploy
        └── Métricas degradadas → inspeccionar traces
```

Ejemplo de diagnóstico realista:

```text
Context Recall cae: 0.89 → 0.63
Faithfulness permanece alta: 0.94 → 0.93
        │
        ▼
Interpretación:
El LLM sigue respondiendo de forma respaldada por el contexto,
pero el retriever está omitiendo información importante.
        │
        ▼
LangSmith permite inspeccionar:
- top-k actual
- chunks recuperados
- scores de similitud
- filtro aplicado
- versión del índice
        │
        ▼
Hipótesis:
El cambio de chunk_size fragmentó una tabla de políticas
y dejó fuera el chunk que contenía el límite numérico.
```

Este es el punto donde LangSmith aporta más valor: RAGAS detecta cuantitativamente la regresión; LangSmith permite navegar al trace exacto y verificar la causa.

## Alternativa gratuita recomendada: Langfuse

Si buscás una alternativa a LangSmith que sea gratuita, abierta y compatible con una arquitectura más independiente, mi recomendación principal es **Langfuse**.

Langfuse ofrece tracing, seguimiento de sesiones y usuarios, registro de tokens y costos, gestión/versionado de prompts, datasets, evaluaciones offline y online, feedback humano, exportaciones y una API pública. [langfuse](https://langfuse.com/pricing-self-host)

Tiene dos alternativas gratuitas importantes:

| Alternativa | Costo de plataforma | Ventaja principal | Limitación principal |
|---|---:|---|---|
| LangSmith Developer | Gratis hasta 5.000 traces/mes | Inicio muy rápido con LangChain/LangGraph | 1 usuario, cloud y retención base de 14 días |
| Langfuse Cloud Hobby | Gratis | Sin tarjeta; útil para POCs | Límite de uso y retención según el plan cloud |
| Langfuse OSS self-hosted | Gratis para el software | Control de datos, uso sin tarifa por volumen y stack open source | Debés operar infraestructura |

Langfuse indica que su edición open source está bajo licencia MIT y puede autoalojarse sin límite de uso tarifado, incluyendo funcionalidades core como observabilidad, evaluaciones, gestión de prompts y datasets. Proporciona guías para Docker Compose, Helm/Kubernetes y Terraform en AWS, GCP y Azure. [langfuse](https://langfuse.com/pricing-self-host)

### Cuándo elegir cada una

**Elegí LangSmith** si:

- Estás aprendiendo LangChain o LangGraph.
- Querés llegar a traces útiles en minutos.
- El proyecto es individual, educativo o de bajo volumen.
- No manejás datos sensibles en las trazas.
- Priorizás velocidad de implementación sobre control de infraestructura.

**Elegí Langfuse Cloud** si:

- Querés una UI administrada, sin desplegar nada.
- Necesitás una alternativa a LangSmith más orientada a observabilidad, costos y prompt management.
- Estás en fase de POC, demo o formación.

**Elegí Langfuse self-hosted** si:

- Trabajás con documentos, conversaciones o datos sensibles.
- Necesitás control sobre dónde se almacenan prompts, contextos y respuestas.
- Querés evitar dependencia de un proveedor SaaS.
- Tenés capacidad de operar Docker Compose localmente o Kubernetes en un entorno de producción.
- Vas a integrar observabilidad con tu stack propio en GCP, PostgreSQL, ClickHouse, OpenTelemetry o Grafana.

## Recomendación concreta para tu caso

Dado que querés aprender RAGAS, LangSmith y construir sistemas RAG en Python de manera didáctica y profesional, haría esta progresión:

1. **Fase 1: LangSmith Developer + RAGAS.**  
   Armá un RAG pequeño con ChromaDB local, un corpus reducido y 20 a 30 preguntas de evaluación. Activá tracing y aprendé a inspeccionar retrieval, prompts, tokens y outputs.

2. **Fase 2: Dataset de regresión.**  
   Versioná un `golden_set.jsonl` con preguntas directas, multipaso, fuera de dominio y paráfrasis. Ejecutá RAGAS antes y después de cambiar `chunk_size`, `top_k`, embeddings o prompts.

3. **Fase 3: Quality gates con Pytest.**  
   Definí umbrales para evitar regresiones importantes, por ejemplo:

   ```python
   assert faithfulness_mean >= 0.85
   assert answer_relevancy_mean >= 0.80
   assert context_recall_mean >= 0.80
   ```

   En un sistema real, complementaría esos umbrales con casos críticos individuales que deben pasar obligatoriamente.

4. **Fase 4: Langfuse self-hosted.**  
   Cuando el proyecto incorpore datos más sensibles, más usuarios o necesidad de soberanía de datos, migrá la observabilidad a Langfuse autoalojado. Mantendría RAGAS como framework de evaluación independiente.

La combinación final de bajo costo y sólida sería:

```text
Python + uv
    │
LangChain o LCEL
    │
ChromaDB local para prototipo
    │
PostgreSQL + pgvector para una etapa más productiva
    │
LangSmith Developer para aprender trazabilidad
o Langfuse OSS para trazabilidad autoalojada
    │
RAGAS para evaluación semántica y regresión
    │
Pytest + GitHub Actions para quality gates
```

Así separás correctamente responsabilidades: el vector store recupera evidencia, el LLM genera, LangSmith o Langfuse muestran lo ocurrido, RAGAS mide calidad y CI evita desplegar regresiones.
