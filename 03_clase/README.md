# Clase 3 — Eslabón del Proyecto: Pydantic, Salidas Estructuradas y Lanzamiento del TP1

## Objetivo de este entregable

Esta clase cierra una deuda y abre otra. Cierra la deuda tecnica de la Clase 2: tenías una tasa de fallo medida sobre 15 mensajes (`reporte_contrato_roto.json`) y ahora se va a construir la capa que la reduce. Abre la deuda del TP1: el brief pide cuatro documentos que ya empezaste a escribir desde la Clase 1, así que este eslabón también es el punto donde esos documentos sueltos se convierten en una entrega formal.

Vas a producir cuatro artefactos:

1. `schemas.py` — el contrato de datos Pydantic V2 para el onboarding de Ortelana (no para pedidos genéricos: para el dominio real del proyecto).
2. `extractor_validado.py` — ahora blindado con Structured Outputs.
3. `comparar_tasas_colapso.py` — re-ejecuta los 15 mensajes de la Clase 2 contra la versión validada y compara la tasa de fallo antes/después.
4. El armado inicial del `TP1_brief_solucion.md`, ensamblando PEAS + Intent Mapping + el nuevo esquema Pydantic.

---

## Parte 1 — El esquema Pydantic de Ortelana

El PDF muestra un `PedidoTextilSchema` genérico de e-commerce. Tu proyecto no vende por consulta de stock: extrae datos de un distribuidor que quiere darse de alta. Adaptás el mismo patrón al dominio real, usando los mismos campos que ya definiste en el `SYSTEM_PROMPT`.



`[schemas.py](./src/schemas.py)`

### Por qué el campo `cuit_verificado_externamente` importa

Este campo es la traducción directa de la "Regla de frontera" que escribiste en `intent_mapping_ortelana.md` en la Clase 2. El esquema lo declara con default `False` a propósito: ningún valor que venga del LLM puede tocarlo. Solo el backend determinista (`verificar_cuit_afip()` en `09_clase.md`) tiene permiso de mutarlo después de consultar una fuente real. Si en algún punto ves que el LLM "decide" poner ese campo en `True`, ya sabés que el diseño se rompió.

### Ejercicio para el alumno

1. Agregá un quinto campo al esquema relacionado con algo que detectaste en tu propio Intent Mapping de la Clase 2 (por ejemplo, `categoria_solicitada: Optional[str]`, pensando en el intento de "VIP Oro" del caso de secuestro semántico).
2. Escribí un `@field_validator` para ese campo que lo rechace si su valor no está en una lista cerrada de categorías legítimas.

---

## Parte 2 — Structured Outputs con Google GenAI

> **Nota:** A diferencia de Anthropic, Google GenAI admite el paso directo de la clase Pydantic al parámetro response_schema. La API se encarga de estructurar el JSON de forma nativa (Garantía del Proveedor), y luego Pydantic procesa las validaciones de negocio internas (Garantía de Aplicación).

`[extractor_validado.py](./src/extractor_validado.py)`


### Ejercicio para el alumno: Laboratorio de Campo (Google GenAI)

> **Objetivo:** Ver en acción la diferencia entre la **Garantía del Proveedor** (Gemini dándonos un JSON estructuralmente válido) y la **Garantía de Aplicación** (Pydantic frenando datos que rompen las reglas de negocio).

#### 1. Verificación del Camino Feliz (Happy Path)

Ejecutá el script `extractor_validado.py` tal como está, utilizando el mensaje de prueba inicial.

* Confirmá en la consola que el diccionario `datos_validados` aparece completo.
* Prestá especial atención al campo `cuit_verificado_externamente`. ¿Quedó en `False`? Recordá que aunque el modelo es muy inteligente, tiene prohibido alterar este flag de infraestructura.

#### 2. Activación de la Garantía de Aplicación (Falla de Negocio)

Modificá el `mensaje_prueba` dentro del script para que el CUIT del taller tenga **9 dígitos** en lugar de 11 (por ejemplo, cambialo a `20-345567-2`). Volvé a correr el script.

* Verificá que ahora el flag `colapso_aplicacion` cambió a `True`.
* Examiná el mensaje de error que capturó el bloque `ValidationError`. Deberías ver el texto exacto que escribiste en tu `@field_validator`.

> **Pregunta de reflexión:** ¿Por qué este error no lo frenó Gemini directamente? (Pista: Para la API de Google, un string de 9 dígitos sigue siendo un string válido según el esquema JSON puro; la regla de que "debe tener 11 dígitos" es lógica de negocio exclusiva de tu aplicación).

#### 3. Investigación de la Garantía del Proveedor (Modo Libre vs. Modo Estricto)

Andá a la función `extraer_con_structured_outputs` y realizá un pequeño experimento de ingeniería inversa eliminando temporalmente estas dos líneas de la configuración:

```python
response_mime_type="application/json",
response_schema=DistribuidorOnboardingSchema,

```

