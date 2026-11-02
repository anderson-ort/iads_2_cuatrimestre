# Ciclo de Vida de Sistemas de IA en Producción (AIOps): Caso Ortelana

## 1. Fundamentos de AIOps y Degradación de Sistemas

Un sistema de IA en producción no permanece estático tras su despliegue. Aunque funcione de manera óptima el primer día, su rendimiento se degrada silenciosamente con el tiempo debido a la dinámica del entorno.

El ciclo de vida AIOps establece un proceso continuo de **despliegue $\rightarrow$ monitoreo $\rightarrow$ detección de degradación $\rightarrow$ experimentación $\rightarrow$ evaluación $\rightarrow$ actualización o rollback**.

```
┌─────────────────────────────────────────────────────────┐
│                   CICLO DE VIDA AIOps                   │
│                                                         │
│   Deploy ──> Monitorear ──> Detectar degradación        │
│     ▲                            │                      │
│     │                            ▼                      │
│   Rollback <─── Evaluar <─── Experimentar               │
│ (si empeora)   (RAGAS)      (A/B Testing)               │
└─────────────────────────────────────────────────────────┘

```

### Causas principales de degradación (Drift)

* **Data Drift:** Cambios en la forma en que los usuarios interactúan con el sistema (e.g., nuevos términos, jerga regional o registros más informales de los distribuidores que difieren del catálogo original).
* **Concept Drift:** Cambios en las definiciones de negocio a lo largo del tiempo (e.g., modificación de las condiciones de la categoría "Cliente Premium" o nuevas políticas comerciales).
* **Model Drift:** Modificaciones en el comportamiento subyacente del LLM debido a actualizaciones automáticas por parte del proveedor (OpenAI, Anthropic, Google), afectando la reproducibilidad.

---

## 2. Telemetría y Observabilidad en Producción

Para evitar fallos silenciosos, es necesario registrar y auditar cada interacción en el endpoint principal (`POST /api/v1/chat`).

### Señales operativas clave

| Señal | Punto de captura | Uso operativo |
| --- | --- | --- |
| `session_id`, `user_id`, `thread_id` | API / LangSmith | Segmentación de usuarios y reproducción de sesiones. |
| Ruta elegida (`routing_used`) | Nodo Orquestador | Detección de degradación del router o sobreuso de agentes costosos (`react_agent`). |
| Estado de Guardrails | Middleware de Seguridad | Alertas en tiempo real por incremento en bloqueos de entrada/salida. |
| Latencia (total y por nodo) | LangSmith / FastAPI | Identificación de regresiones de rendimiento en la cadena RAG. |
| Consumo de tokens y costo | LangSmith / Proveedor | Control presupuestario por consulta y por usuario. |
| Documentos recuperados y scores | Retriever | Diagnóstico de calidad de recuperación y presencia de ruido. |
| Feedback explícito | Endpoint `/feedback` | Evaluación de la utilidad percibida por el usuario final. |
| Métricas RAGAS | Endpoint `/eval` | Comparación objetiva entre versiones de lanzamientos. |

### Alertas operativas mínimas

1. **Latencia p95:** Superior al umbral establecido durante más de 15 minutos.
2. **Seguridad:** Incremento inusual en la tasa de `blocked_input` o `blocked_output`.
3. **Calidad RAGAS:** Caída de `context_recall` o `faithfulness` por debajo del baseline en producción.
4. **Distancia vectorial:** Aumento sostenido en la distancia semántica de las consultas entrantes respecto a la base de datos.

---

## 3. Versionado de Prompts y A/B Testing

Los prompts deben gestionarse con el mismo rigor que el código fuente: mediante control de versiones, metadatos y pruebas en entornos aislados antes de su liberación total.

### Gestión de prompts como artefactos

Herramientas como **PromptLayer** o esquemas de versionado en Git permiten desacoplar los prompts del código base.

```text
prompts/
├── router/
│   ├── v1.md                 # Etiqueta: prod
│   └── v2_few_shot.md        # Etiqueta: experiment
└── synthesizer/
    ├── v1.md                 # Etiqueta: prod
    └── v2_strict_context.md  # Etiqueta: staging

```

