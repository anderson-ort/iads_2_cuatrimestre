from langchain_huggingface import HuggingFaceEmbeddings

# Configuración del modelo con embeddings estáticos multilingües
embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/static-similarity-mrl-multilingual-v1",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

# Generación de vector para una consulta
texto_ejemplo = "LangChain permite orquestar pipelines de Inteligencia Artificial."
vector_resultado = embeddings_model.embed_query(texto_ejemplo)

print(f"Texto analizado: '{texto_ejemplo}'")
print(f"Dimensión del vector generado: {len(vector_resultado)}")
print(f"Muestra de los primeros 5 valores: {vector_resultado[:5]}")
