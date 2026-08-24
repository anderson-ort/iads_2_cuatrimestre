# Clase 3: Prompt Engineering, Structured Outputs y Consumo de APIs

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial

**Objetivo Técnico:** Implementar esquemas de validación de datos en tiempo de ejecución con Pydantic y Structured Outputs multiplataforma, dominar las técnicas de Prompt Engineering para outputs estructurados, y consumir APIs de modelos fundacionales de forma segura y robusta desde Python.

> [!NOTE] **Para quienes vienen de las Microcredenciales**
> En la Microcredencial vieron Prompt Engineering como herramienta de diseño de productos. Hoy damos el paso siguiente: convertir ese diseño en código Python que se ejecuta automáticamente, y agregar una capa de validación que garantiza que el contrato de datos se cumpla siempre — aunque el modelo falle.

---

## Planificación de la Clase (4 horas)

| Bloque | Duración | Contenido |
| --- | --- | --- |
| **Bloque 1** | 30 min | Debate de evidencia: los scripts rotos que trajeron de casa |
| **Bloque 2** | 45 min | Prompt Engineering estructurado: Zero-shot, Few-shot y CoT |
| **Bloque 3** | 75 min | Pydantic V2 y Structured Outputs — cerrando el contrato |
| **Bloque 4** | 60 min | Integración completa: script Python con API real y `.env` |
| **Cierre** | 30 min | Resumen, material asincrónico y conexión con Clase 4 |

---

## Bloque 1: Debate de Evidencia — "El Contrato Roto" (30 min)

### Arranque con la tarea asincrónica

La clase arranca con los alumnos exponiendo sus reportes de falla. Cada uno corrió el script de Ortelana con el lote de correos y documentó cuántas veces `json.loads()` explotó.

**Preguntar al grupo:**

* ¿Cuántos tuvieron 0 fallas? ¿Cuántos tuvieron más de 3?
* ¿Qué tipo de error fue el más común — `JSONDecodeError`, `KeyError`, o tipo de dato incorrecto?
* ¿Cuál fue el correo que más rompió el formato?

**Mapear en el pizarrón los tres tipos de falla:**

| Tipo de error | Qué pasó | Ejemplo |
| --- | --- | --- |
| `JSONDecodeError` | El modelo agregó texto antes o después del JSON | `"Aquí tienes el JSON: {...}"` |
| `KeyError` | El modelo omitió un campo requerido | Faltó `"intencion"` en la respuesta |
| Tipo incorrecto | El modelo puso string donde esperábamos int | `"monto": "medio millón"` |

> [!IMPORTANT] **La conclusión que tiene que surgir**
> El Prompt Engineering solo no alcanza para garantizar un contrato de datos en producción. La solución tiene dos capas: primero le pedimos bien al modelo (Prompt Engineering + Structured Outputs), después validamos en código lo que devuelve (Pydantic). Hoy construimos las dos.

---

## Bloque 2: Prompt Engineering Estructurado (45 min)

### Conexión con clases anteriores

En Clase 2 diseñamos el System Prompt como validador de lógica y vimos que el LLM actúa como **traductor** — convierte texto informal en JSON estructurado. Hoy profundizamos en cómo diseñar ese traductor con precisión técnica.

> [!NOTE] **El problema central**
> Un LLM puede responder en prosa, en Markdown, en JSON, en verso... lo que más probable le resulte. Si no le decimos exactamente qué formato queremos, el código que intenta parsear su respuesta va a fallar. **Prompt Engineering es escribir un contrato: el modelo promete entregar X formato, y el código confía en ese contrato.**

---

### Las tres técnicas fundamentales

#### Zero-shot

Le pedimos algo al modelo sin darle ejemplos. Confiamos en su entrenamiento general.

```text
[System]
Sos un extractor de datos operativos para Ortelana Textil.
Respondé siempre en JSON con esta estructura exacta:
{"intencion": "...", "cuit": "...", "material": "...", "monto": 0.0}

[User]
"Soy del taller Modas del Sur, CUIT 20-34556789-2, quiero cotizar 15 rollos de denim azul, calculamos medio millón."

```

