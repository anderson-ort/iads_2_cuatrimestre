"""Pruebas de /query-memory sin LLM real ni red.

Un LLM falso responde "[n] <ultima pregunta>", donde n es la cantidad de mensajes
humanos que vio: si n crece turno a turno, el hilo conserva su historial.
El router elige agente por palabra clave, asi la ruta de cada turno es predecible.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite import SqliteSaver

import main
from src.schemas import Ruta

PALABRAS_RUTA = {"cuit": "fiscal", "stock": "datos", "internet": "web"}
API_VERSION = "/api/v1"

def _ruta(mensajes) -> Ruta:
    ultima = next(m.content for m in reversed(mensajes) if m.type == "human").lower()
    agente = next((a for p, a in PALABRAS_RUTA.items() if p in ultima), "general")
    return Ruta(agente=agente)


class FakeLLM(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        humanos = [m.content for m in messages if m.type == "human"]
        texto = f"[{len(humanos)}] {humanos[-1]}"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=texto))])

    def bind_tools(self, tools, **kwargs):
        return self  # nunca pide tools: el subagente termina en un paso

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(_ruta)


@pytest.fixture
def db_path():
    return "data" / "test.sqlite.db"


@pytest.fixture
def cliente(monkeypatch, db_path):
    monkeypatch.setattr("src.agent.obtener_llm", lambda: FakeLLM())
    monkeypatch.setattr(main, "saver_persistente", SqliteSaver(sqlite3.connect(db_path, check_same_thread=False)))
    with TestClient(main.app) as c:
        yield c


def _snapshot(cliente, thread_id):
    grafo = cliente.app.state.grafos["persistente"]
    return grafo.get_state({"configurable": {"thread_id": thread_id}})


def test_hilo_por_email_mantiene_ruta_y_llega_a_end(cliente):
    email = "ana@empresa.com"
    turnos = [
        ("hola", "general"),
        ("hay stock de denim azul?", "datos"),
        ("y el cuit del cliente Lopez?", "fiscal"),
    ]
    thread_ids = set()

    for i, (pregunta, ruta_esperada) in enumerate(turnos, start=1):
        r = cliente.post(f"{API_VERSION}/query-memory", json={"pregunta": pregunta, "email": email})
        assert r.status_code == 200, r.text
        body = r.json()
        thread_ids.add(body["thread_id"])

        assert body["memoria"] == "persistente"
        assert body["respuesta"] == f"[{i}] {pregunta}"  # el LLM vio los i turnos del hilo

        snap = _snapshot(cliente, body["thread_id"])
        assert snap.values["ruta"] == ruta_esperada
        assert snap.next == ()  # el grafo llego a END, no quedo un nodo pendiente

    assert thread_ids == {main.generar_thread_id(email.lower())}

    estado = cliente.get(f"{API_VERSION}/state", params={"email": email}).json()
    assert estado["total"] == 2 * len(turnos)
    assert [m["rol"] for m in estado["mensajes"]] == ["usuario", "asistente"] * len(turnos)


def test_thread_id_tiene_prioridad_sobre_email(cliente):
    primero = cliente.post(f"{API_VERSION}/query-memory", json={"pregunta": "hola"}).json()
    segundo = cliente.post(
        f"{API_VERSION}/query-memory",
        json={"pregunta": "sigo", "thread_id": primero["thread_id"], "email": "otro@empresa.com"},
    ).json()

    assert segundo["thread_id"] == primero["thread_id"]
    assert segundo["respuesta"] == "[2] sigo"


def test_hilo_sobrevive_reinicio_de_la_app(monkeypatch, db_path):
    monkeypatch.setattr("src.agent.obtener_llm", lambda: FakeLLM())
    email = "persistente@empresa.com"

    for pregunta, esperado in [("hola", "[1] hola"), ("sigo aca", "[2] sigo aca")]:
        # Saver y app nuevos en cada vuelta: solo comparten el archivo SQLite.
        monkeypatch.setattr(main, "saver_persistente", SqliteSaver(sqlite3.connect(db_path, check_same_thread=False)))
        with TestClient(main.app) as c:
            r = c.post(f"{API_VERSION}/query-memory", json={"pregunta": pregunta, "email": email})
        assert r.json()["respuesta"] == esperado


def test_hilos_distintos_no_se_mezclan(cliente):
    cliente.post(f"{API_VERSION}/query-memory", json={"pregunta": "hola", "email": "a@empresa.com"})
    r = cliente.post(f"{API_VERSION}/query-memory", json={"pregunta": "hola", "email": "b@empresa.com"})
    assert r.json()["respuesta"] == "[1] hola"
