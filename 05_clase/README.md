# Clase 5: Persistencia y Bases de Datos Vectoriales con ChromaDB

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial

**Objetivo Técnico:** Migrar el índice FAISS volátil de Clase 4 a una base de datos vectorial persistente con ChromaDB, implementar filtrado híbrido (semántica + metadatos), construir el Súper-Catálogo unificado de Ortelana Textil aplicando ETL y purga semántica de duplicados, y sentar las bases de conocimiento del TP1 de cada grupo.

> [!NOTE] **Para quienes vienen de las Microcredenciales**
> En las microcredenciales mencionaron ChromaDB como parte del stack de RAG. En esta clase lo implementamos desde cero: persistencia real en disco, colecciones, metadatos y filtros combinados. Al final de la clase cada grupo tiene su propia base de conocimiento lista para conectar con RAG en Clase 6.

---

## Planificación de la Clase

| Bloque | Contenido |
| --- | --- |
| **Bloque 1** | Auditoría, ETL en vivo y purga semántica del catálogo |
| **Bloque 2** | Arquitectura de bases de datos vectoriales — de FAISS a ChromaDB |
| **Bloque 3** | Laboratorio: Súper-Catálogo de Ortelana sobre ChromaDB |
| **Bloque 4** | TP1: cada grupo construye su propia base de conocimiento |
| **Cierre** | El quiebre de la experiencia y conexión con Clase 6 |

---

## Bloque 1: Auditoría, ETL en Vivo y Purga Semántica

### La clase no empieza con una base limpia

Los grupos trajeron de la tarea asincrónica su `catalogo_ortelana.json` con 15 telas. La realidad: cada grupo lo armó con sus propios criterios. Ortelana acaba de adquirir tres talleres independientes y necesita unificar sus catálogos — con todos los vicios de carga que eso implica.

---

### Paso 1 — Rotación "Estilo Vóley"

Cada grupo rota su archivo al grupo siguiente. Auditan el catálogo recibido bajo tres métricas:

**Métrica 1 — Discrepancia estructural**
¿Respetaron las claves exactas de la especificación?

```python
# Correcto              # Incorrecto
"en_stock": True       "stock_disponible": True
"sucursal_disponible"  "sucursal"
"tags_regionales"      "tags" / "palabras_clave"

```

**Métrica 2 — Tipificación errónea**
¿Cargaron booleanos como strings?

```python
# Correcto        # Incorrecto
"en_stock": True    "en_stock": "true"
                    "en_stock": "True"
                    "en_stock": 1

```

**Métrica 3 — Colisión semántica de tags**
¿Qué términos usaron para la jerga regional?

```
Grupo A: ["jean", "vaquero"]
Grupo B: ["mezclilla", "denim"]
Grupo C: ["tela de jeans", "pantalón"]
-> Son todos el mismo producto pero con tags incompatibles

```

> [!TIP] **Para el docente**
> Anotar en el pizarrón las inconsistencias que van encontrando los grupos. Esa lista es el insumo del ETL del Paso 2 — la fricción real genera la necesidad de la solución.

---

### Paso 2 — El ETL de la Galera

El docente toma el control de la pantalla. Escenario: "Tenemos que unificar estos catálogos ya mismo para la operación de la semana que viene."

```python
import json
import os
from pathlib import Path

def etl_unificar_catalogos(directorio_entregas: str) -> list[dict]:
    """
    Lee todos los JSON del directorio, normaliza estructuras
    y resuelve la colisión de IDs prefijando con el ID del grupo.
    """
    catalogo_unificado = []

    for i, archivo in enumerate(Path(directorio_entregas).glob("*.json"), start=1):
        grupo_id = f"G{i}"
        with open(archivo) as f:
            telas = json.load(f)

        for tela in telas:
            # Resolver colisión de IDs: TELA-001 -> G1-TELA-001
            tela["id"] = f"{grupo_id}-{tela['id']}"

            # Normalizar booleanos que llegaron como strings
            if isinstance(tela.get("metadatos", {}).get("en_stock"), str):
                tela["metadatos"]["en_stock"] = tela["metadatos"]["en_stock"].lower() == "true"

            # Normalizar nombres de claves incorrectos
            meta = tela.get("metadatos", {})
            if "sucursal" in meta and "sucursal_disponible" not in meta:
                meta["sucursal_disponible"] = meta.pop("sucursal")
            if "stock_disponible" in meta:
                meta["en_stock"] = meta.pop("stock_disponible")

            catalogo_unificado.append(tela)

    print(f"ETL completado: {len(catalogo_unificado)} telas unificadas de {i} grupos")
    return catalogo_unificado

# catalogo_bruto = etl_unificar_catalogos("./entregas_grupos/")

```

