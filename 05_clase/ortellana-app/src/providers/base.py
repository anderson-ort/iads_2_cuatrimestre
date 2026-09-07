from abc import ABC, abstractmethod
from typing import List, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, system_instruction: str = "") -> str:
        pass

    @abstractmethod
    def extract_structured(self, prompt: str, response_schema: Type[T]) -> T:
        pass


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass