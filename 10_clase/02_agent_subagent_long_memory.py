"""Demo del orquestador de src/agent.py con memoria persistente (SqliteSaver, data/agent.sqlite.db).

START -> router -> fiscal / datos / web / general -> END
"""
from langchain_core.messages import HumanMessage

from src.agent import crear_orquestador
from src.memory import saver_persistente

if __name__ == "__main__":
    orquestador = crear_orquestador(saver_persistente)
    cfg = {"configurable": {"thread_id": "demo123456789abc"}}

    r = orquestador.invoke(
        {"messages": [HumanMessage(content="Textiles Norpatagonia es distribuidor? Que domicilio fiscal tiene?")]},
        cfg,
    )
    print(r["messages"][-1].content)
    r = orquestador.invoke({"messages": [HumanMessage(content="Y que condicion impositiva tiene?")]}, cfg)
    print(r["messages"][-1].content)
    print("Ruta elegida:", orquestador.get_state(cfg).values["ruta"])
