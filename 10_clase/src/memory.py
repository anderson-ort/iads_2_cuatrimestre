
import os
import sqlite3

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver


# En el container apunta a un volumen (ver compose.yaml) para sobrevivir al docker rm.
DB_PATH = os.getenv("DB_PATH", "data/agent.sqlite.db")

# Corto plazo (RAM)
saver_volatil = MemorySaver()

# Largo plazo (SQLite). check_same_thread=False porque FastAPI usa un threadpool.
saver_persistente = SqliteSaver(sqlite3.connect(DB_PATH, check_same_thread=False))