---

### Paso 3 — Purga Semántica de Casi-Duplicados

Tras unificar, aparece el problema que el software tradicional no puede resolver:

```
G1-TELA-001: "Denim pesado de 12 oz, 100% algodón rígido con teñido índigo"
G3-TELA-001: "Jean grueso de 12 onzas, algodón duro color azul oscuro"

```

IDs distintos, strings distintos. Pero para Ortelana es exactamente el mismo rollo de tela.

```python
import chromadb
import numpy as np
from chromadb.utils import embedding_functions
from google.colab import userdata

# Inicializar ChromaDB efímero solo para la purga
client_purga = chromadb.Client()
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=userdata.get('OPENAI_API_KEY'),
    model_name="text-embedding-3-small"
)

col_purga = client_purga.create_collection("purga_tmp", embedding_function=openai_ef)

# Cargar todas las descripciones
textos = [t["descripcion_semantica"] for t in catalogo_bruto]
ids    = [t["id"] for t in catalogo_bruto]
col_purga.add(documents=textos, ids=ids)

# Detectar casi-duplicados
UMBRAL_DUPLICADO = 0.08  # distancia coseno < 0.08 -> prácticamente idénticos

ids_a_eliminar = set()
for tela in catalogo_bruto:
    if tela["id"] in ids_a_eliminar:
        continue
    resultados = col_purga.query(
        query_texts=[tela["descripcion_semantica"]],
        n_results=3
    )
    for id_similar, distancia in zip(
        resultados["ids"][0][1:],       # Saltar el primero (es sí mismo)
        resultados["distances"][0][1:]
    ):
        if distancia < UMBRAL_DUPLICADO:
            print(f"Casi-duplicado detectado (dist={distancia:.4f}):")
            print(f"   Conservar: {tela['id']} — {tela['descripcion_semantica'][:60]}...")
            print(f"   Eliminar:  {id_similar}")
            ids_a_eliminar.add(id_similar)

# Purgar el catálogo
super_catalogo = [t for t in catalogo_bruto if t["id"] not in ids_a_eliminar]
print(f"\nSúper-Catálogo listo: {len(super_catalogo)} telas únicas "
      f"({len(ids_a_eliminar)} duplicados eliminados)")

```

> [!IMPORTANT] **El punto que tiene que quedar claro**
> Un `SELECT DISTINCT` en SQL no hubiera encontrado estos duplicados — los strings son distintos. Solo la búsqueda semántica puede detectar que "Denim pesado 12 oz" y "Jean grueso 12 onzas" son el mismo producto. Esta es la primera vez en la cursada que usamos embeddings para **limpiar datos**, no solo para buscar.

---

## Bloque 2: De FAISS a ChromaDB — Arquitectura

### Los tres límites de FAISS que ChromaDB resuelve

En Clase 4 demostramos la volatilidad de FAISS — al reiniciar Colab, el índice desaparece. Pero hay dos problemas más:

| Problema | FAISS | ChromaDB |
| --- | --- | --- |
| **Persistencia** | Muere con el proceso | Guarda en disco (SQLite por debajo) |
| **Metadatos** | Solo vectores — el texto vive en un dict paralelo en Python | ID + Vector + Documento + Metadatos en un solo objeto atómico |
| **Filtrado** | Buscar semántico, luego filtrar en Python (post-filtering ineficiente) | Pre-filtering nativo: reduce el espacio antes del cálculo vectorial |

---

### El objeto atómico de ChromaDB

En FAISS el programador tenía que mantener dos estructuras sincronizadas: el índice de vectores y un diccionario Python con los textos y metadatos. Si una se desincronizaba, el sistema fallaba silenciosamente.

ChromaDB unifica todo en un solo objeto:

```
┌─────────────────────────────────────────────────┐
│ ID: "G1-TELA-001"                               │
│ Documento: "Denim pesado de 12 oz, 100%..."     │
│ Embedding: [0.12, -0.34, 0.87, ...]  (1536 dims)│
│ Metadata: {                                     │
│   "linea_textil":      "indumentaria",          │
│   "sucursal_disponible": "central_buenos_aires",│
│   "en_stock":          True,                    │
│   "tags_regionales":   ["jean", "vaquero"]      │
│ }                                               │
└─────────────────────────────────────────────────┘

```

---

### Pre-filtering vs Post-filtering

```
POST-FILTERING (FAISS + Python) — ineficiente:
Consulta -> calcular similitud con las 500 telas -> devolver top-10 -> filtrar en Python
                                                                    ^ ya calculó todo para nada

PRE-FILTERING (ChromaDB nativo) — eficiente:
Consulta -> filtrar por sucursal='cordoba' AND stock=True (quedan 8 telas)
         -> calcular similitud solo sobre esas 8
         -> devolver top-2

```

> [!TIP] **Pregunta #1**
> Con 500 telas y un filtro que deja 8 candidatas, ¿cuántos cálculos de similitud coseno ahorra ChromaDB respecto a FAISS?
> **Análisis:** 492 cálculos. En producción con millones de documentos, la diferencia es de minutos vs milisegundos. El pre-filtering es lo que hace viable la búsqueda híbrida a escala.

---

### Comparativa del ecosistema

|  | ChromaDB | Pinecone | FAISS | pgvector |
| --- | --- | --- | --- | --- |
| **Tipo** | Open source local | SaaS cloud | Librería | Extensión PostgreSQL |
| **Persistencia** | Sí (Disco local) | Sí (Cloud) | No (Solo memoria) | Sí (PostgreSQL) |
| **Metadatos + filtros** | Sí | Sí | No | Sí |
| **Costo** | Gratis | Pago (free tier) | Gratis | Gratis |
| **Cuándo usarlo** | Desarrollo y cursada | Producción cloud | Prototipado rápido | Ya tenés PostgreSQL |

> [!NOTE] **¿Por qué ChromaDB en la cursada y no Pinecone?**
> Pinecone es la opción más usada en producción pero requiere cuenta y API key con límites. ChromaDB corre 100% local sin ninguna cuenta. En Clase 14 (AIOps) vemos cómo migrar a Pinecone para producción real.

---

## Bloque 3: Laboratorio — Súper-Catálogo de Ortelana en ChromaDB

### Instalación y configuración

```python
!pip install chromadb openai --quiet

```

```python
import chromadb
from chromadb.utils import embedding_functions
from google.colab import userdata, drive

# Montar Drive para persistencia real entre sesiones de Colab
drive.mount('/content/drive')

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=userdata.get('OPENAI_API_KEY'),
    model_name="text-embedding-3-small"
)

# PersistentClient — los datos sobreviven al reinicio de Colab
client = chromadb.PersistentClient(path="/content/drive/MyDrive/ortelana_vectordb")

```

> [!WARNING] **Sin Drive mount, el PersistentClient guarda en /content/ — que Colab borra al desconectar.**
> Con Drive mount, los datos viven indefinidamente. Demostrar en clase: reiniciar el entorno, volver a conectar con `PersistentClient` y verificar que los documentos siguen ahí sin regenerar embeddings.

---

### Crear la colección del Súper-Catálogo

```python
# get_or_create: si ya existe la usa, si no la crea — patrón seguro
coleccion = client.get_or_create_collection(
    name="super_catalogo_ortelana",
    embedding_function=openai_ef,
    metadata={"hnsw:space": "cosine"}  # Similitud coseno en lugar de L2
)

print(f"Colección: {coleccion.name}")
print(f"Documentos actuales: {coleccion.count()}")

```

---

### Ingesta con upsert — robustez ante cambios de stock

