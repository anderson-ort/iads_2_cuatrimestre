# Clase 5 — Eslabón del Proyecto: Persistencia y ChromaDB (con Google GenAI)

---

## Lo que construiste vs. lo que el eslabón propuso

El eslabón original de la Clase 5 planteó una solución funcional con funciones sueltas. Tu implementación fue más lejos e introdujo tres decisiones de diseño que vale la pena nombrar explícitamente, porque van a aparecer de nuevo en las clases de FastAPI (Clase 11) y LangGraph (Clase 10):

| Concepto | Dónde lo usaste | Por qué importa hacia adelante |
|---|---|---|
| Repository Pattern | `chroma_repository.py` — `OrtelanaCatalogRepository` | Separa el CRUD de ChromaDB de la lógica de negocio. Cuando en la Clase 11 expongas esto como endpoint REST, el Service no necesita saber si el storage es ChromaDB, una base SQL, o un mock de tests |
| Service Layer | `chroma_service.py` — `OrtelanaCatalogService` | Centraliza la lógica de negocio (construir el `$and`, decidir qué es "nuevo", capturar el `ValueError` de stock). El `chroma_ortelana.py` queda como un script de orquestación delgado |
| Inyección de dependencias | Todos los constructores reciben `embedding_function` como parámetro | Permite cambiar de `gemini-embedding-001` a `sentence-transformers` (o un mock en tests) sin tocar el Repository ni el Service |

---

## Estructura del proyecto que entregaste

```
clase_5/
├── __init__.py
├── chroma_ortelana.py          <- punto de entrada / orquestador
├── auditoria_catalogos.py      <- Bloque 1: Paso 1
├── etl_unificacion.py          <- Bloque 1: Paso 2
├── purga_semantica.py          <- Bloque 1: Paso 3
├── prueba_persistencia_chroma.py
├── respuesta_whatsapp.py       <- ejercicio de frustración controlada
└── utils/
    ├── embedding_function.py   <- EmbeddingFunctionGemini (infra)
    ├── chroma_repository.py    <- OrtelanaCatalogRepository (acceso a datos)
    └── chroma_service.py       <- OrtelanaCatalogService (lógica de negocio)
```

---

## Parte 0 — Setup y variables de entorno

```bash
pip install chromadb google-genai python-dotenv
```

```bash
# .env
GEMINI_API_KEY=tu-clave-aqui
GEMINI_MODELO_EMBEDDING=gemini-embedding-001
GEMINI_MODELO_EMBEDDING_DIMENSION=768
```

Tu `EmbeddingFunctionGemini` lee modelo y dimensión directamente del entorno, lo que permite cambiarlos entre ejecuciones sin tocar código. Esto es exactamente la separación config/código que la Clase 3 introdujo con `.dotenv` para las API keys.

### Ejercicio para el alumno

Antes de seguir, verificá que podés instanciar la clase con cada `task_type` soportado sin que rompa:

```python
from utils.embedding_function import EmbeddingFunctionGemini

fn_doc = EmbeddingFunctionGemini(task_type="RETRIEVAL_DOCUMENT")
fn_sim = EmbeddingFunctionGemini(task_type="SEMANTIC_SIMILARITY")

# Ambas deben devolver listas de floats sin error
v1 = fn_doc(["Denim pesado de 12 oz"])
v2 = fn_sim(["Denim pesado de 12 oz"])

print(f"Dimensiones: {len(v1[0])} (doc) | {len(v2[0])} (sim)")
assert len(v1[0]) == len(v2[0]) == 768, "La dimension no es la esperada"
print("OK: ambos task_type devuelven vectores de la dimension correcta")
```

Registrá si los vectores `v1[0]` y `v2[0]` son idénticos o distintos para el mismo texto. Eso confirma o refuta si `task_type` afecta el vector real, no solo la intención declarada.

---

## Parte 1 — Auditoría de catálogos (Bloque 1, Paso 1)

Tu `Hallazgo` usa una clase con `__call__` en lugar de una función suelta. Eso tiene una consecuencia práctica concreta: las `LLAVES_ESPERADAS_RAIZ` y `LLAVES_ESPERADAS_METADATOS` se pasan al constructor, lo que significa que podés tener distintos auditores con distintos esquemas esperados para distintos proveedores.

```bash
python auditoria_catalogos.py
```

El reporte que genera detecta `tags_regionales` en tu propio `clase_5_pre-telas.json` como hallazgo de "Colisión Semántica de Tags" — no como un bug del código sino como el primer caso real de fricción de datos que el ETL va a resolver.

### Ejercicio para el alumno

1. Ejecutá el script y confirmá el hallazgo de `tags_regionales`.

