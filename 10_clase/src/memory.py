
import sqlite3

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver


DB_PATH = "data/agent.sqlite.db"

# Corto plazo (RAM)
saver_volatil = MemorySaver()

# Largo plazo (SQLite). check_same_thread=False porque FastAPI usa un threadpool.
saver_persistente = SqliteSaver(sqlite3.connect(DB_PATH, check_same_thread=False))

