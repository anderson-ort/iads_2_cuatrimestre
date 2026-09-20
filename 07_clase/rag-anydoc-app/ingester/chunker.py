from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


class HybridChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3"), ("####", "H4")]
        )
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def split_documents(self, documents: List[Document]) -> List[Document]:
        final_chunks = []
        for doc in documents:
            semantic_splits = self.markdown_splitter.split_text(doc.page_content)
            if semantic_splits:
                for split in semantic_splits:
                    split.metadata.update(doc.metadata)
                final_chunks.extend(self.recursive_splitter.split_documents(semantic_splits))
            else:
                final_chunks.extend(self.recursive_splitter.split_documents([doc]))
        return final_chunks
