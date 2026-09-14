import os
from dotenv import load_dotenv
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

# 1. Configurar el token de Hugging Face (variable de entorno HF_TOKEN)
HF_TOKEN = os.getenv("HF_TOKEN", "TU_HF_TOKEN_AQUI")

# 2. Crear el LLM base apuntando al modelo Instruct Qwen
llm = HuggingFaceEndpoint(
    repo_id="Qwen/Qwen2.5-7B-Instruct",
    huggingfacehub_api_token=HF_TOKEN,
    task="text-generation",
    temperature=0.3,
    provider="featherless-ai",  # o "novita", "hyperbolic", "fireworks"
)

# 3. Envolverlo en ChatHuggingFace para formatear la plantilla de ChatML automáticamente
chat_model = ChatHuggingFace(llm=llm)

# 4. Tus mensajes estructurados
messages = [
    SystemMessage(content="Eres un asistente especializado en arquitectura de software en la nube."),
    HumanMessage(content="¿Cuáles son las ventajas de desincorporar monolitos a microservicios?")
]

# 5. Invocar al modelo de Liquid AI
response = chat_model.invoke(messages)
print(response.content)
