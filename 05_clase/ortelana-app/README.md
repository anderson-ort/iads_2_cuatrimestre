# Ortelana Process Mini RAG

Implementación completa del sistema RAG modular para Ortelana Textil, configurado explícitamente con el modelo embedding-001 de Gemini (vector de 768 dimensiones), MongoDB Atlas, ChromaDB en Docker Compose y soporte de cambio dinámico a Cohere.

Herramientas adicionales:
- Typer
- Rich
- MongoDB Atlas(Fuente de la verdad)
- ChromaDB -> Instalacion de una version StandAlone


```bash
ortelana-app
├── .env
├── .env.sample
├── .python-version
├── database
│   ├── catalogo.json
│   └── chroma_data
├── docker-compose.yaml
├── pyproject.toml
├── README.md
├── src
│   └── ortelana
│       ├── cli.py
│       ├── config.py
│       ├── db
│       │   ├── chroma.py
│       │   ├── __init__.py
│       │   └── mongo.py
│       ├── __init__.py
│       ├── models
│       │   ├── __init__.py
│       │   ├── product.py
│       │   └── rag.py
│       ├── providers
│       │   ├── base.py
│       │   ├── cohere_provider.py
│       │   ├── factory.py
│       │   ├── gemini_provider.py
│       │   └── __init__.py
│       ├── rag
│       │   ├── engine.py
│       │   ├── __init__.py
│       │   └── router.py
│       └── sync
│           ├── initial.py
│           ├── __init__.py
│           └── worker.py
└── uv.lock
```


Esta documentación detalla la función técnica de cada archivo dentro del proyecto **Ortelana RAG**.

**Configuración e Infraestructura**

* `pyproject.toml`: Configura el empaquetado del proyecto, gestiona las dependencias (`pydantic`, `pydantic-settings`, `google-genai`, `cohere`, `pymongo`, `chromadb`, `typer`, `rich`, `python-dotenv`) y registra el ejecutable de consola `ortelana`.
* `.env.sample`: Plantilla con las variables de entorno necesarias para la ejecución (claves de API, modelos activos y endpoints de base de datos).
* `docker-compose.yaml`: Levanta los contenedores locales de ChromaDB (puerto 8000) y ChromaDB Admin (puerto 3001) con volúmenes persistentes en `./database/chroma_data`.

**Configuración e Interfaz (`src/ortelana/`)**

* `src/ortelana/config.py`: Carga, valida y expone fuertemente tipadas las variables de entorno mediante `pydantic-settings`.
* `src/ortelana/cli.py`: Punto de entrada de la CLI interactiva. Utiliza Typer y Rich para la interfaz visual, implementando un patrón *Never Nested* (`match/case`) y funciones manejadoras para procesar los comandos (`/provider`, `/reload`, `/sync`, `/help`, `/exit`) y enviar consultas RAG.

**Modelos de Datos (`src/ortelana/models/`)**

* `src/ortelana/models/product.py`: Define el modelo de dominio con Pydantic (`Product`, `ProductMetadata`, `LineaTextil`). Incluye validaciones (expresiones regulares de ID `TELA-XXX`, rangos de precio) y expone la propiedad `vector_document` utilizada para la vectorización.
* `src/ortelana/models/rag.py`: Define los modelos Pydantic para el enrutamiento de consultas (`QueryRoute`), los resultados de búsqueda semántica (`SearchResult`) y la respuesta final consolidada (`RAGResponse`).

**Capas de Persistencia (`src/ortelana/db/`)**

* `src/ortelana/db/mongo.py`: Administra la conexión tipo Singleton cliente hacia MongoDB (Atlas o local) y recupera la colección `catalogo`.
* `src/ortelana/db/chroma.py`: Administra la conexión vía cliente HTTP con el servidor de ChromaDB y obtiene/crea dinámicamente la colección vectorial aislada según el proveedor activo (`ortelana_products_gemini` u `ortelana_products_cohere`).

**Proveedores de IA (`src/ortelana/providers/`)**

* `src/ortelana/providers/base.py`: Clases base abstractas (`BaseLLMProvider` y `BaseEmbeddingProvider`) que definen el contrato estándar para integración de modelos de lenguaje y embeddings.
* `src/ortelana/providers/gemini_provider.py`: Implementación concreta utilizando el SDK oficial `google-genai` para generación de texto, extracción estructurada con esquemas y cálculo de embeddings.
* `src/ortelana/providers/cohere_provider.py`: Implementación concreta utilizando `cohere.ClientV2` para generación de chat, cálculo de embeddings en lote y extracción JSON estructurada.
* `src/ortelana/providers/factory.py`: Aplicación del patrón *Factory* para alternar dinámicamente el proveedor activo (Gemini o Cohere) en tiempo de ejecución.

**Sincronización de Datos (`src/ortelana/sync/`)**

* `src/ortelana/sync/initial.py`: Carga los productos directamente desde MongoDB, valida cada documento contra el esquema de Pydantic, genera sus vectores con el proveedor activo y los indexa en ChromaDB.
* `src/ortelana/sync/worker.py`: Escucha eventos en tiempo real (*Change Streams*) en MongoDB para actualizar o insertar automáticamente vectores en ChromaDB ante cualquier cambio en el catálogo.

**Motor RAG (`src/ortelana/rag/`)**

* `src/ortelana/rag/router.py`: Analiza la consulta del usuario mediante el LLM configurado y devuelve una salida JSON estructurada con la clasificación de intención (`PRODUCT`, `DOCUMENT` o `HYBRID`).
* `src/ortelana/rag/engine.py`: Orquestador del flujo RAG; convierte la consulta a vector, busca las coincidencias más cercanas en ChromaDB, recupera la información enriquecida desde MongoDB y genera una respuesta fundamentada en el contexto.

---

## Guía de Ejecución y Uso

### 1. Requisitos Previos
* Python >= 3.13
* [uv](https://github.com/astral-sh/uv)
* Docker y Docker Compose

### 2. Configuración de Variables de Entorno
Copia el archivo de ejemplo `.env.sample` a `.env` y configura tus API Keys:
```bash
cp .env.sample .env
```
Asegúrate de definir `GEMINI_API_KEY`, `COHERE_API_KEY` y la URI de MongoDB (`MONGODB_URI`).

### 3. Levantar Infraestructura Local (ChromaDB)
```bash
docker compose up -d
```
* **ChromaDB**: `http://localhost:8000`
* **ChromaDB Admin UI**: `http://localhost:3001`

### 4. Sincronización Inicial de Datos
Para vectorizar el catálogo existente en MongoDB e indexarlo en ChromaDB:
```bash
uv run python -m ortelana.sync.initial
```

### 5. Iniciar Worker en Tiempo Real (Change Streams)
Para mantener sincronizados los cambios de MongoDB con ChromaDB en tiempo real:
```bash
uv run python -m ortelana.sync.worker
```

### 6. Ejecutar la CLI Interactiva
```bash
uv run ortelana
# o alternativamente:
uv run python -m ortelana.cli
```

**Comandos dentro de la CLI interactiva:**
* `/provider [gemini|cohere]`: Muestra o cambia el proveedor de IA en tiempo de ejecución.
* `/reload`: Recarga el archivo `.env` en caliente sin reiniciar la consola.
* `/sync`: Re-sincroniza manualmente el catálogo contra ChromaDB.
* `/help`: Muestra la lista de comandos disponibles.
* `/exit`: Sale de la aplicación.