2. Creá `taller_2.json` tomando 3 registros de tu archivo, cambiando los IDs a `T2-001`, `T2-002`, `T2-003`, y poniendo `en_stock` como el string `"true"` en uno de ellos. Corré el auditor sobre ese archivo también.

3. Completá esta tabla con los hallazgos reales de ambas corridas:

```markdown
| Taller | Discrepancia Estructural | Tipificación Errónea | Variante de Tags |
|---|---|---|---|
| Taller_Propio (clase_5_pre-telas.json) | | | tags_regionales en lugar de tags |
| Taller_2 (taller_2.json) | | en_stock como string "true" | |
```

4. Pensá en términos de diseño: ¿qué pasaría si el auditor no fuera una clase sino una función suelta, y necesitaras auditar catálogos de tres proveedores con distintos esquemas esperados? ¿Cómo cambia el diseño tener el esquema como parámetro del constructor en lugar de como constante global?

---

## Parte 2 — ETL de unificación (Bloque 1, Paso 2)

Tu `etl_unificacion.py` es correcto y tiene el `assert` de colisión de IDs que garantiza que el pipeline falla rápido y de forma visible si hay un problema de unicidad.

```bash
python etl_unificacion.py
```

### Ejercicio para el alumno

1. Descomentá la línea de `taller_2.json` en `fuentes` y volvé a correr. Confirmá que el `assert` no falla y que el JSON resultante tiene IDs con prefijos `G1-` y `G2-`.

2. Abrí `super_catalogo_ortelana.json` y verificá manualmente que:
   - El campo `tags_regionales` fue renombrado a `tags` en todos los registros.
   - El registro con `en_stock: "true"` (string) ahora aparece como `true` (booleano).

3. Hay un caso que `normalizar_registro` no cubre: ¿qué pasa si un registro tiene tanto `tags` como `tags_regionales`? La condición actual es `if "tags_regionales" in metadatos and "tags" not in metadatos`. Escribí un caso de prueba que demuestre ese escenario y decidí cómo debería manejarlo el ETL (¿conservar `tags`, conservar `tags_regionales`, o mergear ambas listas?).

---

## Parte 3 — Purga semántica de casi-duplicados (Bloque 1, Paso 3)

Tu `purga_semantica.py` tiene un cambio de diseño importante respecto al eslabón original: el `embedder` se inyecta como parámetro en `detectar_casi_duplicados()`, y en el `__main__` instanciás `EmbeddingFunctionGemini(task_type="SEMANTIC_SIMILARITY")` de forma explícita. Eso es correcto para comparar descripciones entre sí — `SEMANTIC_SIMILARITY` está optimizado para encontrar similitud entre dos textos arbitrarios, mientras que `RETRIEVAL_DOCUMENT` está optimizado para que un documento sea recuperable por una consulta.

También usás `combinations` de `itertools` en lugar de un doble `for` con índices, lo cual elimina las comparaciones redundantes `(A,B)` vs `(B,A)`.

```bash
python etl_unificacion.py    # primero generar super_catalogo_ortelana.json
python purga_semantica.py
```

### Ejercicio para el alumno

1. Con tu catálogo actual de 6 telas, el script probablemente no detecte ningún par. Para probar la detección, agregá al final de `super_catalogo_ortelana.json` este registro (que es una paráfrasis directa de TELA-001):

```json
{
  "id": "G1-TELA-TEST",
  "descripcion_semantica": "Jean de tela pesada, composicion 100% algodon rigido, teñido en azul indigo oscuro. Cuerpo firme y aspero, ideal para pantalones de trabajo y abrigos de invierno.",
  "metadatos": {
    "linea_textil": "indumentaria",
    "sucursal_disponible": "central_buenos_aires",
    "en_stock": true,
    "tags": ["denim", "jean"]
  }
}
```

2. Corré `purga_semantica.py` y confirmá que detecta el par `G1-TELA-001 <-> G1-TELA-TEST`.

3. Subí el `UMBRAL_CASI_DUPLICADO` a `0.15` y volvé a correr. Documentá qué pares nuevos aparecen (si aparecen) y si tienen sentido semántico real o son falsos positivos. Esto demuestra que el umbral es una decisión de negocio, no un número matemático fijo.

4. Reflexión de diseño: la estrategia de purga actual conserva siempre el primero del par y descarta el segundo. ¿Qué regla de negocio más sofisticada aplicarías para Ortelana? Por ejemplo: conservar el que tiene `en_stock=True`, o el que tiene mayor cantidad de `tags`, o el que tiene ID más corto (los originales del catálogo base).

---

