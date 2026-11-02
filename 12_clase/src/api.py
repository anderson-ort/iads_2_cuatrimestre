"""FastAPI app: guardrails -> LangGraph orchestrator -> guardrails.

Evaluation is not served here: it runs as a separate stage (see ../eval).
"""

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from src.guardrails import Guardrails
from src.schemas import ChatRequest, ChatResponse


def create_app(graph: CompiledStateGraph, guardrails: Guardrails) -> FastAPI:
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

    return app
