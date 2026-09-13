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




# import os
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.messages import SystemMessage, HumanMessage
# 
# # Configuración de API Key (se recomienda mediante variable de entorno GOOGLE_API_KEY)
# API_KEY = os.getenv("GOOGLE_API_KEY", "TU_API_KEY_AQUI")
# 
# # Inicialización del LLM (Sección 1.5)
# llm = ChatGoogleGenerativeAI(
    # model="gemini-2.5-flash",
    # google_api_key=API_KEY,
    # temperature=0.3
# )
# 
# # Definición de mensajes estructurados (Sección 1.2)
# messages = [
    # SystemMessage(content="Eres un asistente especializado en arquitectura de software en la nube."),
    # HumanMessage(content="¿Cuáles son las ventajas de desincorporar monolitos a microservicios?")
# ]
# 
# # Invocación directa del modelo
# response = llm.invoke(messages)
# 
# print("--- Respuesta de Gemini 2.5 Flash ---")
# print(response.content)


