from typing import List, Type, TypeVar
from google import genai
from google.genai import types
from pydantic import BaseModel
from ortelana.config import settings
from ortelana.providers.base import BaseEmbeddingProvider, BaseLLMProvider

T = TypeVar("T", bound=BaseModel)


class GeminiLLMProvider(BaseLLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_LLM_MODEL

    def generate_response(self, prompt: str, system_instruction: str = "") -> str:
        config = (
            types.GenerateContentConfig(system_instruction=system_instruction)
            if system_instruction
            else None
        )
        response = self.client.models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return response.text

    def extract_structured(self, prompt: str, response_schema: Type[T]) -> T:
        config = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=response_schema
        )
        response = self.client.models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return response_schema.model_validate_json(response.text)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_EMBED_MODEL

    def embed_text(self, text: str) -> List[float]:
        response = self.client.models.embed_content(
            model=self.model, contents=text
        )
        return response.embedding.values

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]