```python
# El Súper-Catálogo unificado (resultado del ETL del Bloque 1)
super_catalogo_ortelana = [
    {
        "id": "TELA-001",
        "descripcion_semantica": "Denim pesado de 12 oz, 100% algodón rígido con teñido índigo intenso. Tacto rústico, alta resistencia al roce y cuerpo firme. Ideal para camperas y pantalones.",
        "metadatos": {"linea_textil": "indumentaria", "sucursal_disponible": "central_buenos_aires", "en_stock": True, "tags_regionales": ["jean", "vaquero", "mezclilla"]}
    },
    {
        "id": "TELA-002",
        "descripcion_semantica": "Seda natural con acabado satinado, caída fluida y brillo sofisticado. Tejido muy liviano y fresco al tacto, diseñado para vestidos de gala.",
        "metadatos": {"linea_textil": "alta_costura", "sucursal_disponible": "filial_cordoba", "en_stock": True, "tags_regionales": ["seda", "satén", "vestido de fiesta"]}
    },
    {
        "id": "TELA-003",
        "descripcion_semantica": "Lona cobertora industrial con recubrimiento de PVC impermeable. Entramado de poliéster de alta tenacidad, nula flexibilidad y máxima resistencia al agua.",
        "metadatos": {"linea_textil": "industrial", "sucursal_disponible": "central_buenos_aires", "en_stock": False, "tags_regionales": ["toldo", "carpa", "pvc", "camión"]}
    },
    {
        "id": "TELA-004",
        "descripcion_semantica": "Gabardina elastizada de 8 oz. Mezcla de algodón y spandex que otorga comodidad sin perder estructura. Textura diagonal clásica.",
        "metadatos": {"linea_textil": "indumentaria", "sucursal_disponible": "filial_cordoba", "en_stock": True, "tags_regionales": ["pantalón de vestir", "uniforme", "elastizado"]}
    },
    {
        "id": "TELA-005",
        "descripcion_semantica": "Gasa de algodón translúcida y ultra respirable. Ideal para prendas de verano muy sueltas y superposiciones. Requiere lavado a mano.",
        "metadatos": {"linea_textil": "alta_costura", "sucursal_disponible": "central_buenos_aires", "en_stock": False, "tags_regionales": ["transparencia", "verano", "liviano", "velo"]}
    },
    {
        "id": "TELA-006",
        "descripcion_semantica": "Chenille de tapicería aterciopelado. Tejido grueso con tratamiento antimanchas, diseñado para soportar el roce constante en muebles de interior.",
        "metadatos": {"linea_textil": "tapiceria", "sucursal_disponible": "filial_cordoba", "en_stock": True, "tags_regionales": ["sillón", "funda", "terciopelo", "decoración"]}
    },
]

# upsert en lugar de add -> si el ID ya existe, actualiza; si no, crea
# Esto permite re-ejecutar el script sin duplicar registros
if coleccion.count() == 0:
    coleccion.upsert(
        documents=[t["descripcion_semantica"] for t in super_catalogo_ortelana],
        metadatas=[t["metadatos"] for t in super_catalogo_ortelana],
        ids=[t["id"] for t in super_catalogo_ortelana]
    )
    print(f"Súper-Catálogo cargado: {coleccion.count()} telas indexadas")
else:
    print(f"Colección ya existente: {coleccion.count()} telas (0 tokens consumidos)")

```

---

### Simular un evento de negocio — actualización de stock en caliente

La sucursal de Buenos Aires se queda sin denim. Actualizar solo el metadato sin tocar el vector:

```python
# upsert con el mismo ID actualiza el registro sin duplicar
coleccion.upsert(
    ids=["TELA-001"],
    documents=["Denim pesado de 12 oz, 100% algodón rígido con teñido índigo intenso. Tacto rústico, alta resistencia al roce y cuerpo firme. Ideal para camperas y pantalones."],
    metadatas=[{"linea_textil": "indumentaria", "sucursal_disponible": "central_buenos_aires",
                "en_stock": False,  # Stock actualizado
                "tags_regionales": ["jean", "vaquero", "mezclilla"]}]
)
print("Stock de TELA-001 actualizado a False")

# Verificar
item = coleccion.get(ids=["TELA-001"])
print(f"Stock actual: {item['metadatas'][0]['en_stock']}")

```

> [!TIP] **Pregunta #2**
> ¿Por qué usamos `upsert` en lugar de `update`?
> **Análisis:** `update` falla si el ID no existe. `upsert` (update + insert) crea el registro si no existe y lo actualiza si ya está. En producción, donde los IDs pueden venir de sistemas externos con lógica propia, `upsert` es más robusto. Es el mismo concepto que `INSERT OR REPLACE` en SQL.

---

### El CLI de búsqueda híbrida — entregable del laboratorio

