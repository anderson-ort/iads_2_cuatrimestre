# LangSmith + RAGAS: trazar y evaluar el RAG de la clase 07

Mismo pipeline que `../ragas-ejemplo/ragas_eval.py` (Chroma -> CrossEncoder -> Gemini),
con dos agregados:

- **Tracing**: cada pregunta genera un *trace* en LangSmith con el árbol completo
  (retrieval, rerank, prompt, LLM, tokens, latencia).
- **Experimentos**: el golden set se sube como *Dataset* y cada corrida de RAGAS
  queda como un *Experiment* comparable en la UI.

Teoría: [`langsmith.md`](langsmith.md). Métricas: [`../ragas-ejemplo/ragas.md`](../ragas-ejemplo/ragas.md).

```text
langsmith-ejemplo/
├── langsmith_eval.py   # pipeline instrumentado + evaluación
├── config.toml         # perillas del RAG, juez y nombre del dataset
├── .env.sample         # keys de Gemini y LangSmith
└── pyproject.toml
```

El golden set no se duplica: se lee de `../ragas-ejemplo/golden_set.json`.

---

## Paso 1. Crear la cuenta y la API key

1. Entrar a <https://smith.langchain.com> y registrarse (plan **Developer**, gratis:
   5.000 traces/mes, retención de 14 días).
2. Elegir región: US o EU. Si elegís EU, después hay que descomentar
   `LANGSMITH_ENDPOINT` en `.env`.
3. Ir a **Settings -> API Keys -> Create API Key** y elegir el tipo **Personal Access Token**.
   Copiar la key (empieza con `lsv2_pt_`): se muestra una sola vez.

## Paso 2. Configurar el entorno

```bash
cd 08_clase/langsmith-ejemplo
uv sync
cp .env.sample .env
```

Completar en `.env`:

| Variable | Para qué sirve |
|---|---|
| `GOOGLE_API_KEY` | LLM del RAG + juez de RAGAS (igual que en ragas-ejemplo) |
| `LANGSMITH_API_KEY` | Autentica el envío de traces |
| `LANGSMITH_TRACING=true` | Interruptor general: sin esta variable no se envía nada |
| `LANGSMITH_PROJECT` | Nombre del proyecto donde caen los traces (se crea solo) |

No hace falta código extra para activar el tracing: LangChain lee estas variables
al arrancar. Por eso el script ejecuta `load_dotenv` antes de importar LangChain.

## Paso 3. Primer trace (observabilidad)

```bash
uv run python langsmith_eval.py --pregunta "¿Qué descuento tiene la gabardina elastizada de 8 oz?"
```

La primera vez indexa los documentos en `chroma_db/` (local, no genera traces).

Ver el resultado en la UI:

1. **Tracing Projects -> rag-ortelana-dev**. Aparece una fila por ejecución, con latencia,
   tokens y estado.
2. Click en la fila. Se abre el árbol del trace:

```text
rag_tecnico                     (chain, @traceable)   metadata: top_n, chunk_size, modelo...
├── recuperar_chunks            (retriever, @traceable) chunks + distancia_vectorial + score_reranker
└── RunnableSequence            (automático de LangChain)
    ├── ChatPromptTemplate      prompt final: system + contexto + pregunta
    └── ChatGoogleGenerativeAI  modelo, temperatura, tokens, latencia, respuesta
```

Qué mirar en cada span:

- **recuperar_chunks**: los chunks que vio el LLM y por qué quedaron en ese orden.
  Si la respuesta es mala, mirá primero acá: ¿estaba el dato en algún chunk?
- **ChatPromptTemplate**: el prompt exacto que se envió.
- **ChatGoogleGenerativeAI**: tokens de entrada/salida y cuánto tardó el LLM.
- **Metadata** (panel derecho de `rag_tecnico`): la configuración que produjo este trace.

Cómo se generó cada span (ver sección 2 del script):

- Los spans de LangChain (prompt, LLM) son **automáticos**.
- Chroma y CrossEncoder no son Runnables de LangChain. Para que aparezcan, el script
  los envuelve con `@traceable(run_type="retriever")`. `run_type="retriever"` hace que la
  UI muestre la salida como documentos y no como JSON crudo.
