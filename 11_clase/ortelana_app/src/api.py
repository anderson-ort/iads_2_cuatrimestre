"""FastAPI app: guardrails -> LangGraph orchestrator -> guardrails."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from src.evaluation import EvalReport
from src.guardrails import Guardrails
from src.schemas import ChatRequest, ChatResponse, EvalRequest, EvalResponse

Evaluator = Callable[[str, Sequence[str]], EvalReport]


def create_app(graph: CompiledStateGraph, guardrails: Guardrails, evaluator: Evaluator) -> FastAPI:
    app = FastAPI(title="Ortelana Assistant", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        checked_input = await guardrails.check_input(request.message)
        if not checked_input.passed:
            return ChatResponse(
                session_id=request.session_id,
                response=checked_input.message,
                routing_used=None,
                guardrail_status="blocked_input",
            )

        config = {
            "configurable": {"thread_id": request.session_id},
            "metadata": {"user_id": request.user_id},  # visible in LangSmith traces
        }
        # The graph and MongoDBSaver are synchronous: run them off the event loop.
        state = await run_in_threadpool(
            graph.invoke, {"messages": [("human", request.message)]}, config
        )
        answer = state["messages"][-1]

        checked_output = await guardrails.check_output(request.message, answer.text)
        if not checked_output.passed:
            # Same id replaces the blocked answer, so the next turn never sees it.
            replacement = AIMessage(id=answer.id, content=checked_output.message)
            await run_in_threadpool(graph.update_state, config, {"messages": [replacement]})

        return ChatResponse(
            session_id=request.session_id,
            response=checked_output.message,
            routing_used=state["route"],
            guardrail_status="passed" if checked_output.passed else "blocked_output",
        )

    @app.post("/api/v1/eval", response_model=EvalResponse)
    def run_eval(request: EvalRequest) -> EvalResponse:
        # Synchronous on purpose: FastAPI runs it in a worker thread. With 5 samples and
        # the free tier it can take a few minutes.
        try:
            report = evaluator(request.dataset_name, request.metrics)
        except FileNotFoundError:
            raise HTTPException(404, f"Dataset not found: {request.dataset_name}") from None
        return EvalResponse(
            samples_evaluated=report.samples_evaluated,
            scores=report.scores,
            timestamp=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )

    return app
