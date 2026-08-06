# Clase 2 — Eslabón del Proyecto: Intent Mapping y el Colapso del Prompt Puro

## Objetivo de este entregable

En la Clase 1 documentaste que un LLM aislado alucina y que un prompt sin validación se rompe ante entradas adversariales. Esta clase no resuelve ese problema todavía con `Pydantic`: primero hay que **medir el problema a escala** y diseñar la frontera arquitectónica correcta entre lo que el modelo puede hacer (normalizar lenguaje) y lo que nunca debería hacer (validar hechos, ejecutar reglas de negocio).

Se crearan tres artefactos:

1. Un lote de 15 mensajes de stress semántico y el script que los procesa contra tu extractor actual, sin ninguna red de seguridad.
2. Un reporte de tasa de colapso, clasificando los errores por tipo.
3. El documento `intent_mapping_ortelana.md`, que diseña la frontera entre el LLM (Normalizador Semántico) y el backend determinista, conectado al código real del proyecto.

---

## Parte 1 — El Dilema del Arquitecto

> Casos de uso 
Antes de programar, fijá el concepto con tu propio caso. Completá esta tabla con dos ejemplos del proyecto Ortelana (no copies los del PDF):

| Tarea del sistema de Onboarding | Determinista o Probabilística | Por que |
|---|---|---|
| Verificar si un CUIT existe en AFIP | Determinista | Es un hecho consultable en una fuente de verdad externa (API), no una opinion |
| Interpretar "quiero vender ropa de bebes y tambien hago envios" como rubro=indumentaria_infantil | Probabilistica | Es traduccion de lenguaje natural ambiguo a una categoria, no hay una unica respuesta correcta verificable |
| [Tu ejemplo 1] | ? | ? |
| [Tu ejemplo 2] | ? | ? |

---

## Parte 2 — Laboratorio "El Contrato Roto"

### Paso 1: el lote de 15 mensajes

> Generación del lote de mensajes de prueba

La cátedra provee 15 correos híbridos reales. Como no tenés ese dataset exacto, construite el tuyo siguiendo la misma lógica: mensajes con ironía, datos faltantes, spanglish, formato roto y los dos casos de falla del PDF (falso positivo de CUIT y secuestro semántico).

`[lote_stress_semantico.py]`(./src/lote_stress_semantico.py)

### Paso 2: el script de stress (sin red de seguridad)

Este script es deliberadamente frágil. Usa un `SYSTEM_PROMPT` tal cual está, y procesa la respuesta con `json.loads()` puro, sin ningún `try/except` defensivo más allá del mínimo necesario para no frenar el lote completo.


`[stress_test_contrato_roto.py]`(./src/stress_test_contrato_roto.py)


### Paso 3: el reporte de tasa de colapso

`[analizar_reporte_colapso.py]`(./src/analizar_reporte_colapso.py)

### Ejercicios

1. Ejecutá los tres scripts en orden: `lote_stress_semantico.py` (verificá que cargan los 15 casos), `stress_test_contrato_roto.py` (con tu API key), `analizar_reporte_colapso.py`.
2. Anotá la `tasa_de_fallo_total_pct` que te dio. Esa es tu métrica de partida.
3. Revisá especialmente los casos `2` (CUIT inexistente pero verosímil) y `3` (secuestro semántico). Verificá manualmente: 
 -¿el modelo devolvió `cuit_valido: true` o algo equivalente sin haber verificado nada contra una fuente real? 
 -¿El caso 3 modificó algún campo fuera de lo que el mensaje legítimamente proveía (por ejemplo, inventando una categoría "VIP Oro")? Documentá tu observación en una frase por caso.

4. Guardá `reporte_contrato_roto.json`: en la Clase 3 vas a usar estos mismos 15 casos como suite de regresión para validar que tu modelo Pydantic efectivamente reduce esta tasa de fallo.

---

## Parte 3 — Diseño del Intent Mapping

Con el diagnóstico cuantitativo en mano, ahora sí diseñás la solución arquitectónica: el LLM deja de ser "el que decide si algo es válido" y pasa a ser exclusivamente un normalizador semántico que traduce `caos` a un contrato candidato. El backend determinista es el que ejecuta.

## Plantilla a completar

```markdown
# Intent Mapping — Sistema de Onboarding Ortelana Textil

## Principio de diseño
El LLM NUNCA valida hechos ni ejecuta logica de negocio. Solo traduce lenguaje
natural a una intencion clasificada y parametros candidatos. El backend
determinista (las funciones de 09_clase.md) es la unica capa con autoridad
para confirmar, escribir o rechazar.

## Matriz de Intent Mapping para Ortelana Textil

| Entrada de Usuario | Intencion Detectada (LLM) | Parametros Extraidos (LLM, candidatos) | Accion de Backend (Determinista) | Riesgo |
|---|---|---|---|---|
| "Quiero registrarme como distribuidor, mi CUIT es 30-71234567-8" | ALTA_DISTRIBUIDOR | {"cuit": "30-71234567-8", "razon_social": null} | `verificar_cuit_afip()` en 09_clase.md — consulta real, no confia en el texto | ALTO |
| "Tienen stock de jersey azul?" | CONSULTA_STOCK | {"articulo": "jersey", "color": "azul"} | SELECT determinista sobre inventario (fuera del alcance actual del proyecto) | BAJO |
| "El lote llego con manchas" | RECLAMO_CALIDAD | {"defecto": "mancha"} | `escalar_a_revision_manual()` en 09_clase.md | MEDIO |
| [Tu ejemplo: el caso 3 del stress test, secuestro semantico] | ? | ? | ? | ? |
| [Tu ejemplo: el caso 2 del stress test, CUIT verosimil pero falso] | ? | ? | ? | ? |

## Regla de frontera (la mas importante del documento)
Completa esta frase con tus propias palabras, usando el caso 2 de tu stress
test como ejemplo concreto:

"El campo `cuit_valido` JAMAS puede ser generado por el LLM porque ____________.
En el codigo del proyecto, ese campo solo puede originarse en ____________
(funcion y archivo)."
```

### Ejercicio para el alumno

1. Completá las dos filas faltantes de la matriz usando tus propios casos 2 y 3 del stress test.
2. Completá la "Regla de frontera" señalando exactamente la función que debería ser la única fuente de verdad para `cuit_valido` (pista: `verificar_cuit_afip`).
3. Guardá el documento como `intent_mapping_ortelana.md` en la raíz del proyecto, junto a `00_PEAS_ortelana.md`.

---

## Cierre y enlace con la Clase 3

Llevás a la Clase 3 dos números concretos: la tasa de fallo de tu `stress_test_contrato_roto.py` y la matriz de Intent Mapping que define qué campos jamás debe decidir el LLM. La Clase 3 introduce Pydantic exactamente para cerrar la brecha que mediste acá: vas a tomar el mismo `SYSTEM_PROMPT` y los mismos 15 mensajes, agregarles un modelo de validación con tipos estrictos, y volver a correr el stress test para comparar la nueva tasa de fallo contra la de hoy.
