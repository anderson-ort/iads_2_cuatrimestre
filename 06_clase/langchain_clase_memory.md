Para elevar la sofisticación de las cadenas LCEL vistas en la guía, el siguiente paso natural es implementar un **RAG Conversacional con Memoria de Sesión**.
### El Reto de la Memoria en RAG

Si en la primera pregunta dices: *«¿Qué es LCEL?»* y en la segunda preguntas: *«¿Cómo se conectan sus componentes?»*, el *retriever* fallará si busca literalmente *"¿Cómo se conectan sus componentes?"* en la base vectorial (porque no sabe a qué se refiere "sus").

Para solucionarlo, la arquitectura sofisticada usa **dos sub-cadenas**:

1. **Cadena de Contextualización**: Toma el historial + la nueva pregunta y genera una pregunta independiente (*standalone query*).
2. **Cadena de Respuesta RAG**: Usa esa pregunta independiente para buscar en ChromaDB y genera la respuesta final teniendo en cuenta el historial.

---

### Ejercicio 6: RAG Conversacional con Memoria y Reformulación de Consultas (LCEL + `RunnableWithMessageHistory`)

**[Ejemplo completo con memory](./code-sample/05_langchain.py)**

### Explicación de los Componentes Clave

1. **`MessagesPlaceholder(variable_name="chat_history")`**:
Sustituye dinámicamente una lista de objetos `HumanMessage` y `AIMessage` guardados en el historial dentro del prompt.
2. **`RunnablePassthrough.assign(...)`**:
Permite calcular un valor al vuelo (en este caso, recuperar el contexto) y añadirlo al diccionario de entrada antes de enviarlo al siguiente eslabón.
3. **`RunnableWithMessageHistory`**:
Es la clase estandarizada en LangChain Core para manejar sesiones de chat. Se encarga de:
* Leer el historial guardado en la sesión activa (`session_id`).
* Inyectar ese historial en la cadena bajo la clave `"chat_history"`.
* Guardar automáticamente la nueva pregunta y la respuesta del LLM en la base de datos de historial al terminar la ejecución.


4. **Multi-Tenancy Integrado (`session_id`)**:
Gracias al parámetro `get_session_history`, puedes cambiar `session_id: "usuario_A"` por `session_id: "usuario_B"` y el pipeline mantendrá estados de memoria totalmente independientes para cada usuario de tu backend o API.
