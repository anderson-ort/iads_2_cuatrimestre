# RAGAS: ejemplo de evaluación

Evalúa con RAGAS el RAG de la clase 07 (`07_clase/.muestra_clase/rag_inferencia.py`).
Aplica los conceptos de `../ragas.md`: las 4 métricas core, el golden set como
contrato de evaluación y la evaluación como regresión contra un baseline.

```
golden_set.json + pipeline (config.toml)
        -> el RAG responde cada pregunta  (retrieval -> rerank -> Gemini)
        -> question + answer + contexts + ground_truth
        -> RAGAS calcula métricas          (Gemini hace de juez)
        -> comparación contra baseline.json
        -> OK o FALLO (exit code 1, como en un CI)
```

## Archivos

| Archivo | Para qué |
|---|---|
| `ragas_eval.py` | Script único: indexa, corre el RAG, mide con RAGAS y compara contra el baseline. |
| `config.toml` | Perillas del pipeline (embeddings, chunking, top_n, reranker) y de la evaluación (juez, umbrales). |
| `golden_set.json` | 8 casos con `ground_truth`: directa, multipaso, parafraseada, con restricción, adversarial y fuera de dominio. |
| `baseline.json` | Se crea en la primera corrida. Es el estándar contra el que se comparan los cambios. |
| `resultados/` | Una corrida completa por archivo (respuesta, contextos y métricas de cada caso). |

## Cómo correrlo

```bash
cd 08_clase/ragas-ejemplo
uv sync
cp .env.sample .env                     # completar GOOGLE_API_KEY

uv run python ragas_eval.py             # 1ra corrida: crea baseline.json
```

Después cambiá **una sola** perilla en `config.toml` y volvé a correr:

```bash
uv run python ragas_eval.py             # compara contra el baseline
uv run python ragas_eval.py --baseline  # acepta esta versión como nuevo baseline
```

No hace falta correr antes `rag_simple.py`: si la colección no existe, el
script indexa los documentos de `07_clase/documents/`. El nombre de la
colección incluye el modelo de embeddings y el chunking, así que cada
variante tiene su propio índice.

## Qué mide cada métrica y qué datos usa

| Métrica | Componente | question | answer | contexts | ground_truth |
|---|---|:---:|:---:|:---:|:---:|
| Faithfulness | Generación | sí | sí | sí | no |
| Answer Relevancy | Generación | sí | sí | no | no |
| Context Precision | Retriever | sí | no | sí | sí |
| Context Recall | Retriever | sí | no | sí | sí |

El caso fuera de dominio (`debe_abstenerse: true`) no se mide con RAGAS:
ahí lo que importa es que el RAG se abstenga. Se verifica con un check
determinista (`abstencion_ok`), que es **bloqueante** aunque el promedio mejore.

## Experimentos sugeridos

| Cambio en `config.toml` | Qué se espera ver |
|---|---|
| Embeddings `paraphrase-multilingual-MiniLM-L12-v2` | Sube Context Recall: los documentos están en español y MiniLM-L6 es un modelo en inglés. |
| `top_n = 1` | Baja Context Recall en las preguntas multipaso. |
| `usar_reranker = false` | Puede bajar Context Precision (chunks útiles más abajo en el ranking). |
| `chunk_size = 200` | Ideas cortadas a la mitad: baja Context Recall. |
| Quitar del prompt "Si la pregunta parte de una premisa falsa, corrígela" | Puede bajar Faithfulness en el caso adversarial. |

## Resultado de referencia

Corrida con la configuración por defecto (MiniLM-L6 en inglés). Los valores
varían un poco entre corridas, porque el juez es un LLM:

```
faithfulness       0.871   peor: restriccion-01 (0.50)
answer_relevancy   0.807   peor: directa-01 (0.00)
context_precision  0.571   peor: directa-01 (0.00)
context_recall     0.571   peor: directa-01 (0.00)
```

Lectura: Faithfulness está alto, así que el LLM no inventa. El problema está en
el **retriever**: en `directa-01`, `parafraseada-01` y `multipaso-02` no llega
el chunk correcto (recall 0). El RAG se abstiene en `directa-01` y en
`parafraseada-01` aunque la respuesta sí está en los documentos.
Con el modelo multilingüe, `directa-01` sube a recall 0.5 y `multipaso-02` a 1.0.

## Notas sobre Gemini

- **RAG:** `langchain-google-genai`, igual que en la clase 07.
- **Juez de RAGAS:** Gemini por su endpoint compatible con OpenAI. Con RAGAS 0.4,
  el cliente async de `google-genai` falla por un problema de la librería
  `instructor`, y la documentación de RAGAS recomienda este endpoint. Usa la
  misma `GOOGLE_API_KEY`.
- **Embeddings del juez** (solo Answer Relevancy): `google-genai` con `gemini-embedding-001`.
- **Cuota del free tier:** `gemini-2.5-flash` permite unos 20 requests por día
  y cada corrida usa 8. Alcanza para un baseline y un experimento por día.
  El juez hace unas 8 llamadas por caso, por eso usa `gemini-3.5-flash-lite`,
  que tiene más cuota. El script espera y reintenta si choca el límite por
  minuto, y corta con un mensaje claro si se agota la cuota diaria.
- **Versión fijada:** `langchain-community` está fijado en `<0.4.2`, porque
  RAGAS 0.4.3 importa un módulo que la versión 0.4.2 eliminó.
