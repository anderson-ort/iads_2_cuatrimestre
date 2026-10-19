# Memoria de corto y largo plazo con truncado a 10

## Cómo funciona

- **Corto plazo:** `MemorySaver` guarda el estado por `thread_id` en RAM y se pierde al reiniciar.
- **Largo plazo:** `SqliteSaver` guarda el mismo estado en `memoria.db` y sobrevive reinicios.
- **Truncado a 10:** ya está aplicado en `agentes.py` con `recortar()`, tanto en el router como en cada agente (vía `pre_model_hook`). El LLM nunca recibe más de los últimos 10 mensajes. El historial completo queda guardado en el checkpointer y `/state` lo muestra truncado.

## memoria.py

```python
import sqlite3

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from agentes import crear_orquestador

DB_PATH = "memoria.db"

# Corto plazo (RAM)
saver_volatil = MemorySaver()

# Largo plazo (SQLite). check_same_thread=False porque FastAPI usa un threadpool.
saver_persistente = SqliteSaver(sqlite3.connect(DB_PATH, check_same_thread=False))

# Mismo grafo, distinto checkpointer
orquestador_volatil = crear_orquestador(saver_volatil)
orquestador_persistente = crear_orquestador(saver_persistente)
```

## Prueba de persistencia

```python
from langchain_core.messages import HumanMessage
from memoria import orquestador_persistente

cfg = {"configurable": {"thread_id": "demo123456789abc"}}

orquestador_persistente.invoke({"messages": [HumanMessage(content="Consulta el CUIT 30712345678")]}, cfg)
r = orquestador_persistente.invoke({"messages": [HumanMessage(content="En que localidad esta?")]}, cfg)
print(r["messages"][-1].content)  # recuerda el CUIT anterior, incluso tras reiniciar el proceso
```

## Alternativa con MongoDB -> Les recomiendo realizarlo para jugar un poco con alternativas que se vieron en clase

Si preferís Mongo en lugar de SQLite, instalá `langgraph-checkpoint-mongodb` y reemplazá `saver_persistente` por:

```python
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

saver_persistente = MongoDBSaver(MongoClient("mongodb://localhost:27017"))
```

