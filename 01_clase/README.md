# Clase 1 — Eslabón del Proyecto: Arquitectura PEAS y Límites del Modelo Aislado

## Objetivo de este entregable

Antes de tocar el código de extracción, RAG o agentes (que ya existe en las clases siguientes), este eslabón te pide construir el documento fundacional del proyecto: el modelado PEAS del sistema de Onboarding de Ortelana Textil, respaldado por dos experimentos de código que demuestran *por qué* hace falta esa arquitectura y no alcanza con un chat web suelto.

Vas a producir tres artefactos:

1. Evidencia de la alucinación de un LLM sin contexto sistémico (Experimento 1).
2. Evidencia de la fragilidad de un prompt sin validación estructural (Experimento 2).
3. El documento `00_PEAS_ortelana.md` con el modelado completo de los 5 pilares, conectado al código real del proyecto.

---

## Parte 1 — Experimento: "El Proveedor Enojado" (sin código)

> Este paso es manual, no requiere Python. Sirve como base empírica para el documento PEAS.

### Instrucciones

1. Abrí ChatGPT (sin uso de websearch tool) o Gemini en su interfaz web (sin ningún system prompt personalizado).
2. Copiá y pegá el siguiente mensaje, simulando ser un distribuidor enojado:

```text
Soy distribuidor mayorista de Ortelana Textil desde hace 8 meses. Hoy me rechazaron
un pedido de reposición citando la "Política de Suspensión por Mora Cat. C" de la
empresa. Quiero que me expliques EXACTAMENTE qué dice esa política, cuántos días de
mora permite antes de suspender la cuenta, y qué artículo del reglamento interno la
respalda. Necesito la cita textual para reclamar.
```

3. Guardá la respuesta completa (captura de pantalla o copia el texto).
4. Repetí el ejercicio con una segunda pregunta inventada (ejemplo: "¿cuál es el descuento por volumen para Responsables Inscriptos con más de 12 meses de antigüedad?").

### Qué vas a observar 
>
El modelo va a generar una respuesta verosímil, con número de artículo, porcentaje o plazo concreto, **inventado por completo**. Esa política no existe en ningún documento real de Ortelana (de hecho, no existe ninguna "Política de Suspensión por Mora Cat. C"). Esto suele pasar en muchas etapas donde no existe las herramientas externas (tools) como WebSearch

### Por qué importa para el proyecto

 El LLM no "sabe" las políticas de Ortelana: las tiene que leer en el contexto que el sistema le provee en tiempo de ejecución. Sin esa base de conocimiento, cualquier respuesta es una alucinación con apariencia de hecho.

---

## Parte 2 — Experimento de código: "El Prompt Roto"

Objetivo: Tratar de romper nuestra app con entradas adversariales previo a cualquier guardrail.

- [Codigo Initial](./src/main.py)


### Resolver las preguntas

1. Ejecutá `main.py` con tu propia API key.

```txt
Si te fijás en la `respuesta_cruda` del Caso 1 y del Caso 3, el JSON que devolvió Gemini está perfecto. El problema es que Gemini es "demasiado educado" y envolvió el resultado en bloques de código para que se vea lindo en una pantalla:

> **Por qué falló el parseo:** La función `json.loads()` de Python espera que el texto empiece estrictamente con `{`. Al encontrarse con ` 
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

```

2. Agregá un quinto caso de tu invención (por ejemplo, un mensaje en otro idioma, o uno con emojis y jerga, o uno donde el distribuidor manda dos CUITs distintos).

```py
# --- QUINTO CASO ADVERSARIAL (Jerga, Emojis y Ambigüedad de Identidades) ---
{
    "nombre": "Doble Identidad y Jerga Argentina",
    "mensaje": (
        "Che, todo bien? 🇦🇷 Te paso el dato de la pyme familiar. La fábrica vieja "
        "tenía el CUIT 30-11111111-2, pero ojo que ahora el contador nos hizo facturar "
        "con la nueva SRL de mi primo Carlos, que tiene CUIT 30-22222222-3 y se llama "
        "La Algodonera de Quilmes. Mandanos un mail a carlitos@algodonera.com.ar, "
        "hacemos hilados finos al toque."
    )
}
```

3. Documentá: ¿cuántos de los 5 casos rompieron el JSON? ¿Cuál fue el patrón de falla más común (texto antes del JSON, formato de lista, explicación adicional, JSON con comillas simples)?
4. Guardá el archivo `evidencia_prompt_roto.json` que genera el script: es la evidencia que vas a citar en el documento PEAS y que vas a volver a usar en la Clase 3 cuando construyas el extractor robusto con validación.

No se espera que arregles el prompt todavía. El objetivo de esta clase es **diagnosticar**, no resolver. La solución (Pydantic, reintentos, parsers tolerantes) llega en clases posteriores.

---

## Parte 3 — Economía del Token (anclaje práctico)

Antes de escribir el documento PEAS, conviene entender el costo real de las decisiones de diseño de prompt, porque el pilar "Objetivo" del PEAS incluye latencia y costo.

```bash
pip install tiktoken
```

- [Tokenizacion y cantidad de tokens](./src/tokens.py)

### Ejercicio para el alumno

1. Ejecutá el script y registrá los cuatro números resultantes.
2. Respondé en una frase: ¿vale la pena el prompt largo (con reglas explícitas y normalización de CUIT) a pesar del costo extra en tokens? Justificá con el caso "Inyección de instrucciones" del Experimento 2.
3. Este resultado va directo al pilar **Objetivo** del PEAS: es el primer dato cuantitativo de costo/latencia del sistema.

---

## Parte 4 — El Documento PEAS

Con la evidencia de las Partes 1, 2 y 3, completá la siguiente plantilla.

```markdown
# PEAS — Sistema de Onboarding Ortelana Textil

## 1. Entorno (Environment)
- ERP legado mockeado
- Sistema de notificacion
- Base de politicas comerciales: `BASE_CONOCIMIENTO_ORTELANA`
- Servidor de correo / canal WhatsApp: representado por el campo `canal` en
  `SolicitudOnboardingRequest`

## 2. Sensores (Perception)
- Mensaje de texto libre del distribuidor: parametro `mensaje_original` que
  recibe `nodo_extraer_datos()`
- Endpoint HTTP: `POST /onboarding/solicitud`
- [Completar: que otro sensor le falta al sistema actual? Pista: PDF/imagen adjunta]

## 3. Base de Conocimiento (Knowledge Base)
- Coleccion ChromaDB `politicas_internas` 
- Coleccion ChromaDB `historial_clientes`
- Log de auditoria SQLite, tabla `decisiones`
- [Completar: que falta para que esta base sea actualizable sin tocar codigo?]

## 4. Actuadores (Action)
- `registrar_solicitud_onboarding()` — escribe en el sistema
- `notificar_distribuidor()` — efecto secundario hacia afuera
- `escalar_a_revision_manual()` — crea ticket para humanos
- Respuesta JSON de FastAPI: `ResultadoOnboardingResponse`

## 5. Objetivo (Objective)
- Metrica de tiempo: reducir el proceso de dias a minutos (linea base: 2-5
  dias habiles segun 01_clase.md)
- Metrica de calidad: fidelidad RAGAS > 0.85 (umbral definido en 08_clase.md)
- Metrica de costo: [completar usando los numeros de tu script economia_tokens.py]
- Metrica de seguridad: tasa de fallos de formato estructural medida en el
  Experimento 2 = ___ de 5 casos (completar con tu resultado)
```

### Instrucciones finales para el alumno

1. Completá los tres corchetes `[Completar: ...]` con tu propio análisis.
2. Guardá este documento como `00_PEAS_ortelana.md` en la raíz del repositorio.
3. Adjuntá (o referenciá) `evidencia_prompt_roto.json` y los números de `tokens.py` como anexos.
