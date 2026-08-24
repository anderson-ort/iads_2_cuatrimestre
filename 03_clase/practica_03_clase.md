# Practica Propuesta Clase 03

Instalación de dependencias necesarias:

```bash
pip install google-genai pydantic python-dotenv

```

Configuración del archivo `.env` en la raíz del proyecto:

```bash
GEMINI_API_KEY=tu_api_key_de_google_ai_studio

```

Código de integración completo para la Clase 3:

```python
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Literal

# Carga de variables de entorno desde el archivo .env
load_dotenv()

# 1. CONTRATO DE DATOS EN PYDANTIC V2
class PedidoTextilSchema(BaseModel):
    """
    Esquema estricto de validacion para extraer intenciones
    y datos operativos de correos recibidos en Ortelana Textil.
    """
    intencion: Literal["CONSULTA_STOCK", "ALTA_DISTRIBUIDOR", "RECLAMO_CALIDAD", "DESCONOCIDO"] = Field(
        description="Categoria operativa asignada obligatoriamente segun el contenido del mensaje."
    )
    cuit: str | None = Field(
        default=None,
        description="CUIT del distribuidor expresado en 11 digitos numericos, o null si no esta."
    )
    materiales_solicitados: list[str] = Field(
        default_factory=list,
        description="Lista de telas o insumos textiles mencionados en la consulta."
    )
    monto_estimado: float = Field(
        default=0.0,
        description="Monto economico total expresado o calculado en el mensaje. 0.0 si no se menciona."
    )

    # Validacion personalizada para garantizar la integridad del CUIT
    @field_validator("cuit")
    @classmethod
    def limpiar_y_validar_cuit(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cuit_limpio = "".join(filter(str.isdigit, v))
        if cuit_limpio and len(cuit_limpio) != 11:
            raise ValueError("El CUIT debe contener exactamente 11 digitos numericos.")
        return cuit_limpio if cuit_limpio else None


# 2. INICIALIZACION DEL CLIENTE (SDK OFICIAL)
# El cliente detecta automaticamente la variable GEMINI_API_KEY del entorno
client = genai.Client()

system_instruction = """
Sos un asistente de operaciones para Ortelana Textil.
Extrae la informacion estructurada del mensaje del distribuidor respetando estrictamente el esquema JSON provisto.
No inventes informacion que no este explicita en el texto.
Si un dato no esta presente, asigna null o una lista vacia segun corresponda.
"""

correo_recibido = """
Hola gente de Ortelana!! Cómo andan??
Soy del taller 'Modas del Sur', mi CUIT es el 20-34556789-2.
Queríamos ver si tienen stock de denim de 12 en azul índigo.
Necesitamos cotizar unos 15 rollos urgente porque se nos cae un cliente grande.
Calculamos una compra de medio millón si nos hacen buen precio.
Avisen porfa!! Gracias!!
"""

# 3. LLAMADA A LA API CON STRUCTURED OUTPUTS
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=correo_recibido,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=PedidoTextilSchema,
            temperature=0.0,
        )
    )

    # Validacion y desempaquetado directo en el objeto Pydantic
    datos: PedidoTextilSchema = PedidoTextilSchema.model_validate_json(response.text)

    print("--- PIPELINE EXITOSO ---")
    print(f"Intencion:   {datos.intencion}")
    print(f"CUIT:        {datos.cuit}")
    print(f"Materiales:  {datos.materiales_solicitados}")
    print(f"Monto:       ${datos.monto_estimado:,.0f}")

except ValidationError as e:
    print(f"ERROR DE VALIDACION: Los datos extraidos rompieron el esquema Pydantic: {e}")
except Exception as e:
    print(f"ERROR DE INFRAESTRUCTURA O API: {e}")

```

---

## Qué se ve en el código

* **Uso del SDK `google-genai**`: Utiliza la librería oficial (`from google import genai`) disponible en la capa gratuita de Google AI Studio.
* **Separación de Credenciales con `python-dotenv**`: La clave de la API se lee automáticamente desde el entorno con `load_dotenv()`, evitando exponer secretos en el código fuente.
* **Declaración del Esquema Pydantic V2**: Se definen tipos estrictos (`Literal`, `list[str]`, `float`, `str | None`) e instrucciones de campo (`Field`) que le indican al modelo el propósito semántico de cada atributo.
* **Uso de `response_schema` en `GenerateContentConfig**`: Se le pasa directamente la clase Pydantic `PedidoTextilSchema` al parámetro de configuración de Gemini.
* **Limpieza y Validación Automática de Datos**: Un decorador `@field_validator` procesa el valor devuelto por el modelo para sanitizar cadenas (remover guiones de CUITs) y verificar su longitud.
* **Manejo explícito de Excepciones**: Diferencia fallas de red/sistema (`Exception`) de errores donde el modelo entregó datos que violan las reglas del negocio (`ValidationError`).

---

## Por qué son las mejores prácticas para el objetivo común

El objetivo de la Clase 3 es pasar de solicitar JSONs en lenguaje natural a **garantizar contratos de datos en producción sin fallas de ejecución**.

### 1. Constrained Decoding a Nivel Motor (Garantía de Proveedor)

Al usar `response_schema=PedidoTextilSchema` junto con `response_mime_type="application/json"`, Gemini restringe la generación de tokens a nivel de inferencia. Esto elimina de raíz los dos errores más comunes que rompían los scripts en el laboratorio:

* Previene respuestas con texto introductorio (ejemplo: "Aquí está tu JSON").
* Evita comillas faltantes o sintaxis JSON corrupta (`JSONDecodeError`).

### 2. Restricción Semántica Estricta con `Literal`

En lugar de permitir cualquier texto en el campo `intencion`, la directiva `Literal["CONSULTA_STOCK", "ALTA_DISTRIBUIDOR", ...]` obliga al LLM a elegir exclusivamente una de las opciones predefinidas. Si el modelo intenta responder `"consulta_de_stock"`, la API o Pydantic lo rechazarán antes de que afecte la base de datos SQL.

### 3. Doble Capa de Validación (LLM + Runtime Python)

La IA actúa como extractor probabilístico, pero el código Python mantiene la autoridad determinista:

* **Capa 1 (LLM):** Extrae el string `"20-34556789-2"` del correo en formato crudo.
* **Capa 2 (Python / `@field_validator`):** Normaliza el valor a `"20345567892"` y confirma que tiene exactamente 11 dígitos. Si la cadena extraída no cumple la regla, Python lanza un `ValidationError` en lugar de propagar un CUIT corrupto al sistema contable.

### 4. Elección del Modelo `gemini-2.5-flash`

Es la opción recomendada para tareas de extracción y estructuración en la capa gratuita. Ofrece latencias bajas, soporta asignación nativa de esquemas JSON y cuenta con límites de cuota (RPM) suficientes para pruebas de desarrollo continuas.

### 5. Control de Temperatura Determinista (`temperature=0.0`)

Ajustar la temperatura a cero reduce la variabilidad del modelo, obligándolo a elegir siempre la ruta probabilística más conservadora. Esto es crítico cuando se requiere que la extracción devuelva resultados idénticos ante entradas idénticas.