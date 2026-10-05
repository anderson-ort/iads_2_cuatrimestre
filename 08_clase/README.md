# Evaluación de Sistemas RAG con RAGAS

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial

**Objetivo Técnico:** Comprender la arquitectura de evaluación automática sobre un pipeline RAG utilizando RAGAS, dominar las cuatro métricas core (Faithfulness, Answer Relevancy, Context Precision, Context Recall), definir la estructura del dataset de evaluación y aplicar análisis de regresión sobre el sistema.

---

## El Problema de Evaluar a Ojo

En entornos de producción, la evaluación manual e informal de un sistema RAG no es viable. Evaluar de forma no automatizada presenta tres inconvenientes fundamentales:

1. **Falta de reproducibilidad:** La evaluación cualitativa cambia según el criterio de cada evaluador o momento, impidiendo establecer una fuente de verdad objetiva.
2. **Incapacidad para detectar regresiones:** Ante cambios en componentes clave (como prompts, modelos de lenguaje o tamaño de fragmentos), no es posible determinar si la calidad general del sistema mejoró o empeoró sin reevaluar manualmente todo el espectro de respuestas.
3. **Imposibilidad de escalado:** Analizar cientos o miles de interacciones diarias de forma manual resulta inasumible.

**La solución técnica:** Construir un dataset de evaluación con ground truth (respuestas de referencia) y ejecutar un framework que calcule métricas cuantitativas reproducibles tras cada modificación del pipeline.

---

## Las Cuatro Métricas Core de RAGAS

El proceso de evaluación de un sistema RAG se divide entre los dos componentes principales de la arquitectura: el **Retriever** (recuperador) y el **LLM** (generador).

```
        Pregunta del usuario
               │
               ▼
        ┌─────────────┐
        │  RETRIEVER  │ ← Evaluado por Context Precision y Context Recall
        └─────────────┘
               │
        chunks recuperados
               │
               ▼
        ┌─────────────┐
        │     LLM     │ ← Evaluado por Faithfulness y Answer Relevancy
        └─────────────┘
               │
          respuesta final

```

---

### 1. Faithfulness (Fidelidad)

* **¿Qué mide?** Determina si las afirmaciones presentes en la respuesta generada por el LLM se fundamentan exclusivamente en el contexto recuperado. Su objetivo principal es detectar alucinaciones.
* **Escala:** 0 a 1. Un valor cercano a 1 indica que toda la respuesta proviene del contexto provisto.
* **Diagnóstico si el indicador es bajo:** El problema radica en el LLM. El recuperador trajo información, pero el modelo generó datos no existentes en los chunks. Se debe ajustar el System Prompt (reforzar restricciones) o reducir la temperatura del modelo a 0.

---

### 2. Answer Relevancy (Relevancia de la Respuesta)

* **¿Qué mide?** Evalúa si la respuesta generada atiende de forma directa e integral a la pregunta formulada, independientemente de que sea fiel al contexto.
* **Escala:** 0 a 1. Un valor cercano a 1 indica que la respuesta es directa, concisa y sin divagaciones.
* **Diagnóstico si el indicador es bajo:** El problema radica en la generación. Ocurre cuando el LLM extrae texto correcto del contexto pero no responde al núcleo de la consulta del usuario. Se resuelve ajustando la estructura del prompt de generación.

---

### 3. Context Precision (Precisión Contextual)

* **¿Qué mide?** Evalúa la calidad del recuperador analizando si los fragmentos (chunks) obtenidos son relevantes para la consulta o si introducen ruido.
* **Escala:** 0 a 1. Un valor cercano a 1 indica alta densidad de información útil entre los chunks recuperados.
* **Diagnóstico si el indicador es bajo:** El problema radica en el retriever. Un exceso de información irrelevante incrementa el riesgo de alucinación del LLM. Se requiere ajustar el tamaño de chunking, perfeccionar el filtrado por metadatos o implementar mecanismos de reranking.

---

### 4. Context Recall (Cobertura Contextual)