**Resultado esperado:**

```json
{"intencion": "CONSULTA_STOCK", "cuit": "20345567892", "material": "denim", "monto": 500000.0}

```

**Cuándo usarlo:** Tareas simples y bien definidas.
**Riesgo:** Si el input es ambiguo o malicioso, el modelo puede romper el formato.

---

#### Few-shot

Damos ejemplos de input → output antes de la pregunta real. "Mostramos" en lugar de solo "describir".

```text
[System]
Sos un extractor de intenciones para Ortelana Textil.
Usá exactamente esta estructura JSON. Sin texto extra.

Ejemplos:
Input: "¿Tienen stock de gabardina azul?"
Output: {"intencion": "CONSULTA_STOCK", "cuit": null, "material": "gabardina", "monto": 0.0}

Input: "Quiero abrir cuenta corriente, CUIT 20-12345678-9"
Output: {"intencion": "ALTA_DISTRIBUIDOR", "cuit": "20123456789", "material": null, "monto": 0.0}

[User]
"El jersey que llegó vino manchado, somos el taller El Gaucho, CUIT 27-98765432-1"

```

**Resultado esperado:**

```json
{"intencion": "RECLAMO_CALIDAD", "cuit": "27987654321", "material": "jersey", "monto": 0.0}

```

**Cuándo usarlo:** Cuando el Zero-shot falla en casos límite o el formato es complejo.

> [!TIP] **Los ejemplos Few-shot son tests de regresión del prompt**
> Si el modelo falla un ejemplo, el prompt necesita ajuste. Antes de ir a producción, probá al menos 5 inputs distintos — incluyendo los casos que rompieron el script en la tarea asincrónica.

---

#### Chain of Thought (CoT)

Pedimos al modelo que "piense en voz alta" antes de responder. Útil para tareas con múltiples pasos lógicos.

```text
[System]
Sos un asistente de operaciones de Ortelana Textil.
Antes de responder, razonás paso a paso:
1. ¿Qué quiere hacer el distribuidor?
2. ¿Qué datos necesito para eso?
3. ¿Tengo todos los datos o necesito pedir más?
Luego respondé en JSON.

[User]
"Quiero abrir cuenta corriente"

```

**Resultado esperado:**

```
Razonamiento:
1. El distribuidor quiere darse de alta como mayorista.
2. Para validar necesito el CUIT.
3. No tengo el CUIT — debo solicitarlo.

{"intencion": "ALTA_DISTRIBUIDOR", "cuit": null, "accion_siguiente": "SOLICITAR_CUIT"}

```

**Cuándo usarlo:** Cuando la respuesta depende de condiciones múltiples. El razonamiento explícito reduce alucinaciones.

---

### Las 4 reglas del prompt para JSON confiable

El salto clave: pasar de "el LLM responde bien" a "el LLM responde de forma que mi código puede leer".

**Regla 1 — Especificar el schema exacto**

```text
Respondé ÚNICAMENTE con un JSON con estas claves:
- "intencion": string (una de: CONSULTA_STOCK, ALTA_DISTRIBUIDOR, RECLAMO_CALIDAD)
- "cuit": string de 11 dígitos o null
- "material": string o null
- "monto": número flotante, 0.0 si no se menciona

```

**Regla 2 — Prohibir texto extra**

```text
No incluyas explicaciones, saludos ni bloques de código (no uses ```json).
Tu respuesta debe comenzar con { y terminar con }.

```

**Regla 3 — Definir el fallback**

```text
Si no podés extraer la intención con certeza,
respondé: {"intencion": "DESCONOCIDO", "cuit": null, "material": null, "monto": 0.0}

```

**Regla 4 — Validar en código, nunca confiar ciegamente**

```python
import json

raw = respuesta_llm
try:
    data = json.loads(raw)
    assert "intencion" in data
except (json.JSONDecodeError, AssertionError):
    data = {"intencion": "PARSE_ERROR", "raw": raw}

```

> [!IMPORTANT] **Conclusión del Bloque 2**
> El Prompt Engineering no es "hablar bonito con la IA". Es escribir una especificación de contrato. Pero ese contrato solo lo cumple el modelo cuando todo sale bien — Pydantic es el que lo hace cumplir cuando algo falla.

---

## Bloque 3: Pydantic V2 y Structured Outputs (75 min)

### Dos capas de garantía

La arquitectura robusta no confía en una sola capa de validación:

| Capa | Herramienta | Qué garantiza |
| --- | --- | --- |
| **Garantía del proveedor** | Structured Outputs (API) | El modelo genera tokens que cumplen el schema matemáticamente |
| **Garantía de aplicación** | Pydantic V2 (runtime) | El objeto Python tiene los tipos correctos antes de tocar el backend |

Juntas, estas dos capas cierran el contrato entre el caos del lenguaje natural y la precisión del backend de Ortelana.

---

### Pydantic V2 — El contrato de datos en código

```python
# schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List

class PedidoTextilSchema(BaseModel):
    """
    Contrato de datos estricto para normalizar consultas
    recibidas por Ortelana Textil.
    """
    intencion: Literal["CONSULTA_STOCK", "ALTA_DISTRIBUIDOR", "RECLAMO_CALIDAD", "DESCONOCIDO"] = Field(
        description="Categoría operativa según el mapa de intenciones de Ortelana."
    )
    cuit: Optional[str] = Field(
        default=None,
        description="CUIT del distribuidor. Exactamente 11 dígitos numéricos."
    )
    materiales_solicitados: List[str] = Field(
        default_factory=list,
        description="Lista de telas o materiales identificados (denim, gabardina, jersey...)"
    )
    monto_estimado: float = Field(
        default=0.0,
        description="Monto financiero mencionado. 0.0 si no se especifica."
    )

    @field_validator('cuit')
    @classmethod
    def limpiar_y_validar_cuit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cuit_limpio = "".join(filter(str.isdigit, v))
        if cuit_limpio and len(cuit_limpio) != 11:
            raise ValueError("El CUIT debe contener exactamente 11 dígitos numéricos.")
        return cuit_limpio

```

> [!TIP] **Pregunta #1**
> ¿Por qué usamos `Literal` para el campo `intencion` en lugar de `str`?
> **Análisis:** Porque `str` acepta cualquier texto — el modelo podría devolver `"CONSULTA_DE_STOCK"` o `"consulta_stock"` y Pydantic lo aceptaría igual. `Literal` restringe los valores posibles exactamente a los que definimos. Si el modelo devuelve algo distinto, Pydantic lanza una excepción en lugar de dejar pasar datos inválidos.

---

### Gestión segura de credenciales con `.env`

Antes de conectar con la API, una regla no negociable:

```bash
# .env — NUNCA subir a Git (.gitignore)
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXX
ANTHROPIC_API_KEY=sk-ant-XXXXXXXXXXXXXXXXXXXXXX

```

```python
# app.py
import os
from dotenv import load_dotenv

load_dotenv()  # Lee el archivo .env

api_key = os.getenv("OPENAI_API_KEY")  # Correcto
# api_key = "sk-proj-abc123..."        # NUNCA hardcodear

```

> [!WARNING] **Si la API Key sube a GitHub, está comprometida en minutos.**
> Los bots escanean repositorios públicos en tiempo real buscando keys expuestas. Una key comprometida puede generar costos de miles de dólares en horas.

---

### Script completo con Structured Outputs (OpenAI)

```python
# app.py
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError
from schemas import PedidoTextilSchema

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

correo_recibido = """
Hola gente de Ortelana!! Cómo andan??
Soy del taller 'Modas del Sur', mi CUIT es el 20-34556789-2.
Queríamos ver si tienen stock de denim de 12 en azul índigo.
Necesitamos cotizar unos 15 rollos urgente porque se nos cae un cliente grande.
Calculamos una compra de medio millón si nos hacen buen precio.
Avisen porfa!! Gracias!!
"""

try:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Sos un asistente de operaciones para Ortelana Textil. "
                           "Extraé los datos estructurados del correo del distribuidor."
            },
            {"role": "user", "content": correo_recibido}
        ],
        response_format=PedidoTextilSchema,  # Structured Output
    )

    datos: PedidoTextilSchema = completion.choices[0].message.parsed

    print("--- PIPELINE EXITOSO ---")
    print(f"Intención:   {datos.intencion}")
    print(f"CUIT:        {datos.cuit}")
    print(f"Materiales:  {datos.materiales_solicitados}")
    print(f"Monto:       ${datos.monto_estimado:,.0f}")

except ValidationError as e:
    print(f"ERROR: Los datos violaron el schema de Ortelana. Detalles: {e}")
except Exception as e:
    print(f"Falla de comunicación con el proveedor: {e}")

```

**Output esperado:**

```
--- PIPELINE EXITOSO ---
Intención:   CONSULTA_STOCK
CUIT:        20345567892
Materiales:  ['denim']
Monto:       $500,000

```

> [!TIP] **Pregunta #2**
> ¿Qué diferencia hay entre usar `.parse()` con `response_format=PedidoTextilSchema` y usar `json.loads()` con el texto crudo?
> **Análisis:** Con `.parse()`, OpenAI restringe la generación del modelo para que matemáticamente solo pueda producir tokens válidos según el schema. El resultado ya llega como objeto Pydantic validado — no como string. Con `json.loads()` el string puede contener cualquier cosa y el parseo puede fallar. Es la diferencia entre garantía y esperanza.

---

### Abstracción multiproveedor — Evitando el Vendor Lock-in

Los tres proveedores resuelven el mismo problema de forma distinta:

| Proveedor | Mecanismo | Código clave |
| --- | --- | --- |
| **OpenAI** | `response_format` con clase Pydantic | `client.beta.chat.completions.parse(..., response_format=MiSchema)` |
| **Anthropic** | Tool Use forzado | Define una "herramienta" ficticia con el schema y fuerza su uso |
| **Gemini** | `generation_config` con schema | `generation_config={"response_mime_type": "application/json", "response_schema": ...}` |

> [!NOTE] **¿Por qué importa esto?**
> Los precios, capacidades y límites de los modelos cambian constantemente. Un sistema bien diseñado puede cambiar de proveedor sin reescribir la lógica de negocio — solo el adaptador de la API. Pydantic actúa como la interfaz común entre todos.

---

### Tabla comparativa de schemas de respuesta

|  | OpenAI | Anthropic | Gemini |
| --- | --- | --- | --- |
| **Acceso al texto** | `response.choices[0].message.content` | `response.content[0].text` | `response.text` |
| **Structured Output** | `.parse()` con Pydantic | Tool Use | `response_schema` |
| **System prompt** | En `messages` con `role: "system"` | Parámetro `system=` separado | Incluido en el prompt |
| **Modelo económico** | `gpt-4o-mini` | `claude-haiku-4-5-20251001` | `gemini-1.5-flash` |

---

## Bloque 4: Laboratorio Técnico — Pipeline completo (60 min)

### Consigna

Construir el pipeline completo de extracción y validación para Ortelana Textil. El script debe:

1. Leer las credenciales desde `.env` — nunca hardcodeadas.
2. Enviar un correo de Ortelana a la API eligiendo uno de los tres proveedores.
3. Usar Structured Outputs + Pydantic para garantizar el contrato.
4. Parsear la respuesta y mostrar los campos extraídos.
5. Manejar correctamente `ValidationError` y excepciones de red.

**Script base — completar eligiendo un proveedor:**

```python
import os
import json
from dotenv import load_dotenv
from pydantic import ValidationError
from schemas import PedidoTextilSchema

load_dotenv()