Cada prompt versionado incluye:

* `prompt_id` y `version` (e.g., `router_v2`).
* `hash` SHA-256 del contenido para garantizar inmutabilidad.
* `label` (`prod`, `staging`, `experiment`).
* Metadatos: Autor, fecha, dataset de evaluación de origen e hipótesis de cambio.

### Asignación determinista de tráfico para A/B Testing

Para evaluar dos variantes de prompt sin perjudicar la experiencia del usuario, se divide el tráfico mediante un *hash* del `session_id`. Esto asegura que el usuario interactúe siempre con la misma variante a lo largo de toda su conversación.

```python
import hashlib

def assign_variant(session_id: str, experiment: dict) -> str:
    """
    Asigna de forma consistente la misma variante de prompt al mismo session_id.
    """
    bucket = int(hashlib.sha256(session_id.encode()).hexdigest(), 16) % 100
    
    cumulative = 0
    for variant in experiment["variants"]:
        cumulative += variant["percentage"]
        if bucket < cumulative:
            return variant["name"]
            
    return experiment["default_variant"]

```

#### Ejemplo de configuración (TOML)

```toml
[prompt_experiments.router_v2]
enabled = true
default_variant = "control"

[prompt_experiments.router_v2.variants.control]
prompt_version = "v1"
percentage = 80

[prompt_experiments.router_v2.variants.treatment]
prompt_version = "v2_few_shot"
percentage = 20

```

### Protocolo de rollout y rollback

1. **Despliegue gradual:** Iniciar con un 5–10% del tráfico en la variante candidata (*treatment*).
2. **Evaluación de métricas:** Monitorear durante 24–48 horas la tasa de aciertos del routing, latencia p95 y tasa de bloqueos.
3. **Criterio de promoción:** Si la variante mejora la métrica primaria (e.g., $+5\%$ en enrutamiento correcto) sin degradar la latencia ni aumentar errores, se promueve a `prod` (100%).
4. **Rollback automático:** Si los errores superan el umbral tolerable, el sistema redirige el 100% del tráfico a la versión estable previa.

---

## 4. Prompt Engineering con Evidencia y Golden Sets

Evite modificar prompts por intuición. La optimización debe seguir un ciclo iterativo basado en datos reales:

```
Análisis de Fallos ──> Dataset (Golden Set) ──> Evaluación Automática ──> Ajuste de Prompt

```

### Construcción del Golden Set

El conjunto de evaluación debe incluir casos representativos de cada categoría del negocio:

* Consultas sobre precios, promociones y descuentos.
* Stock, catálogo y especificaciones de telas.
* Reglamento comercial y condiciones de crédito.
* Validación de CUIT e identificación de clientes.
* Logística, envíos y devoluciones.
* Consultas ambiguas o con múltiples intenciones.
* Preguntas fuera de dominio o intentos de inyección de prompt (*jailbreaks*).

### Buenas prácticas por agente

* **Router:** Exigir salidas categóricas estrictas (`catalogo`, `credito`, `reclamos`, `general`) apoyadas en ejemplos *few-shot* para casos límite.
* **Synthesizer:** Restringir la generación al contexto recuperado (*groundedness*), exigiendo citas explícitas e instrucciones sobre cómo responder ante falta de información.
* **Agente CUIT:** Decouplar la extracción de datos de la validación lógica y el formato de error para evitar alucinaciones fiscales.
* **ReAct Agent:** Limitar la cantidad máxima de pasos e iteraciones con herramientas externas.
* **Guardrails:** Evaluar falsos positivos (bloqueos indebidos a clientes legítimos) y falsos negativos (filtración de datos no permitidos).

---

## 5. Registro y Comparación de Experimentos RAG con MLflow

Optimizar un pipeline RAG requiere probar múltiples combinaciones de parámetros. **MLflow** permite registrar parámetros, métricas y artefactos de cada corrida de evaluación para determinar la configuración óptima.

### Grilla de experimentos recomendada

- `model-name` : gpt-4o-mini


| Experimento | `chunk_size` | `chunk_overlap` | `k` (retriever) | `top_n` (rerank) | LLM | Métricas RAGAS esperadas |
| --- | --- | --- | --- | --- | --- | --- |
| **Baseline** | 300 | 60 | 3 | - | model-name | Referencia de latencia y costo |
| **Medium Chunk** | 500 | 100 | 3 | - | model-name | Mayor continuidad semántica |
| **High Recall** | 500 | 100 | 5 | - | model-name | Mayor `context_recall` |
| **Reranked** | 800 | 160 | 10 | 4 | model-name | Equilibrio entre precision y recall |

### Registro en MLflow con RAGAS

```python
import mlflow
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

mlflow.set_experiment("ortelana_rag_optimization")

with mlflow.start_run(run_name="medium_500_100_k5"):
    # 1. Registrar Parámetros
    mlflow.log_params({
        "chunk_size": 500,
        "chunk_overlap": 100,
        "k_retriever": 5,
        "embedding_model": "text-embedding-3-small",
        "llm_model": "gpt-4o-mini"
    })
    
    # 2. Ejecutar Evaluación RAGAS sobre el Dataset
    results = evaluate(dataset=eval_dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
    df_results = results.to_pandas()
    
    # 3. Registrar Métricas Promedio
    mlflow.log_metrics({
        "faithfulness": df_results["faithfulness"].mean(),
        "answer_relevancy": df_results["answer_relevancy"].mean(),
        "context_precision": df_results["context_precision"].mean(),
        "context_recall": df_results["context_recall"].mean(),
    })
    
    # 4. Guardar Artefacto de Resultados
    df_results.to_csv("ragas_detail.csv", index=False)
    mlflow.log_artifact("ragas_detail.csv")

```

### Trade-offs en la selección de hiperparámetros

* **Chunks grandes y mayor $k$:** Incrementan el `context_recall` (encuentran más información), pero pueden introducir ruido, elevar el consumo de tokens y reducir la `context_precision`.
* **Chunks pequeños y menor $k$:** Incrementan la `context_precision` y reducen latencia/costos, pero corren el riesgo de omitir contexto relevante.

---

## 6. Detección de Drift y Actualización de Bases Vectoriales

### Detección de Drift de Consultas

Para identificar si los usuarios están realizando preguntas fuera de la cobertura del conocimiento actual, se monitorea la distancia semántica entre las consultas entrantes y los vectores de la base de datos.

```python
import numpy as np

def evaluar_drift_consultas(vectorstore, consultas_recientes: list[str], umbral_p90: float = 0.4) -> dict:
    distancias = []
    for q in consultas_recientes:
        res = vectorstore.similarity_search_with_score(q, k=1)
        if res:
            distancias.append(res[0][1]) # Distancia L2 o Coseno
            
    p90 = float(np.percentile(distancias, 90))
    drift_detectado = p90 > umbral_p90
    
    return {
        "drift_detectado": drift_detectado,
        "distancia_p90": round(p90, 4),
        "umbral": umbral_p90
    }

```

Si el percentil 90 ($p90$) de las distancias supera el umbral, indica que las consultas de los usuarios se han alejado del dominio indexado (e.g., búsquedas de productos no incluidos o cambios de vocabulario).

### Actualización incremental con `upsert` en ChromaDB

Recrear el índice vectorial completo genera costos innecesarios en tokens de embeddings. La estrategia recomendada consiste en procesar cambios incrementales manteniendo metadatos estables.

```json
{
  "source_document_id": "catalogo_telas_2026",
  "item_id": "tela_102",
  "content_hash": "a8f5f167...",
  "source_last_modified": "2026-10-28T10:00:00Z"
}

```

#### Flujo de actualización:

1. **Identificación:** Comparar el `content_hash` del nuevo documento/catálogo contra el registrado en la base vectorial.
2. **Nuevos y modificados:** Ejecutar `vectorstore.upsert()` sobre los ítems cuyos hashes difieran.
3. **Descontinuados:** Ejecutar `vectorstore.delete(ids=[...])` para remover los elementos eliminados.
4. **Sincronización del índice léxico:** Reconstruir o actualizar el índice **BM25** para garantizar que las búsquedas híbridas reconozcan las adiciones de forma inmediata.

