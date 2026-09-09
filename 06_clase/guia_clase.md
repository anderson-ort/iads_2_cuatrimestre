# Clase 6: Arquitectura RAG Basica — Del Catalogo al Sintetizador

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial

El software tradicional basado en reglas no escala para atender la variabilidad del lenguaje humano porque carece de "conocimiento del mundo" (relaciones geográficas, estacionales o inferencias implícitas). La arquitectura **RAG (Retrieval-Augmented Generation)** resuelve este problema utilizando el LLM como un **sintetizador semántico**: el modelo no inventa datos ni actúa como base de datos, sino que toma la información verídica recuperada de una base vectorial (como ChromaDB) y la cruza con su comprensión general del mundo para generar respuestas precisas y naturales.

**Los Tres Pasos de RAG**

* **Paso 1: Chunking (Offline):** División de documentos extensos en fragmentos más pequeños e indexables. Evita saturar la ventana de contexto del LLM, previene la dilución semántica y evita el fenómeno *Lost in the Middle* (donde el modelo ignora información traspapelada en textos largos).
* **Paso 2: Retrieval (Online):** La consulta del usuario se transforma en un vector (*embedding*) para buscar y extraer los $k$ fragmentos más similares dentro de la base vectorial.
* **Paso 3: Generación (Online):** El LLM procesa un prompt enriquecido que combina la pregunta del usuario con los fragmentos recuperados para redactar la respuesta.

**Trade-off del Tamaño de Fragmento (Chunking)**

| Criterio | Fragmentos Pequeños (~200 caracteres) | Fragmentos Grandes (~2000 caracteres) |
| --- | --- | --- |
| **Precisión de Búsqueda** | Alta (encuentra el detalle exacto) | Baja (mezcla demasiados temas) |
| **Contexto para el LLM** | Reducido (puede perder contexto) | Amplio (puede saturar la atención) |
| **Costo Operativo** | Bajo | Alto |

**Pipeline LCEL y Trazabilidad de Fuentes**

LangChain LCEL (*LangChain Expression Language*) permite estructurar el flujo completo de forma declarativa uniendo sus componentes esenciales: **Retriever $\rightarrow$ Formateador de Contexto $\rightarrow$ Prompt $\rightarrow$ LLM $\rightarrow$ Parser de Salida**.

Para aplicaciones comerciales, el pipeline debe ofrecer **trazabilidad de fuentes**: adjuntar a la respuesta final los metadatos (IDs, stock, ubicación) de los documentos utilizados. Esto transforma al chatbot en un sistema transparente y auditable por operadores humanos.

**Guardrails Comerciales y Red Teaming**

Un LLM no configurado tiende a ser complaciente y puede inventar precios, descuentos o condiciones inexistentes para satisfacer al usuario. Para evitar pasivos financieros o legales en producción, se aplican dos mecanismos de seguridad:

* **Temperature = 0.0:** Ajuste determinista obligatorio en entornos transaccionales para erradicar la improvisación del modelo.
* **Prompt de Anclaje Estricto (Grounding):** Reglas del sistema que restringen la respuesta *únicamente* al texto provisto, prohibiendo confirmar acuerdos verbales u homologar datos fuera de catálogo y forzando una respuesta estandarizada de desconocimiento cuando falte información.
* **Red Teaming:** Evaluación cruzada mediante pruebas de estrés e ingeniería social (ataques simulados) para garantizar que el bot resista la manipulación y mantenga sus restricciones comerciales intactas.


--- 
