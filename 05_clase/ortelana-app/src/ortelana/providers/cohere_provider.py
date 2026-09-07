import json
import re
from typing import List, Type, TypeVar
import cohere
from pydantic import BaseModel
from ortelana.config import settings
from ortelana.providers.base import BaseEmbeddingProvider, BaseLLMProvider

T = TypeVar("T", bound=BaseModel)


class CohereLLMProvider(BaseLLMProvider):
    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
        self.model = settings.COHERE_LLM_MODEL

    def generate_response(self, prompt: str, system_instruction: str = "") -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat(model=self.model, messages=messages)
        return response.message.content[0].text
    
    def extract_structured(self, prompt: str, response_schema: Type[T]) -> T:
        
        schema_json = response_schema.model_json_schema()
    
        system_instruction = (
            "Eres un extractor de datos estructurados. "
            "Genera un objeto JSON que cumpla estrictamente el esquema especificado."
        )
    
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
    
        # Pasamos json_schema dentro de response_format para forzar las claves exactas
        response = self.client.chat(
            model=self.model,
            messages=messages,
            response_format={
                "type": "json_object",
                "json_schema": schema_json,  # <--- Clave para forzar la estructura de Pydantic
            },
        )
    
        raw_response = response.message.content[0].text
    
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        clean_json = match.group(0) if match else raw_response.strip()
    
        return response_schema.model_validate_json(clean_json)

class CohereEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
        self.model = settings.COHERE_EMBED_MODEL

    def embed_text(self, text: str) -> List[float]:
        response = self.client.embed(
            texts=[text],
            model=self.model,
            input_type="search_query",
            embedding_types=["float"],
        )
        return response.embeddings.float[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",
            embedding_types=["float"],
        )
        return response.embeddings.float