"""LangGraph orchestrator.

START -> router -> rag_direct  -> synthesizer -> END
                -> cuit_direct -> synthesizer -> END
                -> general     -> synthesizer -> END   (no context)
                -> react_agent ----------------> END   (the agent writes its own answer)
"""

from typing import Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, trim_messages
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from src import prompts
from src.cuit import CuitClient, describe_cuit, extract_cuit
from src.retrieval import HybridRetriever
from src.tools import build_tools
from src.web import WebSearch

Route = Literal["rag_direct", "cuit_direct", "react_agent", "general"]
MAX_MESSAGES = 10


class RouteDecision(BaseModel):
    route: Route


class AgentState(MessagesState):
    route: Route
    context: list[str]  # retrieved for this turn only; also used by the RAGAS evaluation


def recent(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Last N messages starting on a human one, so tool call/result pairs are never split."""
    return trim_messages(
        messages,
        max_tokens=MAX_MESSAGES,
        token_counter=len,
        strategy="last",
        start_on="human",
    )


def last_question(state: AgentState) -> str:
    return next(m.content for m in reversed(state["messages"]) if m.type == "human")


def synthesize(chat: BaseChatModel, context: list[str], messages: list[BaseMessage]) -> BaseMessage:
    """Answer grounded on `context`. Shared by the graph and the RAGAS evaluation."""
    system = prompts.SYNTHESIZER.format(context="\n\n".join(context))
    return chat.invoke([SystemMessage(system), *recent(messages)])


def build_graph(
    *,
    chat: BaseChatModel,
    router: BaseChatModel,
    retriever: HybridRetriever,
    cuit_client: CuitClient,
    web: WebSearch,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    classifier = router.with_structured_output(RouteDecision)
    agent = create_agent(
        model=chat,
        tools=build_tools(retriever, cuit_client, web),
        system_prompt=prompts.REACT_AGENT,
        name="react_agent",
    )

    def route_node(state: AgentState) -> dict:
        decision = classifier.invoke([SystemMessage(prompts.ROUTER), *recent(state["messages"])])
        return {"route": decision.route, "context": []}

    def rag_node(state: AgentState) -> dict:
        return {"context": [d.page_content for d in retriever.search(last_question(state))]}

    def cuit_node(state: AgentState) -> dict:
        cuit = extract_cuit(last_question(state))
        if cuit is None:
            return {"context": ["The user did not provide a CUIT; ask for it."]}
        return {"context": [describe_cuit(cuit_client, cuit)]}

    def react_node(state: AgentState) -> dict:
        result = agent.invoke({"messages": recent(state["messages"])})
        return {"messages": [result["messages"][-1]]}

    def synthesizer_node(state: AgentState) -> dict:
        return {"messages": [synthesize(chat, state["context"], state["messages"])]}

    graph = StateGraph(AgentState)
    graph.add_node("router", route_node)
    graph.add_node("rag_direct", rag_node)
    graph.add_node("cuit_direct", cuit_node)
    graph.add_node("react_agent", react_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "rag_direct": "rag_direct",
            "cuit_direct": "cuit_direct",
            "react_agent": "react_agent",
            "general": "synthesizer",
        },
    )
    graph.add_edge("rag_direct", "synthesizer")
    graph.add_edge("cuit_direct", "synthesizer")
    graph.add_edge("synthesizer", END)
    graph.add_edge("react_agent", END)
    return graph.compile(checkpointer=checkpointer)
