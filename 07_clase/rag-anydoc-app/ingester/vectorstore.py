from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_chroma import Chroma
from .embeddings import IEmbeddingProvider

class VectorStoreManager:
    def __init__(self, embedding_provider: IEmbeddingProvider, persist_dir: str, collection_name:str):
        self.embeddings = embedding_provider.get_embeddings()
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        
    def get_vectorstore(self) -> Chroma:
        return Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
        )

    def add_documents(self, documents: List[Document]) -> int:
        vs = self.get_vectorstore()
        vs.add_documents(documents)
        return len(documents)

    def get_stats(self) -> Dict[str, Any]:
        vs = self.get_vectorstore()
        data = vs.get(include=["metadatas"])
        metadatas = data.get("metadatas", []) or []
        sources = {m["filename"] for m in metadatas if m and "filename" in m}
        return {
            "total_chunks": len(data.get("ids", [])),
            "total_files": len(sources),
            "file_names": sorted(sources),
        }
