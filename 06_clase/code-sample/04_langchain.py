import os
import warnings
from dotenv import load_dotenv

# Silenciar advertencias informativas
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser

from langchain_chroma import Chroma
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

# 1. Inicialización de Embeddings y Vector Store
embeddings_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

PERSIST_DIRECTORY = "./database"

vectorstore = Chroma(
    persist_directory=PERSIST_DIRECTORY,
    embedding_function=embeddings_model
)

# Cargar documentos si la base de datos está vacía
if vectorstore._collection.count() == 0:
    documentos_base = [
        Document(page_content="LangChain Core contiene las abstracciones fundamentales como Runnable, Prompts y Parsers."),
        Document(page_content="RAG (Retrieval-Augmented Generation) combina la búsqueda semántica en vector stores con la generación de LLMs."),
        Document(page_content="LCEL (LangChain Expression Language) utiliza el operador pipe | para encadenar componentes de forma declarativa."),
        Document(page_content="Sentence Transformers provee modelos locales para transformar texto en vectores numéricos densos de alta calidad.")
    ]
    splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    vectorstore.add_documents(splitter.split_documents(documentos_base))

# 2. Definición explícita del Retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 3. Función de transformación custom para unir documentos recuperados
def format_docs(docs):
    return "\n---\n".join([doc.page_content for doc in docs])

# 4. Construcción del pipeline con RunnableParallel
mapa_entradas = RunnableParallel(
    context=retriever | format_docs,
    question=RunnablePassthrough()
)

prompt_avanzado = ChatPromptTemplate.from_template(
    "Contexto Informativo:\n{context}\n\nConsulta del Usuario: {question}\n\nRespuesta Analítica:"
)

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
    temperature=0.2
)

# 5. Ensamblado LCEL completo
advanced_chain = mapa_entradas | prompt_avanzado | llm | StrOutputParser()

# 6. Invocación con streaming
print("--- Streaming de Respuesta ---\n")
for chunk in advanced_chain.stream("¿Qué función cumplen los Sentence Transformers?"):
    print(chunk, end="", flush=True)
print("\n")
