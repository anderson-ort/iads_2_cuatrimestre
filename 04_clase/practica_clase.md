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


```bash
# Schema de nuestro proyecto y su avance
ortelana-app/
├── .env
├── main.py
├── database/
│   └── catalogo.json
└── src/
    ├── __init__.py
    ├── config.py
    ├── models.py
    ├── indexer.py
    ├── retriever.py
    └── rag_chain.py

```

| Archivo / Carpeta | Responsabilidad y Función Arquitectónica |
| --- | --- |
| **`.env`** | Almacena las variables de entorno de forma segura (clave privada `GEMINI_API_KEY`). Evita hardcodear credenciales en el código base. |
| **`database/catalogo.json`** | Base de conocimiento estática del catálogo. Contiene descripciones semánticas enriquecidas y metadatos de negocio (`en_stock`, `sucursal_disponible`, `linea_textil`). |
| **`src/__init__.py`** | Declara el directorio `src/` como un paquete ejecutable de Python para permitir importaciones limpias entre módulos. |
| **`src/config.py`** | Punto central de configuración. Inicializa el cliente global `genai.Client()`, lee variables de entorno y fija constantes de modelos (`gemini-2.5-flash`, `gemini-embedding-001`), dimensiones (768) y rutas. |
| **`src/models.py`** | Define los contratos de datos mediante Pydantic V2 (`FiltrosConsultaSchema`, `TelaResultado`, `RespuestaComercialSchema`). Garantiza Structured Outputs estrictos en las llamadas al LLM. |
| **`src/indexer.py`** | Módulo de ingesta y vectorización. Lee `database/catalogo.json`, genera embeddings en lote con `gemini-embedding-001` y construye o recupera el índice binario FAISS L2 en disco (`ortelana_catalogo.index`). |
| **`src/retriever.py`** | Ejecuta la búsqueda híbrida en 2 etapas: primero realiza una búsqueda por distancia euclidiana L2 en FAISS y luego aplica filtrado por metadatos duros (`linea_textil`, `sucursal`, `en_stock`) en Python. |
| **`src/rag_chain.py`** | Orquestador de razonamiento con el LLM (`gemini-2.5-flash`). Contiene dos pasos: `extraer_intencion_y_filtros` (parsea la consulta del cliente a JSON) y `generar_respuesta_final` (sintetiza la respuesta comercial basándose únicamente en el contexto recuperado). |
| **`main.py`** | Script de entrada principal. Coordina la ejecución punta a punta (E2E) integrando indexación, extracción de intenciones, recuperación semántica y generación de respuesta final. |

---

La pipeline se estructuró en **3 etapas independientes y secuenciales** controladas mediante CLI con `argparse`:

* **`ingest`**: Carga `database/catalogo.json`, vectoriza con `gemini-embedding-001` y guarda el archivo binario `.index` de FAISS en disco.
* **`search`**: Extrae la intención/filtros del usuario, vectoriza la consulta, ejecuta la búsqueda semántica + filtrado por metadatos y muestra los vectores/coincidencias encontradas.
* **`rag`**: Ejecuta la búsqueda semántica completa y la envía a `gemini-2.5-flash-lite` para síntesis comercial estructurada.


### Ejemplos de Uso en Terminal

**1. Ingesta e Indexación del Catálogo**

```bash
python main.py ingest

```

**2. Solo Búsqueda Semántica y Mapeo de Embeddings**

```bash
python main.py search "Necesito gabardina con spandex en Cordoba"

```

**3. Pipeline RAG Completa (Búsqueda + Generación Comercial)**

```bash
python main.py rag "Hola! Necesito denim urgente para fabricar pantalones de trabajo. Estoy en Buenos Aires."

```

--- 
### Ejemplos para la clase

**Ejemplos para `search**` *(Verificación de extracción de intenciones y distancia vectorial)*

* **Consulta 1 (Tapicería en filial Córdoba):**
```bash
python main.py search "Busco tela gruesa y antimanchas para retapizar un sillón en Córdoba"

```


* **Consulta 2 (Línea industrial e impermeabilidad):**
```bash
python main.py search "Necesito lona impermeable de PVC para cubrir la carga de un camión"

```


* **Consulta 3 (Confección formal / Indumentaria):**
```bash
python main.py search "Tienen alguna tela elastizada de algodón para confeccionar pantalones de vestir cómodos?"

```



---

**Ejemplos para `rag**` *(Flujo completo: Búsqueda semántica + Síntesis de respuesta comercial con el LLM)*

* **Consulta 1 (Alta costura y disponibilidad geográfica):**
```bash
python main.py rag "Hola, tengo un evento de gala la semana que viene y busco una tela liviana y brillante para un vestido. ¿Tienen algo disponible en la sucursal de Córdoba?"

```


* **Consulta 2 (Manejo de alertas de stock en Buenos Aires):**
```bash
python main.py rag "Buenas tardes, necesito comprar lona industrial con recubrimiento de PVC para un cobertor. ¿Tienen stock inmediato en la sucursal Central de Buenos Aires?"

```


* **Consulta 3 (Ropa de trabajo pesado):**
```bash
python main.py rag "Estimados, estamos confeccionando indumentaria pesada y camperas de trabajo para taller. ¿Qué opciones resistentes tienen en stock en Buenos Aires?"

```


