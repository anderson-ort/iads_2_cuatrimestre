"""Entrypoint: wires dependencies and exposes the CLI.

uv run main.py ingest
uv run main.py search "<query>"
uv run main.py ask --session <id> "<message>"
uv run main.py eval [dataset_name]
uv run main.py serve
"""

import argparse
import logging

import uvicorn
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph.state import CompiledStateGraph
from pymongo import MongoClient

from src.api import create_app
from src.config import Settings, configure_tracing, load_settings
from src.cuit import build_cuit_client
from src.evaluation import DEFAULT_METRICS, build_evaluator
from src.graph import build_graph
from src.guardrails import build_guardrails
from src.ingest import build_index
from src.llm import chat_model
from src.retrieval import HybridRetriever, build_retriever
from src.web import build_web_search


def build_orchestrator(
    settings: Settings, retriever: HybridRetriever, checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph:
    return build_graph(
        chat=chat_model(settings),
        router=chat_model(settings, fast=True),
        retriever=retriever,
        cuit_client=build_cuit_client(settings),
        web=build_web_search(settings),
        checkpointer=checkpointer,
    )


def ask(settings: Settings, session_id: str, message: str) -> None:
    with MongoClient(settings.secrets.mongodb_uri.get_secret_value()) as client:
        saver = MongoDBSaver(client, db_name=settings.mongo.checkpoint_database)
        graph = build_orchestrator(settings, build_retriever(settings), saver)
        state = graph.invoke(
            {"messages": [("human", message)]}, {"configurable": {"thread_id": session_id}}
        )
    print(f"[{state['route']}] {state['messages'][-1].text}")


def serve(settings: Settings) -> None:
    guardrails = build_guardrails(
        settings.path(settings.guardrails.config_dir),
        chat_model(settings, fast=True),
        settings.guardrails.competitors,
    )
    retriever = build_retriever(settings)
    evaluator = build_evaluator(settings, retriever, chat_model(settings))
    with MongoClient(settings.secrets.mongodb_uri.get_secret_value()) as client:
        saver = MongoDBSaver(client, db_name=settings.mongo.checkpoint_database)
        app = create_app(build_orchestrator(settings, retriever, saver), guardrails, evaluator)
        uvicorn.run(app, host=settings.api.host, port=settings.api.port)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="ortelana")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest", help="Rebuild the Chroma index from documents and catalog")
    search = commands.add_parser("search", help="Run a hybrid search")
    search.add_argument("query")
    chat = commands.add_parser("ask", help="Send one message to the orchestrator")
    chat.add_argument("--session", required=True, help="Conversation id (LangGraph thread_id)")
    chat.add_argument("message")
    evaluation = commands.add_parser("eval", help="Run the RAGAS evaluation")
    evaluation.add_argument("dataset_name", nargs="?", default="eval_ortelana_v1")
    commands.add_parser("serve", help="Start the REST API")
    args = parser.parse_args()

    settings = load_settings()
    configure_tracing(settings)
    if args.command == "ingest":
        build_index(settings)
    elif args.command == "search":
        for doc in build_retriever(settings).search(args.query):
            score = doc.metadata.get("relevance_score", 0.0)
            print(f"[{score:.3f}] {doc.id} ({doc.metadata['tipo']}): {doc.page_content[:120]}")
    elif args.command == "ask":
        ask(settings, args.session, args.message)
    elif args.command == "eval":
        evaluator = build_evaluator(settings, build_retriever(settings), chat_model(settings))
        print(evaluator(args.dataset_name, DEFAULT_METRICS))
    else:
        serve(settings)


if __name__ == "__main__":
    main()
