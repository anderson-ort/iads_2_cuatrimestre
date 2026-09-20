from abc import ABC, abstractmethod
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_cohere import CohereEmbeddings


class IEmbeddingProvider(ABC):
    @abstractmethod
    def get_embeddings(self) -> Embeddings:
        pass


class HuggingFaceEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, model_name):
        self.model_name = model_name

    def get_embeddings(self) -> Embeddings:
        return HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )


class GeminiEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, model_name:str, api_key: str):
        self.api_key = api_key
        self.model_name = model_name

    def get_embeddings(self) -> Embeddings:
        if not self.api_key:
            raise ValueError("Se requiere una API Key válida para Gemini.")
        return GoogleGenerativeAIEmbeddings(model=self.model_name, google_api_key=self.api_key)


class CohereEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, model_name:str, api_key: str):
        self.api_key = api_key
        self.model_name = model_name

    def get_embeddings(self) -> Embeddings:
        if not self.api_key:
            raise ValueError("Se requiere una API Key válida para Cohere.")
        return CohereEmbeddings(model=self.model_name, cohere_api_key=self.api_key)