---

## 7. Roadmap Práctico de Implementación

```
Fase 1: Observabilidad ──> Fase 2: Evaluación ──> Fase 3: Prompts Release ──> Fase 4: Datos Vivos

```

### Fase 1: Observabilidad y Telemetría Base

* Incorporar middleware de logging estructurado en FastAPI.
* Capturar latencias, costos, tokens, rutas elegidas y estados de guardrails en LangSmith.
* Implementar alertas automáticas para desviaciones de latencia p95 y bloqueos.

### Fase 2: Evaluación Continua

* Ampliar el conjunto de evaluación (`data/eval`) integrando un **Golden Set** multidisciplinario.
* Automatizar corridas de RAGAS registradas en MLflow para cada versión candidata.

### Fase 3: Prompts como Release

* Migrar prompts fijos a archivos de configuración versionados o a PromptLayer.
* Implementar el enrutamiento por $hash$ de `session_id` para realizar A/B testing con tráfico real.
* Definir políticas automáticas de promoción y rollback.

### Fase 4: Drift y Mantenimiento Incremental

* Programar un trabajo periódico (job semanal) para calcular el drift de distancia semántica de consultas.
* Implementar el pipeline de actualización `upsert` para ChromaDB y refresco dinámico de BM25 sin *downtime*.

---

## 8. Prioridades Críticas para Ortelana

1. **Telemetría detallada por Request:** Permite aislar si una falla proviene de la etapa de recuperación (*retrieval*), del prompt, del modelo o de los guardrails.
2. **Versionado y A/B Testing del Synthesizer:** Impacta directamente en la precisión, fidelidad (*faithfulness*) y utilidad de las respuestas entregadas a los distribuidores.
3. **Estrategia de Upsert Incremental y Refresco de BM25:** Asegura que los cambios continuos en precios, stock y políticas comerciales se reflejen inmediatamente sin incurrir en costos elevados de reindexación.

---

## Bibliografía y Referencias

* **Sculley, D., et al. (2015).** *Hidden Technical Debt in Machine Learning Systems.* NeurIPS.
* **Huyen, C. (2025).** *AI Engineering: Building Applications with Foundation Models.* O'Reilly. Capítulo 10 (Monitoring) y Capítulo 12 (Continual Learning).
* **Kleppmann, M. (2017).** *Designing Data-Intensive Applications.* O'Reilly. Capítulo 11 (Stream Processing).
* **ChromaDB Documentation.** *Core Concepts & Upsert Usage.* Cookbook ChromaDB. [cookbook.chromadb.dev](https://cookbook.chromadb.dev/core/)
* **Galileo AI.** *AI Data Observability and Vector Drift.* [galileo.ai/blog/ai-data-observability](https://galileo.ai/blog/ai-data-observability)
* **LaunchDarkly.** *LLM Observability and Experimentation in Production.* [launchdarkly.com/blog/llm-observability/](https://launchdarkly.com/blog/llm-observability/)
* **Lync.** *AI Observability: Latency and Cost Optimization.* [lync.me/learning/1230/ai-observability-latency-cost-optimization](https://www.lync.me/learning/1230/ai-observability-latency-cost-optimization)
* **Microsoft Learn.** *Design and Implement Advanced Prompt Optimization for Production Agents.* [learn.microsoft.com](https://www.learn.microsoft.com/en-us/training/modules/aaai-design-advanced-prompt-production-agents/6-implement-prompt-version-optimization/)
* **MLflow Documentation.** *RAG Evaluation, Agent Frameworks and A/B Testing Best Practices.* [mlflow.org](https://mlflow.org/)
* **OpenAI Cookbook.** *Building Resilient Prompts Using an Evaluation Flywheel.* [developers.openai.com](https://developers.openai.com/cookbook/examples/evaluation/building_resilient_prompts_using_an_evaluation_flywheel)
* **PromptLayer Documentation.** *Prompt A/B Testing and Version Management.* [promptlayer.com](https://www.promptlayer.com/glossary/prompt-ab-testing/)
