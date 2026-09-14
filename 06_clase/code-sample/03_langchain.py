import os
import warnings
from dotenv import load_dotenv

# Silenciar advertencias informativas de HF y Google SDK
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

# Modelo de Embeddings
embeddings_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

PERSIST_DIRECTORY = "./database"

# Instanciar el VectorStore apuntando al directorio local
vectorstore = Chroma(
    persist_directory=PERSIST_DIRECTORY,
    embedding_function=embeddings_model
)

# Verificar si la colección almacenada contiene elementos reales
if vectorstore._collection.count() == 0:
    print(" Colección vacía o no existente. Creando e insertando documentos...")
    
    documentos_base = [
        Document(page_content="LangChain Core contiene las abstracciones fundamentales como Runnable, Prompts y Parsers."),
        Document(page_content="RAG (Retrieval-Augmented Generation) combina la búsqueda semántica en vector stores con la generación de LLMs."),
        Document(page_content="LCEL (LangChain Expression Language) utiliza el operador pipe | para encadenar componentes de forma declarativa."),
        Document(page_content="Sentence Transformers provee modelos locales para transformar texto en vectores numéricos densos de alta calidad.")
    ]

    splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    docs_divididos = splitter.split_documents(documentos_base)
    vectorstore.add_documents(docs_divididos)
else:
    print("Cargando base de datos vectorial existente con documentos...")

retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

TEMPLATE_RAG = """Responde únicamente basándote en el contexto proveído a continuación.
Si la información no se encuentra en el contexto, responde: 'No dispongo de suficiente información en los documentos.'

Contexto:
{context}

Pregunta: {question}

Respuesta:"""

prompt = ChatPromptTemplate.from_template(TEMPLATE_RAG)

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
    temperature=0.1
)

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

pregunta = "¿Cómo se conectan los componentes en LCEL?"
respuesta = rag_chain.invoke(pregunta)

print(f"\nPregunta: {pregunta}\n")
print(f"Respuesta Generada:\n{respuesta}")