```python
def buscar_tela_ortelana(
    query_semantica: str,
    filtro_sucursal: str = "cualquiera",
    solo_con_stock: bool = True,
    n_resultados: int = 2
) -> None:
    """
    Motor de búsqueda interno para los vendedores de Ortelana.
    Combina búsqueda semántica con filtros duros de metadatos.
    """
    # Construir el filtro de metadatos
    condiciones = []
    if solo_con_stock:
        condiciones.append({"en_stock": {"$eq": True}})
    if filtro_sucursal != "cualquiera":
        condiciones.append({"sucursal_disponible": {"$eq": filtro_sucursal}})

    # Armar el where con operadores nativos de ChromaDB
    if len(condiciones) == 0:
        where = None
    elif len(condiciones) == 1:
        where = condiciones[0]
    else:
        where = {"$and": condiciones}

    resultados = coleccion.query(
        query_texts=[query_semantica],
        n_results=n_resultados,
        where=where
    )

    print(f"\nBúsqueda: '{query_semantica}'")
    print(f"   Filtros: sucursal={filtro_sucursal} | solo_stock={solo_con_stock}")
    print("-" * 60)

    if not resultados["documents"][0]:
        print("Sin resultados con estos filtros.")
        return

    for doc, dist, meta, id_ in zip(
        resultados["documents"][0],
        resultados["distances"][0],
        resultados["metadatas"][0],
        resultados["ids"][0]
    ):
        stock_estado = "[EN STOCK]" if meta["en_stock"] else "[SIN STOCK]"
        print(f"[{id_}] dist={dist:.4f} {stock_estado}")
        print(f"  {doc[:90]}...")
        print(f"  Sucursal: {meta['sucursal_disponible']} | Línea: {meta['linea_textil']}")

```

> [!IMPORTANT] **Sanity check para el docente**
> El filtro correcto en ChromaDB usa operadores nativos. Si un alumno escribe código Python condicional dentro del `where`, está haciendo post-filtering manual — el sistema va a funcionar pero va a ser ineficiente. El filtro correcto luce así:
> ```python
> where={"$and": [
>     {"sucursal_disponible": {"$eq": "filial_cordoba"}},
>     {"en_stock": {"$eq": True}}
> ]}
> 
> ```
> 
> 

---

### Killer Queries — ejecutar con el grupo

```python
# Query 1: Poder semántico puro
buscar_tela_ortelana(
    "Busco algo fresco para un vestido de verano hoy en Córdoba",
    filtro_sucursal="filial_cordoba",
    solo_con_stock=True
)
# Esperado: TELA-002 (Seda) — aunque el cliente no dijo "seda"

# Query 2: El metadato salva el día
buscar_tela_ortelana(
    "Necesito tela resistente y duradera para trabajo pesado",
    filtro_sucursal="central_buenos_aires",
    solo_con_stock=True
)
# TELA-001 (Denim) está sin stock en Buenos Aires -> no debe aparecer
# TELA-003 (Lona) tampoco tiene stock -> no debe aparecer
# ¿Qué devuelve? -> discutir con el grupo

# Query 3: Jerga regional
buscar_tela_ortelana(
    "jean azul clásico",
    filtro_sucursal="cualquiera",
    solo_con_stock=True
)
# ¿Lo resuelve el vector de descripcion_semantica o los tags_regionales?

# Query 4: Sin stock — ver qué hay aunque no esté disponible
buscar_tela_ortelana(
    "gasa translúcida para superposiciones",
    filtro_sucursal="cualquiera",
    solo_con_stock=False  # Ver todo aunque no tenga stock
)

```

---

## Bloque 4: TP1 — Base de Conocimiento Propia

### Consigna

Cada grupo replica el pipeline de Ortelana para su dominio del TP1. Al terminar la clase, la base tiene que estar lista para conectar con RAG en Clase 6.

```python
# Template para el TP1 — completar según el dominio

RUTA_BD_TP1 = "/content/drive/MyDrive/DSI_TP1/vectordb"

client_tp1  = chromadb.PersistentClient(path=RUTA_BD_TP1)
coleccion_tp1 = client_tp1.get_or_create_collection(
    name="base_conocimiento_tp1",
    embedding_function=openai_ef,
    metadata={"hnsw:space": "cosine"}
)

# Esquema de metadatos — definir antes de cargar
# Regla: metadato = campo por el que el usuario podría querer filtrar
ESQUEMA_METADATOS = {
    # Legal:   "tipo": "ley|sentencia|doctrina", "jurisdiccion": "nacional|provincial", "vigente": True
    # Salud:   "tipo": "guia_clinica|protocolo", "especialidad": "cardiologia|...", "nivel_evidencia": "A|B|C"
    # Retail:  "categoria": "ropa|calzado|...", "temporada": "verano|invierno", "en_stock": True
    # RRHH:    "area": "tech|comercial|...", "nivel": "junior|senior", "activo": True
}

DOCUMENTOS_TP1 = [
    # Mínimo 15 documentos con descripcion_semantica rica
    # y metadatos según el esquema definido arriba
]

if coleccion_tp1.count() == 0:
    coleccion_tp1.upsert(
        documents=[d["texto"] for d in DOCUMENTOS_TP1],
        metadatas=[d["metadata"] for d in DOCUMENTOS_TP1],
        ids=[d["id"] for d in DOCUMENTOS_TP1]
    )
    print(f"Base TP1 cargada: {coleccion_tp1.count()} documentos")

```

