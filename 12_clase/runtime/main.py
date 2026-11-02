"""Runtime stage: serves the assistant. The only stage deployed to production.

python -m runtime.main serve
python -m runtime.main search "<query>"
python -m runtime.main ask --session <id> "<message>"
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
from src.graph import build_graph
from src.guardrails import build_guardrails
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
        graph = build_orchestrator(settings, build_retriever(settings, client), saver)
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
    with MongoClient(settings.secrets.mongodb_uri.get_secret_value()) as client:
        retriever = build_retriever(settings, client)
        saver = MongoDBSaver(client, db_name=settings.mongo.checkpoint_database)
        app = create_app(build_orchestrator(settings, retriever, saver), guardrails)
        uvicorn.run(app, host=settings.api.host, port=settings.api.port)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="ortelana-runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Run a hybrid search")
    search.add_argument("query")
    chat = commands.add_parser("ask", help="Send one message to the orchestrator")
    chat.add_argument("--session", required=True, help="Conversation id (LangGraph thread_id)")
    chat.add_argument("message")
    commands.add_parser("serve", help="Start the REST API")
    args = parser.parse_args()

    settings = load_settings()
    configure_tracing(settings)
    if args.command == "search":
        with MongoClient(settings.secrets.mongodb_uri.get_secret_value()) as client:
            for doc in build_retriever(settings, client).search(args.query):
                score = doc.metadata.get("relevance_score", 0.0)
                print(f"[{score:.3f}] {doc.id} ({doc.metadata['tipo']}): {doc.page_content[:120]}")
    elif args.command == "ask":
        ask(settings, args.session, args.message)
    else:
        serve(settings)


if __name__ == "__main__":
    main()
