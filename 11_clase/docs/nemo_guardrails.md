# NeMo Guardrails: el control de seguridad del chatbot

**En una frase:** NeMo Guardrails revisa cada mensaje *antes* de que entre al asistente y cada respuesta *antes* de que salga. En Ortelana frena temas fuera de lugar, intentos de manipular al bot y menciones a competidores, sin tocar el código del grafo.

---

## 1. ¿Qué es?

NeMo Guardrails es una librería open source de NVIDIA para poner "barandas" (*rails*) alrededor de un LLM. Una baranda es una regla que se ejecuta en un punto fijo de la conversación:

| Tipo de rail | Cuándo corre | Para qué |
|--------------|--------------|----------|
| **Input rail** | Antes de procesar el mensaje del usuario | Bloquear lo que no debería llegar al sistema |
| **Output rail** | Antes de devolver la respuesta | Bloquear respuestas inadecuadas |
| Dialog rail | Durante la conversación | Guiar el diálogo (no lo usamos) |

Piensalo como el control de seguridad de un aeropuerto: no decide a dónde viajás (eso lo hace el grafo), solo decide si podés pasar.

## 2. ¿Cómo funciona?

Las reglas se escriben en archivos de configuración, no en Python:

| Archivo | Qué contiene |
|---------|--------------|
| `config.yml` | Qué rails están activos y en qué orden |
| `*.co` (Colang) | Flujos y respuestas fijas del bot, en un lenguaje simple parecido a pseudocódigo |
| `prompts.yml` | Los prompts que usa NeMo cuando le pregunta a un LLM "¿esto se bloquea?" |

Hay dos formas de decidir si algo se bloquea:

1. **Con código (determinista):** una función Python devuelve `True`/`False`. Rápido y gratis.
2. **Con un LLM (*self check*):** NeMo le manda el mensaje al modelo con un prompt y el modelo responde "Yes" o "No". Más flexible, pero cuesta una llamada.

## 3. ¿Cómo lo usamos en Ortelana?

La configuración está en `ortelana_app/guardrails/` y el código que la usa en `ortelana_app/src/guardrails.py`.

### El recorrido de un mensaje

```text
POST /api/v1/chat
   │
   ▼
[INPUT] 1. check competitors  → función Python, sin LLM
        2. self check input   → modelo rápido responde Yes/No
   │  bloqueado → respuesta fija en español, el grafo NUNCA se ejecuta
   ▼
LangGraph (router → RAG / CUIT / ReAct / general)
   │
   ▼
[OUTPUT] 3. self check output → modelo rápido responde Yes/No
   │  bloqueado → se devuelve un rechazo y se reemplaza en el historial
   ▼
respuesta al usuario
```

### Las tres reglas

| Regla | Cómo decide | Qué bloquea | Qué responde |
|-------|-------------|-------------|--------------|
| `check competitors` | Python busca nombres de la lista `competitors` de `config.toml` (sin importar tildes ni mayúsculas) | Preguntas sobre otras empresas | "No puedo darte información sobre otras empresas, pero con gusto te ayudo..." |
| `self check input` | LLM con el prompt de `prompts.yml` | Fuera de tema, insultos, "ignorá tus instrucciones", pedidos destructivos | "Disculpá, solo puedo ayudarte con consultas sobre telas..." |
| `self check output` | LLM con el prompt de `prompts.yml` | Respuestas groseras, en otro idioma, que hablan de competidores, revelan instrucciones o inventan datos | El mismo rechazo |

### Decisiones de diseño

- **Competidores sin LLM:** es una lista de nombres, no hace falta "pensar". Ahorra una llamada y nunca se equivoca con los nombres cargados.
- **Usamos el modelo rápido** (`fast_model` en `config.toml`) para los self checks: solo tiene que responder Yes/No.
- **El rechazo de salida se borra de la memoria:** si una respuesta se bloquea, la reemplazamos en MongoDB por el mensaje de rechazo. Así el bot no "recuerda" su respuesta mala en el siguiente turno.
- **La API informa qué pasó** en `guardrail_status`: `passed`, `blocked_input` o `blocked_output`.

## 4. ¿Por qué es relevante para nosotros?

- **Lo pide el PRD:** competidores, off-topic y tono corporativo (sección 4.1).
- **Lo pide el TP:** resistencia a *prompt injection* (`tp_consignas/ortelana_steps.md`).
- **Ahorra cuota:** un mensaje bloqueado a la entrada no ejecuta el router, el RAG ni el agente.
- **Separa responsabilidades:** las políticas de seguridad viven en `guardrails/`, no mezcladas en los prompts del grafo. Cambiar una regla no obliga a tocar la orquestación.

## 5. Costo y limitaciones

| Tema | Detalle |
|------|---------|
| Costo | 2 llamadas extra al modelo rápido por mensaje aprobado (entrada + salida) |
| Falsos positivos | El LLM puede bloquear algo válido. Se ajusta editando `prompts.yml` |
| Lista de competidores | Solo detecta los nombres exactos cargados. Hoy son **ejemplos**: reemplazalos por los reales |
| Latencia | Cada self check suma el tiempo de una llamada al LLM |

## Para probarlo

```bash
cd 11_clase/ortelana_app
uv run pytest tests/test_guardrails.py -v   # sin red: usa un LLM falso
```

Con la API levantada, probá un mensaje fuera de tema ("¿quién ganó el partido?") y mirá `guardrail_status`.
