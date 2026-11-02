"""RAGAS evaluation of the deterministic RAG path (hybrid retrieval + synthesizer)."""

import json
import logging
import math
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from src.config import Settings
from src.graph import synthesize
from src.retrieval import HybridRetriever

logger = logging.getLogger(__name__)

Metric = Literal["faithfulness", "answer_relevance", "context_precision", "context_recall"]
# Judge LLM calls per sample: context_recall 1, answer_relevance 1 (+ embeddings),
# faithfulness 2, context_precision 1 per retrieved context (top_n). At most 2 metrics
# per run keeps the free-tier quota low; the default is the cheapest pair.
MAX_METRICS = 2
DEFAULT_METRICS: list[Metric] = ["answer_relevance", "context_recall"]
DATASET_NAME = r"^[A-Za-z0-9_-]+$"

# (question, answer, contexts, reference) -> score in [0, 1], or NaN when it does not apply
Scorer = Callable[[str, str, list[str], str], float]
Answerer = Callable[[str], tuple[str, list[str]]]


@dataclass(frozen=True)
class Sample:
    question: str
    ground_truth: str


@dataclass(frozen=True)
class EvalReport:
    samples_evaluated: int
    scores: dict[str, float | None]  # None: no sample produced a valid score


def dataset_path(directory: Path, name: str) -> Path:
    if not re.fullmatch(DATASET_NAME, name):
        raise ValueError(f"Invalid dataset name: {name!r}")
    return directory / f"{name}.json"


def load_dataset(path: Path) -> list[Sample]:
    records = json.loads(path.read_text(encoding="utf-8"))
    return [Sample(r["question"], r["ground_truth"]) for r in records]


def evaluate(
    samples: Sequence[Sample],
    answer: Answerer,
    scorers: dict[str, Scorer],
    metrics: Sequence[str],
) -> EvalReport:
    values: dict[str, list[float]] = {m: [] for m in metrics}
    for sample in samples:
        response, contexts = answer(sample.question)
        for metric in metrics:
            score = scorers[metric](sample.question, response, contexts, sample.ground_truth)
            logger.info("%s | %s = %.2f", sample.question[:60], metric, score)
            values[metric].append(score)
    return EvalReport(len(samples), {m: _mean(v) for m, v in values.items()})


def _mean(values: list[float]) -> float | None:
    valid = [v for v in values if not math.isnan(v)]
    return round(sum(valid) / len(valid), 2) if valid else None


def _with_retries(fn: Callable[[], float], wait_seconds: float, attempts: int = 3) -> float:
    """The Gemini free tier answers 429 (rate limit) or 503 (overloaded): wait and retry."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # RAGAS wraps provider errors in several exception types
            retryable = any(code in str(exc) for code in ("429", "RESOURCE_EXHAUSTED", "503"))
            if not retryable or attempt == attempts:
                raise
            logger.warning("Judge rate limited, retrying in %ss", wait_seconds)
            time.sleep(wait_seconds)
    raise AssertionError("unreachable")


def build_scorers(settings: Settings) -> dict[str, Scorer]:
    """RAGAS metrics with Gemini as judge, through its OpenAI-compatible endpoint
    (RAGAS 0.4 has issues with the async google-genai client)."""
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    from google import genai
    from openai import AsyncOpenAI
    from ragas.embeddings import GoogleEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    key = settings.secrets.google_api_key
    if key is None:
        raise ValueError("GOOGLE_API_KEY is required for the RAGAS judge")
    cfg = settings.evaluation
    judge = llm_factory(
        cfg.judge_model,
        client=AsyncOpenAI(
            api_key=key.get_secret_value(),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ),
    )
    embeddings = GoogleEmbeddings(
        client=genai.Client(api_key=key.get_secret_value()), model=cfg.judge_embedding_model
    )
    faithfulness = Faithfulness(llm=judge)
    relevance = AnswerRelevancy(llm=judge, embeddings=embeddings, strictness=1)  # 1 = less quota
    precision = ContextPrecision(llm=judge)
    recall = ContextRecall(llm=judge)

    def scored(call: Callable[[], object]) -> float:
        return _with_retries(lambda: call().value, cfg.retry_wait_seconds)

    return {
        "faithfulness": lambda q, a, c, r: scored(
            lambda: faithfulness.score(user_input=q, response=a, retrieved_contexts=c)
        ),
        "answer_relevance": lambda q, a, c, r: scored(
            lambda: relevance.score(user_input=q, response=a)
        ),
        "context_precision": lambda q, a, c, r: scored(
            lambda: precision.score(user_input=q, reference=r, retrieved_contexts=c)
        ),
        "context_recall": lambda q, a, c, r: scored(
            lambda: recall.score(user_input=q, reference=r, retrieved_contexts=c)
        ),
    }


def build_evaluator(
    settings: Settings, retriever: HybridRetriever, chat: BaseChatModel
) -> Callable[[str, Sequence[str]], EvalReport]:
    scorers = build_scorers(settings)

    def answer(question: str) -> tuple[str, list[str]]:
        contexts = [d.page_content for d in retriever.search(question)]
        return synthesize(chat, contexts, [HumanMessage(question)]).text, contexts

    def run(dataset_name: str, metrics: Sequence[str]) -> EvalReport:
        path = dataset_path(settings.path(settings.evaluation.datasets_dir), dataset_name)
        return evaluate(load_dataset(path), answer, scorers, metrics)

    return run
