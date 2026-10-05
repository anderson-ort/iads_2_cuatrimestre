# RAGAS
RAGAS es un framework de evaluación para aplicaciones **RAG** (*Retrieval-Augmented Generation*). Su valor central es transformar una evaluación subjetiva —“esta respuesta parece buena”— en un conjunto de métricas reproducibles que permiten medir, comparar y detectar regresiones en el recuperador y el modelo generativo. [arxiv](https://arxiv.org/html/2309.15217v2)

## Qué es RAGAS

Un sistema RAG responde una pregunta en dos etapas:

1. **Retrieval:** busca fragmentos relevantes en una base documental.
2. **Generation:** entrega esos fragmentos al LLM para que formule la respuesta.

Por ello, una respuesta deficiente puede tener orígenes muy distintos:

- El LLM puede inventar una afirmación aunque el contexto sea correcto.
- El retriever puede traer información irrelevante.
- El retriever puede omitir una fuente crítica.
- El LLM puede disponer del contexto adecuado, pero contestar de forma vaga, parcial o desviada.

RAGAS —*Retrieval Augmented Generation Assessment*— separa esos fallos en dimensiones evaluables. El trabajo original plantea además métricas que pueden operar sin depender necesariamente de anotaciones humanas de referencia para todos los casos, aunque ciertas métricas y evaluaciones más rigurosas se benefician de contar con respuestas de referencia. [arxiv](https://arxiv.org/html/2309.15217v2)

En términos prácticos, RAGAS funciona como una suite de tests de calidad para tu aplicación RAG:

```text
Dataset de evaluación
        +
Versión del pipeline RAG
        ↓
Ejecución de preguntas
        ↓
Respuestas + contextos recuperados
        ↓
RAGAS calcula métricas
        ↓
Comparación contra baseline / umbrales
        ↓
Deploy, alerta o rollback
```

La analogía útil para ingeniería es:

- Tests unitarios verifican comportamiento determinista de componentes de software.
- Tests de integración validan el flujo entre servicios.
- **RAGAS evalúa la calidad probabilística y semántica** de la recuperación y generación de un pipeline RAG.

## Las cuatro métricas principales

Las cuatro métricas que incluiste constituyen una muy buena base pedagógica y operativa. RAGAS las organiza naturalmente entre evaluación del recuperador y evaluación de la respuesta del LLM. [docs.ragas](https://docs.ragas.io/en/v0.1.21/getstarted/evaluation.html)

| Métrica | Evalúa principalmente | Pregunta que responde | Señal típica de fallo |
|---|---|---|---|
| Faithfulness | Generación | “¿La respuesta está respaldada por el contexto recuperado?” | Alucinaciones o afirmaciones no sustentadas |
| Answer Relevancy / Response Relevancy | Generación | “¿La respuesta responde realmente a la pregunta?” | Divagación, información redundante o respuesta parcial |
| Context Precision | Retrieval | “¿Los primeros chunks recuperados son útiles y relevantes?” | Ruido documental y ranking débil |
| Context Recall | Retrieval | “¿El contexto contiene toda la evidencia necesaria?” | Omisión de información relevante |

### Faithfulness: ¿la respuesta está fundamentada?

**Faithfulness** mide si las afirmaciones de la respuesta se pueden inferir a partir de los contextos recuperados. Es la métrica más directamente relacionada con el riesgo de alucinación dentro de un flujo RAG. [arxiv](https://arxiv.org/html/2309.15217v2)

Ejemplo:

```text
Pregunta:
"¿Cuál es el período de retención de logs?"

Contexto recuperado:
"Los logs de auditoría se retienen durante 90 días."

Respuesta A:
"Los logs de auditoría se retienen durante 90 días."
→ Faithfulness alto.

Respuesta B:
"Los logs se almacenan cifrados durante 90 días y se eliminan automáticamente."
→ Faithfulness menor si el contexto no menciona cifrado ni eliminación automática.
```

Un valor alto no implica necesariamente que la respuesta sea útil. Un modelo podría responder algo completamente respaldado, pero irrelevante:

```text
Pregunta: "¿Cómo se configura la retención?"
Respuesta: "Los logs se retienen 90 días."
```

La respuesta puede ser fiel al contexto, pero no explica la configuración solicitada. Por eso Faithfulness debe leerse junto con Answer Relevancy.

**Cuando Faithfulness baja**, inspeccionaría:

- System prompt: obligar a responder únicamente usando el contexto entregado.
- Instrucción explícita de abstención: “Si el contexto no contiene evidencia suficiente, indica que no dispones de información.”
- Temperatura y parámetros de muestreo.
- Formato de respuesta: citas por chunk, respuesta estructurada o extracción de evidencia.
- Calidad del contexto: a veces la supuesta alucinación nace de un contexto contradictorio o incompleto, no solo del modelo.

Un matiz importante: aunque normalmente se atribuye al LLM, Faithfulness no debe diagnosticarse de forma aislada como “problema exclusivo de generación”. Si se recuperan documentos contradictorios, desactualizados o ambiguos, el modelo puede producir una respuesta fiel a evidencia de baja calidad.

### Answer Relevancy: ¿contesta lo que se preguntó?

**Answer Relevancy** —en documentación más reciente puede aparecer como *Response Relevancy*— mide si la respuesta está alineada con la pregunta. Penaliza respuestas incompletas, redundantes o que agregan información innecesaria. [docs.ragas](https://docs.ragas.io/en/v0.1.21/references/metrics.html)

Ejemplo:

```text
Pregunta:
"¿Qué variables debo ajustar para mejorar el recall?"

Respuesta relevante:
"Aumenta top-k, revisa chunk_size y overlap, y considera búsqueda híbrida o query expansion."

Respuesta poco relevante:
"Los sistemas RAG combinan recuperación de información con modelos generativos. 
Los embeddings convierten texto en vectores..."
```

La segunda puede ser técnicamente correcta, pero no responde de manera directa a la consulta.

Una Answer Relevancy baja suele indicar:

- Prompt de generación demasiado general.
- Falta de instrucciones sobre concisión, formato y cobertura.
- Contexto amplio que induce respuestas enciclopédicas.
- Preguntas ambiguas sin una estrategia de clarificación.
- Modelo que prioriza explicar conceptos relacionados en lugar de resolver la intención del usuario.

Una instrucción útil de prompt sería:

```text
Responde directamente la pregunta del usuario usando solo el contexto.
Incluye todos los puntos necesarios para resolverla.
No agregues antecedentes, supuestos ni detalles no solicitados.
Si la evidencia es insuficiente, dilo explícitamente.
```

### Context Precision: ¿hay ruido entre los chunks?

**Context Precision** evalúa si los chunks relevantes aparecen bien posicionados dentro de los resultados recuperados. La versión actual de la documentación lo define como una evaluación de la capacidad del retriever para rankear fragmentos relevantes por encima de los irrelevantes; se calcula en torno a precision@k sobre el ranking recuperado. [docs.ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)

Ejemplo:

```text
Pregunta:
"¿Cómo se rota una API key?"

Top-4 recuperado:
1. "Rotación de API keys mediante endpoint /keys/rotate"
2. "Política de expiración de tokens JWT"
3. "Guía de despliegue de Kubernetes"
4. "Las API keys se pueden revocar desde el panel"

Resultado:
- Los chunks 1 y 4 son relevantes.
- Los chunks 2 y 3 agregan ruido.
- Si los relevantes aparecen primero, Context Precision será mejor
  que si aparecen relegados al final.
```

Una precision baja suele producir dos problemas:

- El LLM recibe demasiada información no necesaria.
- Aumenta el riesgo de que el modelo se distraiga, mezcle conceptos o responda con evidencia equivocada.

Mejoras típicas:

- Ajustar `top_k`: recuperar más no siempre mejora la respuesta.
- Añadir un **reranker** cross-encoder o LLM-based.
- Aplicar filtros por metadatos: producto, versión, fecha, tenant, idioma, tipo de documento.
- Mejorar embeddings según el dominio e idioma documental.
- Usar recuperación híbrida: búsqueda vectorial + BM25/keyword search.
- Refinar la estrategia de chunking, títulos, jerarquía y metadatos.
- Realizar *query rewriting* o expansión de consulta para preguntas ambiguas.

### Context Recall: ¿recuperaste toda la evidencia necesaria?

**Context Recall** mide si los contextos recuperados incluyen la información necesaria para construir la respuesta correcta, usando la respuesta de referencia como señal para identificar hechos esperados. [docs.ragas](https://docs.ragas.io/en/v0.1.21/getstarted/evaluation.html)

Ejemplo multipaso:

```text
Pregunta:
"¿Qué rol puede aprobar gastos y cuál es el límite?"

Ground truth:
"El rol Manager puede aprobar gastos de hasta USD 5.000."

Contextos recuperados:
1. "Los gastos requieren aprobación según el rol."
2. "El rol Manager puede aprobar gastos de hasta USD 5.000."

→ Recall alto: están presentes rol y límite.

Contextos recuperados alternativos:
1. "Los gastos requieren aprobación según el rol."
2. "El rol Analyst no puede aprobar gastos."

→ Recall bajo: falta el dato esencial sobre Manager y USD 5.000.
```

Recall bajo significa que incluso un LLM perfectamente obediente no tendría suficiente evidencia para producir una respuesta completa. En este caso el primer sospechoso es el retrieval, la indexación o la segmentación del corpus.

Mejoras típicas:

- Aumentar `top_k` con cautela y contrarrestar el ruido con reranking.
- Revisar `chunk_size` y `chunk_overlap`.
- Evitar fragmentar una idea semántica o una tabla de forma destructiva.
- Mantener metadatos y estructura documental: título, sección, jerarquía, fecha, fuente y versión.
- Incorporar búsqueda híbrida.
- Aplicar expansión o reformulación de queries.
- Indexar correctamente PDFs, tablas, código y documentación con secciones anidadas.
- Evaluar si los documentos fuente contienen realmente la respuesta esperada.

## Dataset: contrato de evaluación

El objeto que propones recoge los elementos esenciales. Conceptualmente, cada fila del dataset representa un caso de prueba con su entrada, ejecución real del pipeline y respuesta esperada:

```python
caso = {
    "question": "¿Cuál es el período de retención de logs de auditoría?",
    "answer": "Los logs de auditoría se retienen durante 90 días.",
    "contexts": [
        "Los logs de auditoría se retienen durante 90 días.",
        "La política aplica a todos los entornos de producción."
    ],
    "ground_truth": "Los logs de auditoría se retienen durante 90 días."
}
```

Las dependencias conceptuales de las métricas son:

| Métrica | Question | Answer | Contexts | Ground truth / Reference |
|---|:---:|:---:|:---:|:---:|
| Faithfulness | Sí | Sí | Sí | No necesariamente |
| Answer Relevancy | Sí | Sí | No necesariamente | No necesariamente |
| Context Precision | Sí | No necesariamente | Sí | Puede utilizarse según la variante de métrica |
| Context Recall | Sí | No | Sí | Sí |

En la práctica, mantendría siempre las cuatro columnas. Aunque algunas métricas puedan funcionar sin `ground_truth`, tener una respuesta de referencia permite evaluar completitud, corrección funcional y cambios de comportamiento con mayor solidez.

### Recomendaciones de diseño

Un dataset robusto no debe consistir solo en preguntas “fáciles” cuya respuesta aparece textual y literalmente en un único chunk. Debe representar el tráfico y los riesgos reales del sistema.

- **Preguntas directas:** validan la recuperación básica y la extracción puntual.
- **Preguntas multipaso:** exigen combinar hechos presentes en documentos o secciones distintas.
- **Preguntas parafraseadas:** comprueban que la búsqueda semántica funciona más allá de coincidencias léxicas.
- **Preguntas con restricciones:** incluyen versión, fecha, región, rol de usuario o producto.
- **Preguntas fuera de dominio:** validan que el sistema se abstiene correctamente en lugar de inventar.
- **Preguntas adversariales:** contienen premisas falsas, instrucciones conflictivas o ambigüedades deliberadas.
- **Preguntas sobre documentos recientes y antiguos:** detectan errores de versionado, frescura o filtrado temporal.
- **Preguntas multilingües:** importantes si tu base documental o usuarios usan español e inglés.

Para un producto real, conviene separar el dataset en:

```text
golden_set/
├── smoke/          # Casos mínimos, ejecutados en cada PR
├── regression/     # Casos históricos de fallos corregidos
├── domain/         # Cobertura de áreas funcionales
├── adversarial/    # Casos difíciles, ambiguos o fuera de alcance
└── production/     # Muestra anonimizada y curada de tráfico real
```

La regla más importante: cada incidente de calidad significativo que encuentres en producción debería, tras corregirse, convertirse en un nuevo caso de regresión.

## Ecosistema RAG: evaluación y observabilidad

RAGAS no reemplaza al resto del ecosistema; cubre específicamente la **medición de calidad**. Para operar un RAG de producción necesitas varias capas complementarias.

| Capa | Pregunta operativa | Componentes habituales |
|---|---|---|
| Ingesta | “¿Qué documentos entran y cómo se versionan?” | Loaders, OCR, limpieza, normalización, metadatos |
| Indexación | “¿Cómo represento y fragmento el conocimiento?” | Chunking, embeddings, vector DB, BM25 |
| Retrieval | “¿Qué evidencia recupero para esta pregunta?” | Similarity search, filtros, híbrido, reranking |
| Generación | “¿Cómo responde el LLM usando la evidencia?” | Prompt, modelo, citas, abstención, structured output |
| Observabilidad | “¿Qué ocurrió dentro de una ejecución?” | Traces, prompts, latencia, tokens, errores |
| Evaluación | “¿Qué tan bien funciona frente a un estándar?” | RAGAS, datasets golden, umbrales, comparación |
| Operación | “¿Puedo desplegar con seguridad?” | CI/CD, alertas, rollback, control de versiones |

### RAGAS y LangSmith

La combinación que planteas es correcta, pero sus funciones deben distinguirse:

- **RAGAS** responde: “¿Cuál fue la calidad de este sistema o esta versión?” Mide fidelidad, relevancia, precisión y cobertura del retrieval.
- **LangSmith** responde: “¿Qué ocurrió en esta ejecución?” Registra trazas de llamadas, prompts, pasos intermedios y métricas de rendimiento de la aplicación LLM. Su documentación describe observabilidad desde trazas individuales hasta métricas agregadas de producción. [docs.langchain](https://docs.langchain.com/langsmith/observability)

Una forma operativa de integrarlos sería:

```text
Usuario envía una consulta
        ↓
LangSmith registra la traza:
- query original
- query reescrita
- documentos recuperados
- scores del retriever
- prompt final
- modelo y parámetros
- respuesta
- latencia y tokens
        ↓
RAGAS procesa:
- question
- answer
- contexts
- ground_truth, si corresponde
        ↓
Dashboard / CI compara:
- baseline vs versión candidata
- métricas por categoría
- fallos por pregunta
        ↓
Equipo inspecciona la traza
del caso degradado en LangSmith
```

La métrica te señala *que algo empeoró*; la traza te ayuda a descubrir *por qué*. Por ejemplo:

```text
Context Recall cae de 0.91 a 0.69
        ↓
Inspección en trazas:
- se redujo top_k de 8 a 3
- la respuesta exige combinar dos documentos
- el segundo documento quedó fuera del ranking
        ↓
Acción:
- restablecer top_k o sumar reranking
- agregar el caso al regression suite
```

## Evaluación como regresión

El uso más valioso de RAGAS no es una ejecución aislada, sino comparar versiones del sistema.

Define un baseline versionado:

```yaml
baseline:
  faithfulness: 0.88
  answer_relevancy: 0.84
  context_precision: 0.80
  context_recall: 0.86
```

Luego, ante un cambio —nuevo embedding model, modificación de `chunk_size`, prompt nuevo, cambio de vector store o incorporación de reranker— ejecutas el mismo dataset y comparas distribuciones, medias y casos individuales.

Una política de CI razonable podría ser:

```text
Bloquear deploy si:
- Faithfulness disminuye más de 0.03.
- Context Recall disminuye más de 0.05.
- Más del 5% de los casos quedan por debajo del umbral mínimo.
- Un caso crítico de negocio falla, aunque el promedio global mejore.
```

No conviene decidir solo por el promedio. Un cambio puede elevar la media de Faithfulness pero romper consultas críticas de compliance, seguridad, facturación o soporte. Por eso es recomendable definir:

- Umbrales globales.
- Umbrales por categoría.
- Casos bloqueantes o *must-pass*.
- Métricas de dispersión, no solo promedio.
- Comparaciones por versión del corpus y del pipeline.

Finalmente, las métricas RAGAS son evaluaciones basadas en modelos y no una verdad absoluta. Debes calibrarlas con revisión humana periódica, especialmente para dominios sensibles, respuestas largas, lenguaje especializado, documentación contradictoria o decisiones de alto impacto. RAGAS proporciona una señal sistemática y escalable; los expertos de dominio siguen siendo necesarios para validar que esa señal se corresponda con calidad real. [arxiv](https://arxiv.org/html/2309.15217v2)

En síntesis: RAGAS convierte la calidad de un RAG en una propiedad medible; LangSmith hace visible el recorrido interno que produjo cada resultado; y un dataset de evaluación versionado transforma ambos elementos en un proceso continuo de ingeniería, pruebas de regresión y despliegue más seguro.
