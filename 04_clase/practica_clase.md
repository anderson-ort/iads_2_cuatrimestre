# Faiss y embeddings [Recomendado Google Colab]

La principal innovación arquitectónica es el uso de **Matryoshka Representation Learning (MRL)**, que permite ajustar dinámicamente el tamaño de los vectores generados (por defecto 3072, recortable a 1536, 768 u otros tamaños) mediante el parámetro `output_dimensionality` sin perder precisión semántica.

```bash
uv add google-genai faiss-cpu numpy pydantic python-dotenv
```

---

**Tabla Comparativa de Modelos**

| Parámetro | `text-embedding-004` (Legacy) | `gemini-embedding-001` (Actual Estándar) | `gemini-embedding-2` (Multimodal) |
| --- | --- | --- | --- |
| **Modalidad de Entrada** | Texto puro | Texto puro | Texto, Imagen, Audio, Video, PDF |
| **Dimensiones por Defecto** | 768 | 3072 (configurable) | 3072 (configurable) |
| **Soporte MRL** | No | Sí (`output_dimensionality`) | Sí (`output_dimensionality`) |
| **Uso Recomendado** | Deprecado | Búsqueda semántica y RAG de texto | Catálogos multimodales e imágenes |

---

## Parte 1: Ejercitación Técnica Actualizada

### Ejercicio 1: Vectorización y Creación de FAISS con `gemini-embedding-001`

Archivo: `ejercicios/01_vectorizacion_faiss.py`

```python
import os
import faiss
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

textos_demo = [
    "Denim pesado de 12 oz, 100% algodón rígido con teñido índigo intenso. Ideal para ropa de trabajo.",
    "Seda natural satinada con caída fluida y brillo suave. Diseñada para vestidos de alta costura.",
    "Lona cobertora industrial con recubrimiento de PVC impermeable. Máxima resistencia a la intemperie."
]

print("Generando embeddings con gemini-embedding-001...")
# Mantenemos 768 dimensiones para optimizar memoria RAM usando Matryoshka Learning (MRL)
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=textos_demo,
    config=types.EmbedContentConfig(output_dimensionality=768)
)

vectores = np.array([e.values for e in response.embeddings], dtype=np.float32)
dimensiones = vectores.shape[1]

print(f"Matriz generada: {vectores.shape[0]} textos | Dimensiones: {dimensiones}")

index = faiss.IndexFlatL2(dimensiones)
index.add(vectores)

print(f"Total de vectores en el índice FAISS: {index.ntotal}")

```

---

### Ejercicio 2: Normalización y Similitud Coseno con `gemini-embedding-001`

Archivo: `ejercicios/02_similitud_coseno.py`

```python
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

def normalizar_vector(v: np.ndarray) -> np.ndarray:
    norma = np.linalg.norm(v)
    return v / norma if norma != 0 else v

textos = [
    "Gabardina elastizada ideal para pantalones de vestir.",
    "Tela elastizada de algodón para confección de pantalones formal.",
    "Lona gruesa para tapizado de muebles exteriores."
]

res = client.models.embed_content(
    model="gemini-embedding-001",
    contents=textos,
    config=types.EmbedContentConfig(output_dimensionality=768)
)
vecs = [normalizar_vector(np.array(e.values, dtype=np.float32)) for e in res.embeddings]

similitud_1_2 = np.dot(vecs[0], vecs[1])
similitud_1_3 = np.dot(vecs[0], vecs[2])

print(f"Similitud (Gabardina vs Tela elastizada): {similitud_1_2:.4f}")
print(f"Similitud (Gabardina vs Lona exterior):    {similitud_1_3:.4f}")

```

---

### Ejercicio 3: Evaluador de Búsqueda Semántica con Umbral L2

Archivo: `ejercicios/03_evaluador_queries.py`

```python
import faiss
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

catálogo_corto = [
    {"id": "TELA-01", "desc": "Denim 12oz 100% algodón rígido índigo."},
    {"id": "TELA-02", "desc": "Seda natural satinada ligera para fiesta."},
    {"id": "TELA-03", "desc": "Chenille de tapicería aterciopelado antimanchas."}
]

res_cat = client.models.embed_content(
    model="gemini-embedding-001", 
    contents=[t["desc"] for t in catálogo_corto],
    config=types.EmbedContentConfig(output_dimensionality=768)
)
matriz = np.array([e.values for e in res_cat.embeddings], dtype=np.float32)

index = faiss.IndexFlatL2(768)
index.add(matriz)

def evaluar_busqueda(query: str, umbral_max_l2: float = 0.65):
    res_q = client.models.embed_content(
        model="gemini-embedding-001", 
        contents=query,
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    vec_q = np.array([res_q.embeddings[0].values], dtype=np.float32)
    
    distancias, indices = index.search(vec_q, k=1)
    dist = distancias[0][0]
    idx = indices[0][0]
    
    print(f"\nQuery: '{query}'")
    if dist <= umbral_max_l2:
        match = catálogo_corto[idx]
        print(f"MATCH: [{match['id']}] Distancia L2: {dist:.4f} -> {match['desc']}")
    else:
        print(f"SIN COINCIDENCIA CONFIABLE. Distancia {dist:.4f} supera el umbral {umbral_max_l2}")

evaluar_busqueda("Jean clásico para trabajo pesado")
evaluar_busqueda("Repuesto de motor para camión de carga")

```

