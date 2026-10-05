# Agentes inteligentes

### 1. Cadenas, RAG y agentes

Un sistema RAG tradicional combina recuperación de información y generación:

```bash
Pregunta -> Recuperacion por Docs -> LLM -> Respuesto
```


Es especialmente útil cuando la respuesta se encuentra en documentos relativamente estáticos: manuales, normativas, PDFs, bases de conocimiento, políticas internas o contenido académico.

Sin embargo, RAG por sí solo no resuelve tareas que exigen consultar datos cambiantes o ejecutar operaciones. Por ejemplo:

- Consultar el estado actual de un pedido en una base SQL
- Verificar stock en tiempo real
- Obtener el clima mediante una API
- Crear un ticket de soporte
- Consultar una agenda institucional
- Ejecutar una operación matemática o un proceso de negocio

Un agente integra al LLM con herramientas y un ciclo de decisión. No se limita a “buscar documentos y responder”: evalúa el estado de la tarea, solicita una acción cuando la necesita, observa el resultado y decide el siguiente paso.

| Aspecto | Cadena / RAG | Agente |
|---|---|---|
| Flujo | Predeterminado | Dinámico |
| Orden de pasos | Fijo | Decidido durante la ejecución |
| Uso de herramientas | Opcional y normalmente fijo | Seleccionado según la consulta |
| Datos externos | Suele centrarse en documentos | Puede usar APIs, SQL, búsquedas, CRM, etc. |
| Ejemplo | “Resume este reglamento” | “¿Cuántas vacantes quedan hoy y anotame?” |
| Riesgo principal | Recuperar contexto irrelevante | Uso incorrecto, excesivo o inseguro de herramientas |

