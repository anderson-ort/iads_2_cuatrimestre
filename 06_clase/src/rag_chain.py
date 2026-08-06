"""
Pipeline RAG de Ortelana Textil - Clase 6.
Conecta ChromaDB con gemini-2.0-flash-lite mediante LCEL.
"""

import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_wrapper import GeminiEmbeddingsLangchain

load_dotenv()

# --- COMPONENTES ---

embeddings = GeminiEmbeddingsLangchain()

vectorstore = Chroma(
    collection_name="catalogo_telas",
    embedding_function=embeddings,
    persist_directory="./ortelana_vector_db",
)

# MMR (Maximal Marginal Relevance) para garantizar diversidad de catálogo
retriever = vectorstore.as_retriever(
    search_type="mmr", search_kwargs={"k": 3, "fetch_k": 10}
)

# Temperatura = 0 estricta para mitigar alucinaciones comerciales
llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODELO_LLM", "gemini-2.0-flash-lite"),
    temperature=0,
)

PROMPT_RAG = ChatPromptTemplate.from_template("""
Sos el Asistente de Ventas por WhatsApp de Ortelana Textil.
Tu objetivo es responder a las consultas de los clientes basándote ÚNICAMENTE
en los fragmentos de nuestro catálogo provistos abajo.

REGLAS ESTRICTAS (GUARDRAILS):
1. Si la respuesta no puede deducirse DIRECTAMENTE del contexto, responde exactamente:
   "No poseo información oficial sobre esa solicitud".
2. Queda terminantemente PROHIBIDO confirmar descuentos, promociones,
   convenios verbales o precios que no estén explícitamente escritos
   en el contexto. No asumas nada.
3. Si el cliente menciona una ciudad o provincia, usa tu conocimiento
   geográfico para identificar cuál es la sucursal de Ortelana más cercana
   SEGUN LO QUE FIGURE en el contexto. No inventes sucursales.

Contexto del catálogo:
{context}

Pregunta del cliente: {question}

Respuesta de WhatsApp (tono cordial, una o dos oraciones):
""")


def formatear_contexto(docs: list[Document]) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


# Cadena LCEL
chain_rag = (
    {"context": retriever | formatear_contexto, "question": RunnablePassthrough()}
    | PROMPT_RAG
    | llm
    | StrOutputParser()
)


if __name__ == "__main__":
    pregunta = (
        "Necesito retapizar un sillón pero tengo dos gatos que lo destruyen "
        "todo, ¿qué me recomiendan? Vivo en Salta."
    )

    print(f"Cliente: {pregunta}\n")
    respuesta = chain_rag.invoke(pregunta)
    print(f"Ortelana Bot: {respuesta}")