---

## Parte 2: Ortelana App Modular (Actualizada)

### 1. `src/config.py`

```python
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY no encontrada en el entorno.")

client = genai.Client()

MODELO_LLM = "gemini-2.5-flash"
# Actualizado al modelo estándar vigente
MODELO_EMBEDDINGS = "gemini-embedding-001"
# Dimensiones configuradas vía MRL
DIMENSION_EMBEDDINGS = 768
INDEX_FILE_PATH = "ortelana_catalogo.index"
CATALOGO_JSON_PATH = "catalogo_ortelana.json"

```

---

### 2. `src/indexer.py`

```python
import json
import os
import faiss
import numpy as np
from google.genai import types
from src.config import client, MODELO_EMBEDDINGS, DIMENSION_EMBEDDINGS, INDEX_FILE_PATH, CATALOGO_JSON_PATH

def cargar_catalogo_json() -> list[dict]:
    with open(CATALOGO_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def obtener_embeddings_lote(textos: list[str]) -> np.ndarray:
    response = client.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=textos,
        config=types.EmbedContentConfig(output_dimensionality=DIMENSION_EMBEDDINGS)
    )
    vectores = [item.values for item in response.embeddings]
    return np.array(vectores, dtype=np.float32)

def inicializar_o_cargar_indice() -> tuple[faiss.IndexFlatL2, list[dict]]:
    catalogo = cargar_catalogo_json()
    textos = [item["descripcion_semantica"] for item in catalogo]

    if not os.path.exists(INDEX_FILE_PATH):
        print(f"Construyendo índice FAISS con {MODELO_EMBEDDINGS} ({DIMENSION_EMBEDDINGS} dim)...")
        matriz = obtener_embeddings_lote(textos)
        index = faiss.IndexFlatL2(DIMENSION_EMBEDDINGS)
        index.add(matriz)
        faiss.write_index(index, INDEX_FILE_PATH)
        print(f"Índice binario guardado en '{INDEX_FILE_PATH}'.")
    else:
        index = faiss.read_index(INDEX_FILE_PATH)
        print(f"Índice binario cargado desde '{INDEX_FILE_PATH}'.")

    return index, catalogo

```

---

### 3. `src/retriever.py`

```python
import numpy as np
import faiss
from google.genai import types
from src.config import client, MODELO_EMBEDDINGS, DIMENSION_EMBEDDINGS
from src.models import FiltrosConsultaSchema, TelaResultado

def buscar_y_filtrar(
    query_filtros: FiltrosConsultaSchema, 
    index: faiss.IndexFlatL2, 
    catalogo: list[dict], 
    top_k: int = 5
) -> list[TelaResultado]:
    # Generar embedding de la búsqueda con el nuevo modelo y dimensión configurada
    res_vector = client.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=query_filtros.terminos_busqueda_semantica,
        config=types.EmbedContentConfig(output_dimensionality=DIMENSION_EMBEDDINGS)
    )
    vec_query = np.array([res_vector.embeddings[0].values], dtype=np.float32)
    
    distancias, indices = index.search(vec_query, top_k)
    resultados_filtrados: list[TelaResultado] = []

    for dist, idx in zip(distancias[0], indices[0]):
        item = catalogo[idx]
        meta = item["metadatos"]

        if query_filtros.linea_textil != "TODAS" and meta["linea_textil"] != query_filtros.linea_textil:
            continue
            
        if query_filtros.sucursal_preferida != "CUALQUIERA" and meta["sucursal_disponible"] != query_filtros.sucursal_preferida:
            continue

        if query_filtros.requiere_stock_inmediato and not meta["en_stock"]:
            continue

        resultados_filtrados.append(
            TelaResultado(
                id=item["id"],
                descripcion_semantica=item["descripcion_semantica"],
                linea_textil=meta["linea_textil"],
                sucursal=meta["sucursal_disponible"],
                en_stock=meta["en_stock"],
                distancia_l2=float(dist)
            )
        )

    return resultados_filtrados

```