## Parte 4 — El motor persistente: Repository + Service (Bloque 3)

Tu arquitectura en tres capas merece un diagrama antes de ver el código, porque la Clase 6 (LangChain + RAG) va a consumir exactamente `OrtelanaCatalogService` como la capa de Retrieval:

```
chroma_ortelana.py (orquestador)
    |
    v
OrtelanaCatalogService     <- reglas de negocio, construye where clauses
    |
    v
OrtelanaCatalogRepository  <- CRUD ChromaDB puro, sin reglas de negocio
    |
    v
EmbeddingFunctionGemini    <- infraestructura de embeddings
    |
    v
ChromaDB (disco)
```

```bash
python etl_unificacion.py        # 1. generar super_catalogo_ortelana.json
python purga_semantica.py        # 2. generar super_catalogo_ortelana_limpio.json
python chroma_ortelana.py        # 3. cargar en ChromaDB y probar búsquedas
```

### Ejercicio para el alumno

1. Ejecutá el flujo completo en el orden de arriba. Confirmá en la salida que:
   - La primera búsqueda devuelve resultados que incluyen el Denim (TELA-001).
   - Después de `service.actualizar_stock_por_evento("G1-TELA-001", False)`, la misma búsqueda con `solo_con_stock=True` **ya no lo devuelve**.

2. Ejecutá las Killer Queries de tu `clase_5_pre-pedidos_killers.txt` llamando directamente a `service.buscar_telas_para_vendedores()` desde un script de prueba:

```python
# killer_queries_test.py
from utils.chroma_repository import OrtelanaCatalogRepository
from utils.chroma_service import OrtelanaCatalogService
from utils.embedding_function import EmbeddingFunctionGemini

fn = EmbeddingFunctionGemini()
repo = OrtelanaCatalogRepository(embedding_function=fn)
service = OrtelanaCatalogService(repo)

# Killer Query 1: el vector busca telas gruesas, el metadato asegura tapiceria
r1 = service.buscar_telas_para_vendedores(
    query_semantica="Quiero armar unas fundas para los sillones de casa que aguanten a los perros",
    filtro_sucursal=None,
    solo_con_stock=True,
)
print("KQ1:", r1["documents"])

# Killer Query 2: TELA-003 (toldo PVC) tiene en_stock=False.
# Con solo_con_stock=True no deberia aparecer aunque el vector la encuentre perfecta.
r2 = service.buscar_telas_para_vendedores(
    query_semantica="Necesito urgente armar un toldo de PVC para un camion en Buenos Aires",
    filtro_sucursal="central_buenos_aires",
    solo_con_stock=True,
)
print("KQ2:", r2["documents"])
assert r2["documents"] == [[]] or "TELA-003" not in str(r2), \
    "ERROR: el metadato en_stock no esta filtrando correctamente"
print("KQ2 OK: TELA-003 filtrada por en_stock=False")
```

3. Mirá `update_metadata_fields` en `chroma_repository.py`. Usa `self.collection.update()` en lugar de `upsert()`. ¿Cuál es la diferencia entre ambos métodos en ChromaDB? Verificá en la documentación oficial qué pasa si llamás a `update()` con un ID que no existe (vs. lo que hace `upsert()`). El `ValueError` que levanta tu código lo anticipa — ¿eso es suficiente para producción?

---

## Parte 5 — Prueba de persistencia

```bash
# Terminal / sesión 1:
python chroma_ortelana.py       # carga la colección

# Cerrar el proceso completamente y abrir una nueva terminal:
python prueba_persistencia_chroma.py
```

### Ejercicio para el alumno

1. Confirmá que `prueba_persistencia_chroma.py` muestra el mismo número de registros sin haber llamado a la API de embeddings en esta segunda ejecución.

2. Buscá el directorio `./ortelana_vector_db/` que crea ChromaDB en disco. Listá su contenido y anotá los archivos que genera. ¿Reconocés algún formato de base de datos en esos archivos? (Pista: ChromaDB usa SQLite internamente para los metadatos).

3. Reflexión: tu `OrtelanaCatalogRepository` recibe `db_path` como parámetro del constructor (con default `"./ortelana_vector_db"`). ¿Cómo conectás esto con la práctica de `.env` de la Clase 3? ¿Qué variable de entorno agregarías al `.env` para que el path de la DB también sea configurable sin tocar código?

---

## Parte 6 — El ejercicio de frustración controlada

Tu `respuesta_whatsapp.py` tiene una mejora conceptual importante sobre lo que el eslabón propuso: introduce **dos estrategias en paralelo** — `generar_respuesta_control_flujo()` (el `if/else` manual) y `generar_respuesta_usando_servicio()` (el mensaje crudo directo a embeddings) — y las corre sobre el mismo lote de mensajes para comparar resultados.

