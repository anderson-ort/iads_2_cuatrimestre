from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas import RagAnswer
from retrieval import biencoder_retrieve, Reranker
from prompts import RAG_SYSTEM_PROMPT, RAG_HUMAN_TEMPLATE

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [("system", RAG_SYSTEM_PROMPT), ("human", RAG_HUMAN_TEMPLATE)]
)


def format_context(docs: List[Document]) -> str:
    if not docs:
        return "(sin resultados relevantes)"
    partes = [f"[{d.metadata.get('filename', 'desconocido')}]\n{d.page_content}" for d in docs]
    return "\n\n---\n\n".join(partes)


def build_rag_chain(
    api_key: str,
    vectorstore: Chroma,
    reranker: Reranker,
    model_name: str,
    temperature: float,
    k: int,
    top_n: int,
):
    llm = ChatGoogleGenerativeAI(
        model=model_name, google_api_key=api_key, temperature=temperature
    )
    structured_llm = llm.with_structured_output(RagAnswer)

    def retrieve_and_rerank(inputs: dict) -> dict:
        pregunta = inputs["pregunta"]
        candidatos = biencoder_retrieve(vectorstore, pregunta, k=k)
        top_docs = reranker.rerank(pregunta, candidatos, top_n=top_n)
        return {"pregunta": pregunta, "contexto": format_context(top_docs)}

    return RunnableLambda(retrieve_and_rerank) | RAG_PROMPT | structured_llm