La distinción actual que hace LangGraph es consistente con esto: los **workflows** tienen rutas predeterminadas, mientras que los **agentes** definen dinámicamente su proceso y su uso de herramientas. [docs.langchain](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

### 2. ReAct: razonar, actuar y observar

El patrón **ReAct** significa *Reasoning + Acting*. Su aporte es intercalar el razonamiento con acciones hacia fuentes externas.

El ciclo conceptual es:
```bash
Entrada -> Evaluacion -> ToolCalling -> Resultado -> Nueva evaluacion
```

Luego de una o más iteraciones, el agente entrega una respuesta final.

Ejemplo conceptual:

> Usuario: “¿Qué productos de la categoría notebooks tienen stock y cuál cuesta menos?”

1. El LLM interpreta que necesita datos actuales, no solo conocimiento general.
2. Solicita una herramienta de inventario con un parámetro como `categoria="notebooks"`.
3. El sistema ejecuta la consulta real contra la fuente autorizada.
4. El resultado vuelve al LLM como observación.
5. El LLM compara precio y disponibilidad.
6. Responde con el producto más económico que tenga stock.

El modelo ReAct fue presentado por Yao y colaboradores como una forma de alternar trazas de razonamiento y acciones específicas de una tarea. Las acciones permiten conectarse con fuentes externas —por ejemplo, bases de conocimiento o entornos— y obtener datos adicionales; esto ayuda a corregir planes y manejar excepciones. [arxiv](https://arxiv.org/abs/2210.03629)

### 3. Qué significa “razonar”

En una implementación responsable, no se debe asumir que el sistema necesita exponer al usuario razonamientos internos extensos. Lo importante desde la arquitectura es que el modelo tome una decisión operativa verificable:

- ¿Puede responder con el contexto actual?
- ¿Necesita recuperar documentos?
- ¿Necesita consultar una API?
- ¿Qué herramienta se ajusta a la intención?
- ¿Qué parámetros necesita?
- ¿El resultado es suficiente o debe realizar otra acción?
- ¿Debe finalizar, pedir aclaración o escalar a una persona?

Por lo tanto, el “Reason” del diagrama debe entenderse principalmente como una **política de decisión**: evaluación de intención, estado, herramientas disponibles y evidencias obtenidas.

## Tool use y function calling

### El LLM no ejecuta funciones

Este es uno de los conceptos más importantes de la clase:

> El LLM propone una llamada estructurada; el software de la aplicación valida y ejecuta —o rechaza— esa llamada.

Cuando el modelo usa *function calling* o *tool calling*, no ejecuta Python, SQL, HTTP ni comandos del sistema. Genera una intención estructurada, con:

- Nombre de herramienta
- Argumentos
- Identificador de llamada, si el proveedor lo incluye

Conceptualmente:

```json
{
  "name": "consultar_stock",
  "args": {
    "producto": "notebook",
    "sucursal": "Buenos Aires"
  }
}
```

El orquestador recibe ese objeto, comprueba que la herramienta existe, valida tipos y permisos, ejecuta la operación en un entorno controlado y retorna el resultado al modelo.

LangChain aclara explícitamente que *tool calling* no implica que el modelo esté realizando la acción: el modelo genera los argumentos de una herramienta y la ejecución efectiva queda bajo control de la aplicación. [python.langchain](https://python.langchain.com/v0.2/docs/how_to/function_calling/)

El ciclo real es:

```text
Usuario
  ↓
LLM genera solicitud estructurada de herramienta
  ↓
Orquestador valida nombre, argumentos, permisos y políticas
  ↓
Herramienta ejecuta código, consulta o API
  ↓
Resultado retorna como ToolMessage
  ↓
LLM interpreta el resultado y responde o decide otra acción
```

### El papel del ToolMessage

El resultado de una herramienta debe volver al modelo como un mensaje de herramienta, no como una instrucción de usuario ni como un texto indistinto. Esto permite mantener la trazabilidad entre:

- La llamada solicitada por el modelo
- El identificador de la llamada
- La respuesta real de la función

LangChain representa estas devoluciones mediante `ToolMessage`, asociados al identificador de la llamada original. Esa asociación es necesaria para que el modelo sepa qué observación corresponde a qué acción previa. [python.langchain](https://python.langchain.com/v0.2/docs/how_to/function_calling/)

### Cómo el modelo elige una herramienta

La selección no es una garantía lógica perfecta. Es una predicción probabilística basada en:

- La intención expresada por el usuario
- El prompt del sistema
- El nombre de la herramienta
- La descripción de la herramienta
- La firma y los tipos de entrada
- La descripción de cada parámetro
- Ejemplos de uso, si existen
- El historial conversacional
- Los resultados de herramientas usadas previamente

Por esta razón, una herramienta debe definirse como una **API diseñada para un consumidor probabilístico**, no solamente como una función técnica para otro desarrollador.

Una buena herramienta tiene:

- Un nombre específico y semánticamente claro
- Una única responsabilidad
- Descripción que indique cuándo usarla
- Descripción que indique cuándo no usarla
- Parámetros mínimos y bien definidos
- Tipos y formatos explícitos
- Salidas predecibles y estructuradas
- Mensajes de error claros
- Límites de permisos definidos

Ejemplo conceptual de buena y mala interfaz:

| Diseño débil | Diseño recomendable |
|---|---|
| `hacer_consulta(datos)` | `consultar_estado_pedido(numero_pedido)` |
| `buscar(texto)` | `buscar_politica_interna(consulta, area)` |
| `ejecutar_sql(query)` | `obtener_ventas_por_periodo(fecha_inicio, fecha_fin)` |
| `modificar_usuario(datos)` | `actualizar_email_usuario(usuario_id, nuevo_email)` |

La diferencia es fundamental: una herramienta genérica deja demasiadas decisiones y riesgo en manos del modelo; una herramienta de dominio reduce ambigüedad y limita el alcance de la acción.

## LangGraph y el agente

LangGraph es una capa de orquestación basada en grafos con estado. Es apropiado cuando se necesita más control que una cadena lineal: ciclos, condiciones, persistencia, reintentos, validación, intervención humana y trazabilidad.

Los tres elementos didácticos principales son correctos:

| Componente | Función |
|---|---|
| Estado | Contiene la información compartida y acumulada durante la ejecución |
| Nodo | Ejecuta una operación: invocar LLM, llamar herramientas, validar, enrutar o persistir |
| Arista | Define el paso siguiente; puede ser fija o condicional |
| Arista condicional | Decide la transición según el estado actual |
| `END` | Señala que el grafo terminó la ejecución |
| Checkpoint o persistencia | Guarda el estado para retomar conversaciones, depurar o manejar interrupciones |

Un punto de precisión conceptual: LangGraph no debe describirse estrictamente como un “DAG con ciclos”, porque un DAG, por definición, no contiene ciclos. Es mejor decir:

> LangGraph modela sistemas como un **grafo dirigido con estado**, que puede incluir ciclos controlados, bifurcaciones condicionales, rutas paralelas y puntos de finalización.

El ciclo mínimo de un agente ReAct en LangGraph es:

```text
START
  ↓
Nodo agente: LLM + historial + herramientas disponibles
  ↓
¿El LLM solicitó una herramienta?
  ├── No → END
  └── Sí
       ↓
   Nodo de herramientas
       ↓
   ToolMessage con la observación
       ↓
   Nodo agente
```

La documentación de LangGraph presenta exactamente esta idea: el agente es un LLM que opera en bucles de retroalimentación, toma decisiones sobre qué herramientas utilizar y cómo resolver problemas cuyo camino no puede predefinirse. [docs.langchain](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

### Rol de ToolNode

`ToolNode` representa el componente que ejecuta las herramientas solicitadas por el LLM. Su utilidad no es “dar inteligencia” al agente, sino resolver de forma controlada la parte operativa entre la intención del modelo y la función real.

Actualmente, LangGraph indica que `ToolNode` puede encargarse de ejecutar herramientas en paralelo, manejar errores e inyectar estado automáticamente cuando corresponde. [docs.langchain](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

Desde el punto de vista arquitectónico, el nodo de herramientas debería complementar, no sustituir, controles como:

- Validación de tipos y esquemas
- Autorización por usuario, rol u organización
- Registro de auditoría
- Timeouts
- Rate limits
- Manejo de errores
- Sanitización de entradas
- Protección contra inyección de prompts desde contenido externo
- Confirmación humana antes de operaciones sensibles

## Información adicional relevante

### RAG y agentes no compiten

La arquitectura más útil suele ser **RAG como una herramienta del agente**, no RAG versus agentes.

Ejemplo:

```text
Usuario: “Según la política de devoluciones, ¿puedo devolver este pedido?
Además, verificá si ya fue despachado.”

Agente
  ├── Tool 1: búsqueda RAG sobre políticas internas
  ├── Tool 2: API de logística / pedidos
  └── Síntesis final con ambas fuentes
```

En este caso:

- El RAG resuelve conocimiento documental.
- La API de logística aporta estado actual.
- El agente decide que necesita ambas evidencias.
- La respuesta debe distinguir entre una regla documentada y un hecho transaccional en tiempo real.

Esto es más robusto que intentar indexar en una base vectorial datos operativos altamente dinámicos.

### Agente no significa autonomía ilimitada

Un error frecuente es considerar “más autónomo” como “mejor”. En sistemas empresariales, la calidad se logra con **autonomía acotada**.

Un agente productivo debería tener:

- Un conjunto pequeño de herramientas permitidas
- Instrucciones claras por dominio
- Límites de iteración
- Presupuesto de tiempo y costo
- Restricciones de datos y permisos
- Validación de parámetros
- Observabilidad de llamadas y resultados
- Criterios explícitos para finalizar
- Escalamiento a humano si no tiene confianza o si la acción es sensible

No conviene dar al LLM acceso directo a una herramienta SQL arbitraria, una terminal o una API de pagos sin una capa de control fuerte. Es preferible exponer herramientas de alto nivel y propósito limitado.

### Límites de ejecución

El límite de iteraciones que mencionás es indispensable. Un agente puede caer en ciclos como:

```text
LLM solicita búsqueda
  ↓
La búsqueda devuelve información insuficiente
  ↓
LLM reformula la búsqueda
  ↓
La búsqueda vuelve a ser insuficiente
  ↓
Se repite indefinidamente
```

Las protecciones mínimas son:

- Máximo de pasos o iteraciones
- Tiempo máximo total de ejecución
- Límite de llamadas por herramienta
- Detección de acciones repetidas
- Respuesta de fallback cuando no hay evidencia suficiente
- Registro de la razón de terminación
- Interrupción manual o aprobación humana para acciones críticas

El objetivo no es que el agente siempre “insista hasta resolver”, sino que falle de manera segura y explicable.

### Observabilidad y evaluación

Para evaluar un agente no alcanza con observar si la respuesta final parece buena. Hay que evaluar la trayectoria:

- ¿Seleccionó la herramienta correcta?
- ¿Generó parámetros válidos?
- ¿Hizo llamadas innecesarias?
- ¿Respetó las políticas de seguridad?
- ¿Usó datos reales cuando eran necesarios?
- ¿Interpretó correctamente el resultado?
- ¿Terminó en tiempo y dentro del presupuesto?
- ¿Respondió con incertidumbre cuando faltaban datos?

Métricas útiles:

| Métrica | Qué evalúa |
|---|---|
| Tool selection accuracy | Si eligió la herramienta correcta |
| Argument accuracy | Si generó parámetros correctos |
| Tool success rate | Porcentaje de llamadas ejecutadas sin error |
| Task success rate | Si resolvió el objetivo real del usuario |
| Average steps | Eficiencia del trayecto del agente |
| Latencia total | Tiempo de respuesta extremo a extremo |
| Costo por tarea | Tokens, llamadas externas y cómputo |
| Groundedness | Si la respuesta está respaldada por resultados reales |
| Policy compliance | Si respetó reglas, permisos y restricciones |

### Multiagente: cuándo usarlo

El patrón multiagente tiene sentido cuando existen dominios realmente diferenciados, herramientas extensas o políticas propias por área. Por ejemplo:

- Subagente de documentación y RAG
- Subagente de operaciones y base de datos
- Subagente de soporte
- Subagente de facturación
- Subagente de análisis y reporting
- Orquestador que clasifica, delega y consolida

Pero no se debe usar multiagente solo porque parece más avanzado. Agregar agentes también aumenta:

- Latencia
- Costo
- Complejidad de depuración
- Riesgo de pérdida de contexto
- Dificultad de evaluación
- Posibles contradicciones entre subagentes

La recomendación práctica es:

> Empezar con un solo agente con pocas herramientas, separar herramientas por dominio y pasar a subagentes solo si hay evidencia de que el conjunto de herramientas es demasiado amplio o los flujos requieren especialización clara.

LangGraph documenta patrones de enrutamiento y de orquestador-trabajadores, donde un orquestador divide una tarea, delega subtareas y sintetiza las salidas. Esto resulta útil cuando las subtareas no pueden predefinirse completamente antes de recibir la solicitud. [docs.langchain](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

### Ollama y modelos locales

Ollama permite ejecutar modelos localmente y puede integrarse en una arquitectura de agentes mediante una interfaz compatible con *tool calling*. La ventaja principal es el control sobre el entorno y los datos, especialmente para prototipos offline o escenarios donde la información no debe salir de una red privada.

Sin embargo, conviene matizar tres ideas:

- Ejecutar localmente no elimina todas las obligaciones de seguridad: los permisos, el control de herramientas y la auditoría siguen siendo necesarios.
- La capacidad de uso de herramientas depende del modelo específico, su entrenamiento para tool calling, el formato del proveedor y la calidad de los prompts.
- Un modelo local pequeño puede tener más errores en selección de herramientas, extracción de parámetros y seguimiento de instrucciones que un modelo más capaz; esto debe medirse con casos de prueba, no asumirse.

La interfaz `bind_tools` busca estandarizar la asociación entre un chat model y las definiciones de herramientas, aunque la implementación concreta puede variar según el proveedor y el modelo. [python.langchain](https://python.langchain.com/v0.2/docs/how_to/function_calling/)

## Ideas clave para enseñar

- Un LLM no ejecuta una función: genera una **solicitud estructurada** para que el sistema la ejecute.
- Un RAG aporta conocimiento documental; una herramienta aporta datos o acciones externas.
- Un agente decide si necesita una herramienta, cuál usar y qué hacer con su resultado.
- ReAct es un bucle de evaluación, acción y observación, no una secuencia lineal fija.
- LangGraph organiza el control de flujo con estado, nodos y aristas condicionales.
- La calidad de nombres, descripciones, parámetros y límites de una herramienta determina gran parte de la calidad del agente.
- La autonomía debe estar limitada por permisos, validaciones, presupuestos y condiciones de parada.
- Multiagente es una evolución arquitectónica para dominios complejos, no un requisito inicial.
- RAG, herramientas, memoria, validación y observabilidad son componentes complementarios de una aplicación agéntica sólida.

## Versión breve para el cierre

> Un RAG recupera información para responder; un agente puede decidir qué información necesita y qué acciones debe ejecutar para cumplir un objetivo. El LLM no llama funciones directamente: produce una solicitud estructurada de herramienta, el orquestador la valida y ejecuta, y el resultado vuelve al modelo como observación. LangGraph permite modelar ese ciclo mediante un grafo con estado, nodos de decisión y ejecución, y aristas condicionales. En producción, la prioridad no es maximizar autonomía, sino construir agentes controlados, trazables, seguros y evaluables.
