# Etapa `eval` — medir la calidad del RAG

Job por lotes que **no se despliega**. Corre RAGAS sobre el camino RAG
(`retrieval híbrido → sintetizador`) y devuelve las métricas. Es el gate de calidad previo a
promover una versión a producción.

```
 Atlas Vector Search (de ingest) ─┐
 data/eval/<dataset>.json ───┴─> retrieve + synthesize ─> juez RAGAS (Gemini) ─> scores
```

## Qué hace

1. Carga `data/eval/<dataset>.json` (`question` + `ground_truth`).
2. Para cada caso: recupera contexto (BM25 + vector + RRF + rerank de Cohere) y genera la respuesta
   con el mismo `synthesize()` que usa el runtime.
3. Puntúa con RAGAS. **Máximo 2 métricas por corrida** (por defecto `answer_relevance` y
   `context_recall`) para cuidar la cuota gratuita del juez. Reintenta ante 429/503.
4. Imprime `EvalReport(samples_evaluated, scores)`.

Código: `eval/main.py` (entrypoint) + `src/evaluation.py` (lógica).

## Por qué está separado del runtime

- `ragas` arrastra `datasets`, `scikit-network`, `networkx`, `instructor`, `tiktoken`: es la parte
  más pesada y el runtime no la usa.
- Antes `/api/v1/eval` estaba en la API pública y consumía cuota del juez sin autenticación.
  **Ese endpoint ya no existe en el runtime.**

## Dependencias (grupo `eval`)

`core` + `agent` (LangChain/LangGraph, necesarios para `synthesize`) + `ragas` + `openai`
(cliente del endpoint compatible de Gemini) + `langchain-community<0.4.2` (lo exige RAGAS).
Sin FastAPI ni NeMo.

## Variables de entorno

`.env` de `12_clase/`: `GOOGLE_API_KEY` (**siempre**, el juez es Gemini aunque el provider sea
cohere), `COHERE_API_KEY` (rerank), `MONGODB_URI`. `SUPABASE_KEY` es exigida pero no se usa.

## Ejecutar

Desde `12_clase/`, con el índice ya construido por `ingest`.

```bash
# Local
uv sync --only-group eval
uv run --only-group eval python -m eval.main                  # eval_ortelana_v1
uv run --only-group eval python -m eval.main eval_ortelana_v1

# Docker
docker build -f eval/Dockerfile -t ortelana-eval .
docker run --rm --env-file .env -v "$PWD/data:/app/data" ortelana-eval eval_ortelana_v1
```

## Alcance y límites

- Cubre solo `rag_direct`: no evalúa CUIT, agente ReAct, búsqueda web ni guardrails.
- El golden set (`data/eval/`) tiene 5 casos; la clase 12 propone ampliarlo (sección 4 del README).
- Aún no registra corridas en MLflow ni bloquea un deploy: hoy imprime el resultado.
