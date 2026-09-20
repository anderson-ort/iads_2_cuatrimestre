from typing import List
import anydoc
from langchain_core.documents import Document


class AnyDocParserService:
    def parse(self, file_path: str, filename: str) -> List[Document]:
        try:
            markdown_content = anydoc.to_markdown(file_path)
            return [
                Document(
                    page_content=markdown_content,
                    metadata={"filename": filename, "parser": "firecrawl-anydoc"},
                )
            ]
        except Exception as e:
            raise ValueError(
                f"Error al convertir '{filename}' con anydoc: {e}. "
                "Si el archivo es un PDF escaneado, procesalo con la CLI/API de "
                "Firecrawl Parse (OCR hospedado) antes de ingestarlo aquí."
            )
