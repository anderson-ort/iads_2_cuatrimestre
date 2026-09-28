# Muestra de clase: RAG en dos scripts

Versión simplificada de `rag-anydoc-app/` y `rag-inference-app/`. Cada proyecto
queda reducido a un único script lineal, sin clases, CLI ni UI, para poder leer
el flujo de arriba hacia abajo. Todos los parámetros se leen de `config.toml`.

```
.muestra_clase/
├── config.toml        # parámetros de los dos scripts
├── .env.sample        # plantilla de API keys (copiar a .env)
├── rag_simple.py      # ingesta: documentos -> base vectorial
├── rag_inferencia.py  # inferencia: pregunta -> router -> respuesta
└── chroma_db/         # base vectorial (la crea rag_simple.py)
```

## Preparación

Los scripts usan el entorno de `rag-anydoc-app`, que ya tiene todas las
dependencias instaladas.

```bash
cp .muestra_clase/.env.sample .muestra_clase/.env   # completar las keys
cd rag-anydoc-app
uv run python ../.muestra_clase/rag_simple.py       # 1. ingesta
uv run python ../.muestra_clase/rag_inferencia.py   # 2. inferencia
```

| Key              | Cuándo se necesita                                          |
|------------------|-------------------------------------------------------------|
| `GOOGLE_API_KEY` | Siempre en `rag_inferencia.py` (router y LLM de Gemini)     |
| `GEMINI_API_KEY` | Solo si `[embeddings] provider = "gemini"`                  |
| `COHERE_API_KEY` | Solo si `provider = "cohere"` o `[reranker] tipo = "cohere"` |

Con `provider = "huggingface"` (valor por defecto), `rag_simple.py` no necesita
ninguna key: el modelo se descarga y corre localmente.

## 1. `rag_simple.py`: ingesta

Convierte documentos en chunks con embeddings y los guarda en Chroma.

```
archivo (PDF, DOCX...) --parse--> Markdown --chunk--> fragmentos --embed--> vectores --store--> chroma_db/
```

| Paso | Qué hace                                                                                  |
|------|-------------------------------------------------------------------------------------------|
| 0    | Lee `config.toml` y `.env`.                                                               |
| 1    | Crea el modelo de embeddings del proveedor elegido.                                       |
| 2    | Abre (o crea) la colección de Chroma en `chroma_db/`.                                     |
| 3    | **Ingesta.** Por cada archivo: `anydoc` lo convierte a Markdown; se corta primero por títulos (`#`, `##`...) y después por tamaño (`size`, `overlap`); se guarda con ids `archivo-0`, `archivo-1`... |
| 4    | **Consulta.** Devuelve los `k` chunks más cercanos a `[consulta] texto`, con su distancia. |
| 5    | **Stats.** Muestra el total de chunks y los archivos presentes en la colección.           |

`[run] modo` elige qué pasos se ejecutan: `ingest`, `query`, `stats` o `all`.

Como los ids son determinísticos, volver a ingestar un archivo reemplaza sus
chunks en lugar de duplicarlos. Si cambiás `chunk_size` y el archivo genera
menos chunks, los sobrantes quedan en la base. Para empezar de cero, borrá
`chroma_db/`.

## 2. `rag_inferencia.py`: router + RAG

Recibe preguntas, decide qué tipo de consulta es y responde por la rama que
corresponde. Lee la misma base que creó `rag_simple.py`.

```
pregunta --> router (LLM) --+-- stock        --> datos mock
                            +-- promociones  --> datos mock
                            +-- tecnico      --> retrieval --> rerank --> LLM + contexto
                            +-- otro         --> "no pude clasificar"
```

| Paso | Qué hace                                                                                  |
|------|-------------------------------------------------------------------------------------------|
| 1    | Esquemas Pydantic (`RouterDecision`, `RagAnswer`): obligan al LLM a responder con una estructura fija. |
| 2    | Prompts del router y del RAG.                                                             |
| 3    | Datos mock de stock y promociones. Reemplazan a una base de datos real.                   |
| 4    | Embeddings y Chroma. Tienen que ser los mismos que usó la ingesta.                        |
| 5    | Reranker: `crossencoder` (local) o `cohere` (API).                                        |
| 6    | LLMs de Gemini con `with_structured_output`.                                              |
| 7    | **Pipeline.** Recorre `[inferencia] preguntas`, clasifica cada una y la resuelve.         |

La rama `tecnico` tiene tres etapas:

1. **Retrieval (bi-encoder).** Trae `k_candidatos` chunks por cercanía de
   vectores. Es rápido y tiene buen recall, pero precisión moderada.
2. **Rerank (cross-encoder).** Evalúa cada par pregunta–chunk y se queda con los
   `top_n` más relevantes. Es más lento, pero más preciso.
3. **Generación.** El LLM responde **solo** con ese contexto y cita las fuentes.
   Si el contexto no alcanza, marca `informacion_insuficiente` en lugar de
   inventar.

## Cómo se aplica como ejemplo en clase

1. **Ingesta paso a paso.** Correr `rag_simple.py` con `modo = "ingest"` y
   mirar cuántos caracteres y chunks genera cada documento.
2. **Efecto del chunking.** Cambiar `size` y `overlap`, borrar `chroma_db/`,
   reingestar y comparar los resultados de `modo = "query"`.
3. **Efecto del modelo de embeddings.** Hoy la consulta "como se aplica el
   descuento" devuelve chunks de `reglas_alta_distribuidores`, porque
   `all-MiniLM-L6-v2` es un modelo en inglés. Probar con
   `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` o con
   `provider = "gemini"` y comparar.
4. **Router.** Correr `rag_inferencia.py` con las 4 preguntas de ejemplo: cada
   una debería ir por una rama distinta (stock, promociones, técnico, otro).
5. **Retrieval vs. rerank.** En la rama técnica, comparar el orden de los
   candidatos del bi-encoder con el orden después del reranker.
6. **Alucinaciones.** Agregar una pregunta técnica que no esté en los
   documentos y verificar que el modelo declare información insuficiente.
7. **Ejercicio.** Reemplazar los diccionarios `MOCK_STOCK` y `MOCK_PROMOS` por
   una consulta real (CSV, SQLite o una API).

> Importante: `rag_inferencia.py` tiene que usar el mismo `provider` que se usó
> en la ingesta. Si se cambia, Chroma abre otra colección (vacía) y el retrieval
> no devuelve nada.