* **¿Qué mide?** Mide si el recuperador extrajo **todos** los fragmentos necesarios para construir la respuesta correcta, comparando el contexto obtenido contra la respuesta de referencia (ground truth).
* **Escala:** 0 a 1. Un valor cercano a 1 indica que no se omitió información crítica.
* **Diagnóstico si el indicador es bajo:** El problema radica en la estrategia de indexación o fragmentación. Ocurre cuando la información existe en el origen pero el recuperador no la selecciona. Se debe modificar el tamaño de fragmento (chunk_size), aumentar el solapamiento (overlap) o aplicar búsquedas híbridas/semánticas avanzadas.

---

### Matriz de Diagnóstico de Métricas

| Métrica | Componente Evaluado | Causa Principal de Bajo Rendimiento | Acción Correctiva |
| --- | --- | --- | --- |
| **Faithfulness** | LLM (Generación) | Alucinación de información no presente | Ajustar System Prompt y temperature = 0 |
| **Answer Relevancy** | LLM (Generación) | Respuestas evasivas o incompletas | Clarificar el prompt de generación |
| **Context Precision** | Retriever (Búsqueda) | Inclusión de chunks irrelevantes o ruidosos | Mejorar retrieval, filtros o reranking |
| **Context Recall** | Retriever (Búsqueda) | Omisión de chunks con datos clave | Ajustar chunk_size, overlap o embeddings |

---

## Objeto Técnico: Estructura del Dataset de Evaluación

Para ejecutar la evaluación automatizada, RAGAS requiere un objeto estructurado que contenga las siguientes cuatro variables centrales:

```python
dataset_evaluacion = {
    "question": [
        "Consulta enviada por el usuario"
    ],
    "answer": [
        "Respuesta final generada por el pipeline RAG"
    ],
    "contexts": [
        ["Lista de fragmentos de texto recuperados por el retriever"]
    ],
    "ground_truth": [
        "Respuesta de referencia ideal escrita previamente por expertos"
    ]
}

```

### Definición de Campos del Objeto:

* **question:** Texto original de la consulta.
* **answer:** Output textual generado por la cadena RAG a evaluar.
* **contexts:** Lista de cadenas correspondiente a los contenidos de los fragmentos recuperados en la fase de retrieval.
* **ground_truth:** Texto de la respuesta correcta esperada según la documentación de origen.

---

## Monitoreo Continuo y Pruebas de Regresión

El dataset de evaluación junto con RAGAS funciona como una suite de pruebas automatizadas de regresión para sistemas RAG:

```
Cambio en el sistema (prompt, chunk_size, modelo)
                        │
                        ▼
    Ejecución del dataset de evaluación
                        │
                        ▼
      Comparación de métricas vs. Baseline
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
Métricas mejoran                Métricas empeoran
 Deploy de cambios               Reversión de cambios

```

### Integración de Observabilidad (LangSmith + RAGAS)

La combinación de herramientas permite cubrir tanto la medición como la depuración del sistema:

* **RAGAS (Evaluación cuantitativa):** Proporciona la métrica sobre *qué* tan preciso, fiel o relevante es el resultado.
* **LangSmith (Trazabilidad):** Permite inspeccionar el *cómo*, registrando el comportamiento interno de la cadena, los tiempos de ejecución y los prompts intermedios para identificar el punto exacto de falla.

---

## Criterios de Diseño para un Dataset de Evaluación Robusto

Un dataset de evaluación balanceado para sistemas RAG debe incluir diversidad de casos de prueba:

1. **Preguntas directas (Unipaso):** Consultas cuya respuesta se encuentra contenida de forma completa en un único fragmento.
2. **Preguntas compuestas (Multipaso):** Consultas que exigen combinar la información contenida en múltiples fragmentos.
3. **Preguntas fuera de dominio (Trampa):** Consultas sobre temas no cubiertos por la base de conocimientos, donde el sistema debe responder declarando no poseer la información.
4. **Preguntas con lenguaje informal o ambiguo:** Variaciones en la formulación del usuario para validar la capacidad del recuperador ante búsquedas semánticas no literales.

---

## Bibliografía

* **Es, S., et al. (2023).** *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* arXiv:2309.15217.
* **Documentación oficial RAGAS** — docs.ragas.io
* **Documentación oficial LangSmith** — smith.langchain.com
* **Alammar, J., & Grootendorst, M. (2024).** *Hands-On Large Language Models.* O'Reilly. Capítulo 7.
* **Lewis, M., et al. (2020).** *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.*