```bash
python respuesta_whatsapp.py
```

### Ejercicio para el alumno (el más importante de la clase)

No se espera que ninguna de las dos estrategias funcione bien. Se espera que documentes exactamente dónde y por qué falla cada una. Completá esta tabla con los 6 mensajes:

```markdown
| # | Mensaje | Fallo de CONTROL_FLUJO | Fallo de PURE_SERVICE | Qué necesitaría el sistema para resolverlo bien |
|---|---|---|---|---|
| 1 | Casamiento en enero, transpira mucho | Mapea a "elegante fresca" pero pierde el contexto "transpira mucho" como restricción de material | Busca bien pero la respuesta es un string crudo, no un mensaje persuasivo | Un LLM que interprete la restricción y redacte |
| 2 | Sillon + gatos + Salta | Busca "filial_salta" que no existe en el catálogo: devuelve vacío | Busca sin filtro de sucursal: puede devolver stock de Córdoba, que el cliente no puede retirar | Extracción de entidades (sucursal, restricción de durabilidad) + verificación de sucursal disponible |
| 3 | Vestido de noche + lo mas barato | ? | ? | ? |
| 4 | Delantales para taller mecanico | ? | ? | ? |
| 5 | Seda natural + descuento por volumen | ? | ? | ? |
| 6 | Alergica a sinteticos, ropa de cama | ? | ? | ? |
```

Pistas para las filas incompletas:
- Mensaje 3: "lo más barato posible" es una restricción de precio que ni el `if/else` ni los embeddings pueden resolver — no existe en los metadatos del catálogo. ¿Qué campo agregarías al catálogo para soportarlo?
- Mensaje 5: el cliente hace una pregunta de negocio (descuento por volumen) completamente fuera del scope de la búsqueda de telas. Ninguna de las dos estrategias tiene una rama para eso. ¿Cómo lo detectarías antes de intentar buscar?
- Mensaje 6: "alérgica a sintéticos" es una **restricción de exclusión** sobre el campo `linea_textil` o composición — pero el catálogo no tiene un campo `composicion_material`. ¿Qué cambio de esquema en `clase_5_pre-telas.json` resolvería esto sin romper el ETL que ya construiste?

---

## Actualización del TP1

Agregá este bloque a la sección "Decisiones de Arquitectura" de tu `TP1_brief_solucion.md`:

```markdown
## Decisiones de Arquitectura — Clase 5

### Repository Pattern en la capa de persistencia vectorial

El acceso a ChromaDB se encapsuló en `OrtelanaCatalogRepository`, separado
de la lógica de negocio en `OrtelanaCatalogService`. Esto permite:

- Reemplazar ChromaDB por otro vector store (Pinecone, Weaviate) en la Clase 12
  sin tocar el Service ni los endpoints de FastAPI (Clase 11).
- Testear el Service en aislamiento inyectando un Repository mock.
- Centralizar todas las cláusulas `where` de ChromaDB en un único punto.

### trade-off de task_type en EmbeddingFunctionGemini

ChromaDB invoca la misma EmbeddingFunction para indexar documentos (.upsert)
y para embeber consultas (.query). La función actual usa RETRIEVAL_DOCUMENT
para ambos casos cuando se usa desde ChromaDB, y SEMANTIC_SIMILARITY cuando
se inyecta en purga_semantica.py.

Impacto estimado: bajo para el volumen actual del catálogo de Ortelana.
Si el catálogo escala a 10.000+ telas, se evaluaría implementar un
QueryEmbeddingFunction separado (mecanismo soportado por ChromaDB desde v0.4).
```

---

## Cierre y enlace con la Clase 6

Tu `OrtelanaCatalogService.buscar_telas_para_vendedores()` es la función que la Clase 6 va a consumir directamente como capa de Retrieval del primer pipeline RAG completo. La Clase 6 agrega exactamente la pieza que el ejercicio de frustración controlada demostró que falta: un LLM que recibe el diccionario de ChromaDB y lo convierte en lenguaje natural, sin el `if/else` que no escala.

La firma que vas a necesitar en la Clase 6 es exactamente la que ya tenés:

```python
# Lo que el pipeline RAG de la Clase 6 va a llamar:
service.buscar_telas_para_vendedores(
    query_semantica=query_del_cliente,
    filtro_sucursal=sucursal_extraida_por_el_llm,
    solo_con_stock=True,
)
# El resultado de esta llamada va a ir como contexto al LLM,
# y el LLM va a redactar la respuesta humana que hoy falta.
```