Corré el script de nuevo con el mensaje original y observá qué pasa. Luego, **anotá en una sola frase** la diferencia de comportamiento que observás cuando Gemini opera en "Modo Libre" vs. cuando se le impone un `response_schema`.

---

## Parte 3 — Comparación de tasas de colapso (antes / después)

Este script lee tu reporte_contrato_roto.json generado previamente y contrasta las métricas históricas contra el nuevo extractor blindado con response_schema.

`[comparar_tasas_colapso.py](src/comparar_tasas_colapso.py)`

### Ejercicio para el alumno

1. Copiá tu `reporte_contrato_roto.json` de la Clase 2 a la misma carpeta de este script.
2. Ejecutá `comparar_tasas_colapso.py` y registrá los dos porcentajes.
3. Respondé por escrito: ¿bajó la tasa de colapso a cero? Si no bajó a cero, ¿qué tipo de caso sigue fallando? (Pista esperada: el caso 2, "CUIT verosímil pero inexistente", **no debería desaparecer** con este cambio, porque Pydantic valida formato, no realidad. Ese caso solo se resuelve cuando el campo `cuit_verificado_externamente` se setea desde `verificar_cuit_afip()`, que es trabajo de capas posteriores del proyecto). Si tu reporte muestra que el caso 2 "pasó", es una señal de alerta: revisá que tu validador no esté inflando la confianza del campo solo porque el formato es correcto.

---

## Parte 4 — Gestión de credenciales con `.env`

Este paso es obligatorio antes de subir cualquier código a un repositorio.

---

## Parte 5 — Lanzamiento del TP1: ensamblando el Brief de Solución

```markdown
# TP1 — Brief de Solucion: Sistema de Onboarding Ortelana Textil

## 1. Mapeo del Entorno (PEAS)
[Pegar aqui el contenido completo de 00_PEAS_ortelana.md de la Clase 1]

## 2. Mapa de Intenciones (Intent Mapping)
[Pegar aqui la matriz completa de intent_mapping_ortelana.md de la Clase 2]

## 3. Esquema de Validacion Pydantic V2
[Pegar aqui el contenido completo de schemas.py de esta clase, que incluye la mitigacion del quinto campo 'categoria_solicitada']

## 4. Evaluacion de Hipotesis de Riesgo
Completar esta tabla usando evidencia real de tus propios experimentos:

| Hipotesis de Riesgo | Evidencia (de que clase / archivo) | Mitigacion implementada | Mitigacion pendiente |
|---|---|---|---|
| El LLM puede alucinar la validez de un CUIT | Caso 2 del stress test, Clase 2 | Campo `cuit_verificado_externamente` con default False | Conectar con `verificar_cuit_afip()` real (Clase 9) |
| Un mensaje malicioso puede secuestrar el formato de salida o inventar categorias | Caso 3 del stress test, Clase 2 | `response_schema` forzado + enum `Literal` en `intencion` y `categoria_solicitada` | Monitoreo semantico en backend transaccional |
| El prompt engineering solo no garantiza JSON valido | Tasa de colapso medida en `reporte_contrato_roto.json` | Google GenAI Structured Outputs + Validadores Pydantic (Clase 3) | Implementar reintentos (Polly/Tenacity) ante errores de timeout o red |
| La API puede bloquear la operacion por limites de trafico comercial | Excepcion 429 de Google GenAI detectada en testeo | Captura de `errors.ClientError` con flujo alternativo de bypass / continue | Cola de mensajeria asincronica con Backoff exponencial |

## 5. Seleccion Justificada de Stack
* **Capa de Inferencia:** Google GenAI SDK con `gemini-2.5-pro`, debido a su capacidad de analisis semantico complejo y velocidad de procesamiento.
* **Garantia de Proveedor:** Uso de `response_schema` nativo de Gemini, lo que delega la estructuracion basica y de tipos directamente a la API sin consumo extra de tokens en explicaciones o formateos manuales.
* **Garantia de Aplicacion:** Pydantic V2 para sanitizacion de strings (limpieza de CUITs, normalizacion de emails) y validaciones de logica dura no soportadas nativamente por esquemas JSON planos.
```

### Ejercicio para el alumno

1. Creá el archivo `TP1_brief_solucion.md` en la raíz del proyecto.
2. Pegá los tres documentos previos en las secciones 1, 2 y 3, resolviendo cualquier corchete pendiente que hayas dejado abierto.
3. Completá la tabla de hipótesis de riesgo con tu propia fila adicional.
4. Completá la sección 5 (Stack) en no más de media página.

---

## Cierre y enlace con la Clase 4

Tenés ahora una capa de validación funcionando, pero el `SYSTEM_PROMPT` sigue siendo estático: no sabe nada del stock real de Ortelana. La consigna asincrónica te pide simular qué pasa si tratás de resolver eso metiendo un inventario completo dentro del prompt. Guardá tu respuesta a la pregunta de reflexión del PDF (los tres problemas de ingeniería de meter todo el stock en el system prompt): la Clase 4 introduce embeddings y búsqueda semántica exactamente para resolver ese problema, en lugar de fuerza bruta contextual.
