# Punto 1: Agente con tools y orquestador multiagente

```bash
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic[email]>=2.7
python-dotenv>=1.0
httpx>=0.27
ddgs>=9.0
langchain-core>=0.3
langchain-google-genai>=2.0
langchain-cohere>=0.4
langgraph>=0.3
langgraph-checkpoint-sqlite>=2.0
```

## Ejecución y pruebas

```bash
uvicorn main:app --reload --port 8000
```

```bash
# 1. Health
curl http://localhost:8000/health

# 2. Volatil: la primera respuesta devuelve un thread_id; reutilizalo para mantener contexto
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "Que productos hay en stock?"}'

# 3. Persistente con email (el thread_id sale del hash del email, siempre el mismo)
curl -X POST http://localhost:8000/query-memory \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "Consulta el CUIT 30712345678", "email": "consultas@castelar.com"}'

# 4. Seguimiento en el mismo hilo (usa el thread_id devuelto, o el mismo email)
curl -X POST http://localhost:8000/query-memory \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "En que localidad esta esa empresa?", "email": "consultas@castelar.com"}'

# 5. Historial (usa el thread_id de la respuesta anterior)
curl http://localhost:8000/state/<thread_id>
curl "http://localhost:8000/state/<thread_id>?memoria=volatil"
```

## Notas finales

- Verificá los nombres de modelo (`gemini-2.5-flash`, `command-a-03-2025`) contra tu cuenta; ambos se pueden sobrescribir por variable de entorno.
- `pre_model_hook` en `create_react_agent` requiere `langgraph>=0.3`. Con versiones anteriores no existe.
- Un hash de email como `thread_id` es predecible: quien conozca el email puede leer ese historial en `/state`. Si la API es pública, agregá autenticación o usá un UUID aleatorio.
