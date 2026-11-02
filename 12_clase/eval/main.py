"""Eval stage: RAGAS over the RAG path, reading the index built by the ingest stage.

python -m eval.main [dataset_name]
"""

import argparse
import logging

from src.config import configure_tracing, load_settings
from src.evaluation import DEFAULT_METRICS, build_evaluator
from src.llm import chat_model
from src.retrieval import build_retriever


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="ortelana-eval")
    parser.add_argument("dataset_name", nargs="?", default="eval_ortelana_v1")
    args = parser.parse_args()

    settings = load_settings()
    configure_tracing(settings)
    evaluator = build_evaluator(settings, build_retriever(settings), chat_model(settings))
    print(evaluator(args.dataset_name, DEFAULT_METRICS))


if __name__ == "__main__":
    main()
