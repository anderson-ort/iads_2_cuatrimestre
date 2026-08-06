from langchain_chroma import Chroma
from langchain_wrapper import GeminiEmbeddingsLangchain

embeddings = GeminiEmbeddingsLangchain()
vectorstore = Chroma(
    collection_name="catalogo_telas",
    embedding_function=embeddings,
    persist_directory="./ortelana_vector_db",
)

print(f"Colección conectada: {vectorstore._collection.count()} registros")

docs = vectorstore.similarity_search("tela resistente para tapiceria", k=2)
for doc in docs:
    print(f"  -> {doc.page_content[:80]}... | {doc.metadata}")