- `@traceable(run_type="chain")` en `responder` crea el span padre. La llamada a
  `rag_chain.invoke` se anida dentro de ese span sin código adicional.

## Paso 4. Evaluar el golden set como experimento

```bash
uv run python langsmith_eval.py
```

Qué hace el script, en orden:

1. **Dataset** (`client.create_dataset` + `create_examples`): sube `golden_set.json` a
   LangSmith como `ortelana-golden-set-v1`. Esto ocurre solo la primera vez.
   Cada Example tiene `inputs` (pregunta), `outputs` (ground_truth, debe_abstenerse) y
   `metadata` (id, categoría).
2. **Target** (`rag_target`): LangSmith lo llama una vez por Example. Cada llamada es un
   trace completo, con el mismo árbol del paso 3.
3. **Evaluadores**: funciones que reciben `inputs`, `outputs` y `reference_outputs` y
   devuelven `{"key", "score", "comment"}`. Hay uno por métrica de RAGAS
   (`faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`) y uno
   determinista (`abstencion_ok`). LangSmith guarda cada score como *feedback* del caso.
4. **Juez trazado**: el cliente OpenAI del juez está envuelto con `wrap_openai`. Las
   llamadas del juez aparecen dentro de cada evaluador y muestran qué afirmaciones
   extrajo RAGAS y cómo las verificó.
5. **Quality gate**: al final el script recalcula los promedios y termina con
   exit code 1 si alguno queda bajo `umbral_minimo` (igual que en un CI).

Ver el resultado en la UI:

1. **Datasets & Experiments -> ortelana-golden-set-v1**. Hay una fila por experimento,
   con el promedio de cada métrica.
2. Click en el experimento. Hay una fila por caso con columnas `faithfulness`,
   `context_recall`, etc. Ordená por la peor métrica y abrí ese caso: se ve el trace
   del RAG (qué chunks recibió) junto al trace del evaluador (por qué puntuó bajo).
3. La columna **metadata** del experimento muestra las perillas (`top_n`, `chunk_size`...).

Nota sobre la cuota: el free tier de Gemini limita llamadas por día. Si se corta, el
experimento parcial queda en LangSmith; volvé a correr cuando haya cuota (se crea un
experimento nuevo).

## Paso 5. Cambiar una perilla y comparar

1. Editar `config.toml`, por ejemplo `top_n = 1`.
2. Volver a correr `uv run python langsmith_eval.py`. Se crea otro experimento,
   con prefijo `top1-k10-chunk800-rerank`.
3. En **Datasets & Experiments -> ortelana-golden-set-v1**, seleccionar los dos
   experimentos y presionar **Compare**.
4. La vista compara caso por caso y resalta en rojo/verde qué empeoró o mejoró.
   Abrir un caso que bajó en `context_recall` y comparar los chunks de cada versión.

Este es el flujo de `langsmith.md`: **RAGAS detecta la regresión, LangSmith muestra la causa.**

## Diferencias con ragas-ejemplo

| | ragas-ejemplo | langsmith-ejemplo |
|---|---|---|
| Golden set | `golden_set.json` local | mismo archivo, subido como Dataset |
| Resultados | `resultados/corrida_*.json` | Experiment en la UI (+ resumen en consola) |
| Baseline | `baseline.json` + `caida_maxima` | comparar experimentos en la UI; acá solo `umbral_minimo` |
| Por qué falló un caso | leer `answer`/`contexts` del JSON | navegar el trace del RAG y del juez |
| `--resume` | sí | no; el experimento parcial queda en LangSmith |

## Precauciones

- Todo lo que pasa por el pipeline se envía a LangSmith: preguntas, chunks, prompts y
  respuestas. Los documentos de OrTelana son ficticios. Con datos reales, revisá que no
  haya PII ni secretos antes de activar el tracing.
- La retención del plan gratuito es de 14 días. Para un historial permanente usá los
  JSON de `ragas-ejemplo`.
- Si cambiás `golden_set.json`, cambiá también `[langsmith].dataset` en `config.toml`
  (por ejemplo `-v2`). El script no modifica un dataset que ya existe.
- Para apagar el tracing sin tocar código: `LANGSMITH_TRACING=false`. El modo evaluación
  necesita el tracing activo, por eso el script corta si falta.