# ── Elegir proveedor (descomentar uno) ───────────────────────────────────────
# OPCIÓN A: OpenAI
# from openai import OpenAI
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# OPCIÓN B: Anthropic
# import anthropic
# client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# OPCIÓN C: Gemini
# import google.generativeai as genai
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ── Input de prueba ──────────────────────────────────────────────────────────
correo = """
Buenas! Soy de Textiles Norpatagonia, CUIT 30-71234567-8.
Necesitamos jersey 40/60 algodón-poliéster en gris melange,
unos 25 rollos. Presupuesto aprox $800.000. ¿Tienen en filial Córdoba?
"""

# ── Llamada a la API (completar según proveedor elegido) ─────────────────────
datos_validados = None  # Reemplazar con la llamada real

# ── Mostrar resultado ────────────────────────────────────────────────────────
if datos_validados:
    print(f"Intención:   {datos_validados.intencion}")
    print(f"CUIT:        {datos_validados.cuit}")
    print(f"Materiales:  {datos_validados.materiales_solicitados}")
    print(f"Monto:       ${datos_validados.monto_estimado:,.0f}")

```

**Preguntas de cierre:**

* ¿Qué pasa si cambiás `temperature=0` a `temperature=1`? ¿El JSON sigue siendo estable?
* ¿Qué técnica de prompting usaste? ¿Mejoraría con Few-shot?
* ¿En qué paso del flujo de Clase 2 conectarías este script con el SQL?

---

## Cierre y Material Asincrónico (30 min)

### Resumen de la clase

* **Zero-shot / Few-shot / CoT:** tres técnicas con distintos niveles de control sobre el output del modelo.
* **4 reglas del JSON confiable:** schema estricto + prohibir texto extra + fallback + validar en código.
* **Dos capas de garantía:** Structured Outputs (nivel API) + Pydantic (nivel aplicación).
* **`.env`:** las credenciales nunca van en el código — siempre en variables de entorno.
* **Multiproveedor:** el schema Pydantic es la interfaz común — el adaptador cambia, la lógica no.

---

### Material asincrónico — Entre Clase 3 y Clase 4

> [!IMPORTANT] **La Clase 4 arranca asumiendo que reflexionaron sobre esto**

**Desafío del contexto estático:**

Modificar el script de hoy e intentar que el LLM responda si hay stock físico de un producto, inyectando directamente en el prompt esta lista simulada de 100 artículos del catálogo de Ortelana:

```python
catalogo_simulado = [
    {"id": "TELA-001", "nombre": "Denim 12oz índigo", "stock": True, "sucursal": "central_bsas"},
    {"id": "TELA-002", "nombre": "Seda natural satinada", "stock": True, "sucursal": "filial_cordoba"},
    # ... 98 artículos más
]

prompt = f"""
Sos el asistente de stock de Ortelana.
Catálogo completo: {json.dumps(catalogo_simulado)}
Pregunta del distribuidor: "¿Tienen denim azul en Córdoba?"
"""

```

**Pregunta de reflexión — responder antes de la Clase 4:**

Si el catálogo de Ortelana cambia cada 3 minutos (ventas en tiempo real), ¿cuáles son los tres problemas críticos de ingeniería que surgen al meter todo el inventario dentro del System Prompt de forma estática?

*Pista: pensá en costo por token, ventana de contexto y latencia.*

---

### Conexión con Clase 4

En la Clase 4 resolvemos el problema que acabamos de crear: meter el catálogo entero en el prompt es costoso, lento y no escala. La solución son los **Embeddings y la búsqueda semántica** — en lugar de pasarle todo el catálogo al modelo, le pasamos solo los artículos más relevantes para la consulta. Eso es la base de RAG.

---

## Bibliografía de la Clase

* **Pydantic V2 Documentation.** Models, Fields and Custom Validators. docs.pydantic.dev
* **OpenAI API Reference.** Structured Outputs Guide. platform.openai.com/docs
* **Documentación oficial Anthropic.** Tool Use. docs.anthropic.com
* **Huyen, C. (2025).** *AI Engineering: Building Applications with Foundation Models.* O'Reilly. Capítulo 3.
* **White, J., et al. (2023).** *A Prompt Pattern Catalog to Enhance Prompt Engineering with ChatGPT.*