**Validar con 3 consultas de prueba antes de terminar la clase:**

```python
def validar_base_tp1(coleccion, consultas: list[dict]) -> None:
    for prueba in consultas:
        res = coleccion.query(query_texts=[prueba["consulta"]], n_results=2)
        print(f"\nConsulta:  {prueba['consulta']}")
        print(f"Esperado:  {prueba['esperado']}")
        for doc, dist in zip(res["documents"][0], res["distances"][0]):
            print(f"  [{dist:.4f}] {doc[:80]}...")

# Cada grupo define sus propias consultas de prueba

```

**Entregable del hito — responder en el notebook:**

* ¿Cuántos documentos tiene la base? ¿De dónde los obtuvieron?
* ¿Qué metadatos definieron y por qué esos?
* ¿Las 3 consultas de validación devolvieron el resultado correcto?
* ¿Qué tipo de consulta del usuario creen que va a ser más difícil de recuperar?

---

## Cierre — El Quiebre de la Experiencia

El docente ejecuta la Killer Query 1 y proyecta el resultado en la pantalla:

```python
resultados = coleccion.query(
    query_texts=["Busco algo fresco para un vestido hoy en Córdoba"],
    n_results=1,
    where={"$and": [{"sucursal_disponible": {"$eq": "filial_cordoba"}}, {"en_stock": {"$eq": True}}]}
)
print(resultados)

```

**Lo que aparece en la pantalla:**

```python
{
  'documents': [['Seda natural con acabado satinado, caída fluida y brillo sofisticado...']],
  'metadatas': [[{'en_stock': True, 'sucursal_disponible': 'filial_cordoba', 'linea_textil': 'alta_costura'}]],
  'distances': [[0.214]],
  'ids': [['TELA-002']]
}

```

> [!IMPORTANT] **El disparador para Clase 6**
> "El sistema de recuperación funciona perfectamente. Es rápido, persistente, respeta el stock y la sucursal. Pero si un cliente nos pregunta esto por WhatsApp y le respondemos con este diccionario de Python, perdemos la venta. ¿Qué nos falta? Nos falta un cerebro lingüístico que tome este dato preciso y lo convierta en una respuesta humana, cordial y persuasiva. Eso es LangChain. Eso es RAG. Es lo que arranca en Clase 6."

---

### Tarea asincrónica — La frustración controlada

> [!NOTE] **Objetivo pedagógico: que choquen contra la pared**
> El objetivo NO es que lo logren. Es que se den cuenta de que es imposible escalar respuestas dinámicas con `if/else`. Ese choque justifica LangChain en Clase 6.

Escribir un script Python **sin LLM** — solo funciones, f-strings e if/else — que tome el resultado de ChromaDB y genere una respuesta lista para enviar por WhatsApp. Procesar estos 6 mensajes:

```python
mensajes_whatsapp = [
    "Hola, tengo un casamiento en enero al mediodía y transpiro mucho, ¿qué llevo?",
    "Necesito retapizar un sillón pero tengo dos gatos que lo destruyen todo. Vivo en Salta.",
    "Busco algo con mucha caída, bien brillante para un vestido de noche, lo más barato posible.",
    "Quiero hacer delantales para un taller mecánico, se van a manchar con grasa.",
    "Hola, busco seda natural. ¿Me hacen descuento si llevo 50 metros?",
    "Soy alérgica a los materiales sintéticos, necesito algo 100% transpirable para ropa de cama.",
]

```

En Clase 6 arrancamos viendo cuántos if/else necesitaron y por qué el script colapsa con la variedad del lenguaje natural.

---

## Bibliografía de la Clase

* **Documentación oficial ChromaDB** — docs.trychroma.com
* **Alammar, J., & Grootendorst, M. (2024).** *Hands-On Large Language Models.* O'Reilly. Capítulo 6: Vector Databases.
* **Lewis, M., et al. (2020).** *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* (Los documentos que indexamos hoy son los que RAG recupera en Clase 6).