from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas import RouterDecision
from prompts import ROUTER_SYSTEM_PROMPT

ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [("system", ROUTER_SYSTEM_PROMPT), ("human", "{pregunta}")]
)


def build_router_chain(api_key: str, model_name: str, temperature: float, thinking_budget: int):
    # with_structured_output fuerza al modelo a devolver un RouterDecision
    # valido (via function calling), no texto libre que haya que parsear.
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        thinking_budget=thinking_budget,
    )
    structured_llm = llm.with_structured_output(RouterDecision)
    return ROUTER_PROMPT | structured_llm