Faltaban la configuración del entorno, la inicialización del paquete, la cadena RAG completa y el punto de entrada principal.

---

### `.env`

```env
GEMINI_API_KEY=tu_api_key_de_google_ai_studio

```

---

### `src/__init__.py`

```python
# Inicialización del paquete ejecutable src

```

---

### `src/rag_chain.py`

```python
from google.genai import types
from src.config import client, MODELO_LLM
from src.models import FiltrosConsultaSchema, RespuestaComercialSchema, TelaResultado

def extraer_intencion_y_filtros(mensaje_usuario: str) -> FiltrosConsultaSchema:
    prompt_parser = """
    Analiza la solicitud del cliente de Ortelana Textil y extrae los filtros operativos e intención semántica.
    """
    response = client.models.generate_content(
        model=MODELO_LLM,
        contents=mensaje_usuario,
        config=types.GenerateContentConfig(
            system_instruction=prompt_parser,
            response_mime_type="application/json",
            response_schema=FiltrosConsultaSchema,
            temperature=0.0
        )
    )
    return FiltrosConsultaSchema.model_validate_json(response.text)

def generar_respuesta_final(mensaje_usuario: str, articulos_recuperados: list[TelaResultado]) -> RespuestaComercialSchema:
    if articulos_recuperados:
        contexto_str = "\n".join([
            f"- [{t.id}] {t.descripcion_semantica} | Sucursal: {t.sucursal} | Stock: {t.en_stock}"
            for t in articulos_recuperados
        ])
    else:
        contexto_str = "No se encontraron artículos que cumplan los criterios estrictos."

    system_instruction = f"""
    Sos el asesor de ventas senior de Ortelana Textil.
    Responde al cliente de forma profesional y clara basándote ÚNICAMENTE en este contexto recuperado:

    {contexto_str}

    No prometas stock ni productos fuera de este contexto.
    """

    response = client.models.generate_content(
        model=MODELO_LLM,
        contents=mensaje_usuario,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=RespuestaComercialSchema,
            temperature=0.2
        )
    )
    return RespuestaComercialSchema.model_validate_json(response.text)

```

---

### `main.py`

```python
from src.indexer import inicializar_o_cargar_indice
from src.retriever import buscar_y_filtrar
from src.rag_chain import extraer_intencion_y_filtros, generar_respuesta_final

def procesar_consulta_cliente(mensaje_cliente: str):
    print(f"\n=======================================================")
    print(f"ENTRADA CLIENTE: '{mensaje_cliente}'")
    
    # 1. Carga o inicialización del índice vectorial binario
    indice, catalogo = inicializar_o_cargar_indice()

    # 2. Extracción estructurada de filtros e intención (Paso LLM 1)
    filtros = extraer_intencion_y_filtros(mensaje_cliente)
    print(f"\n[PASO 1] Filtros estructurados extraídos:")
    print(f" - Línea: {filtros.linea_textil}")
    print(f" - Sucursal: {filtros.sucursal_preferida}")
    print(f" - Stock requerido: {filtros.requiere_stock_inmediato}")
    print(f" - Query Semántica: '{filtros.terminos_busqueda_semantica}'")

    # 3. Búsqueda vectorial con gemini-embedding-001 + filtrado por metadatos
    articulos = buscar_y_filtrar(filtros, indice, catalogo, top_k=5)
    print(f"\n[PASO 2] Artículos que pasaron los filtros ({len(articulos)}):")
    for a in articulos:
        print(f" - [{a.id}] (Dist L2: {a.distancia_l2:.4f}) {a.descripcion_semantica[:60]}...")

    # 4. Generación de respuesta comercial con RAG (Paso LLM 2)
    respuesta_final = generar_respuesta_final(mensaje_cliente, articulos)
    print(f"\n[PASO 3] Respuesta Comercial Final:")
    print(f" Mensaje: {respuesta_final.mensaje_comercial}")
    print(f" Artículos recomendados: {respuesta_final.articulos_recomendados}")
    if respuesta_final.advertencia_stock:
        print(f" Advertencia: {respuesta_final.advertencia_stock}")

if __name__ == "__main__":
    # Prueba 1: Coincidencia semántica + Filtro de stock/sucursal
    procesar_consulta_cliente(
        "Hola! Necesito denim urgente para fabricar pantalones de trabajo. Estoy en Buenos Aires."
    )

    # Prueba 2: Búsqueda de alta costura en Córdoba
    procesar_consulta_cliente(
        "Busco algo elegante y liviano para vestidos de gala en la filial de Córdoba."
    )

```