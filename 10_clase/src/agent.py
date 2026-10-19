"""LangGraph con router y subagentes especializados (create_agent).

START -> router -> fiscal  (buscar_datos_internos + consultar_cuit)
                -> datos   (buscar_datos_internos)
                -> web     (buscar_web + buscar_datos_internos)
                -> general (sin tools)
                      -> END
"""
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, wrap_model_call
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from src.config import contexto, obtener_llm, recortar
from src.schemas import Ruta
from src.tools import buscar_datos_internos, buscar_web, consultar_cuit

@wrap_model_call
def ventana(request: ModelRequest, handler):
    """Recorta solo lo que ve el LLM; el historial completo queda en el checkpointer."""
    return handler(request.override(messages=recortar(request.messages)))


def crear_agente(herramientas: list, prompt: str, nombre: str, checkpointer: BaseCheckpointSaver | None = None):
    """Agente ReAct ya armado: modelo, nodo de tools, aristas condicionales y bucle."""
    return create_agent(
        model=obtener_llm(),
        tools=herramientas,
        system_prompt=prompt,
        middleware=[ventana],
        checkpointer=checkpointer,
        name=nombre,
    )


class Estado(MessagesState):
    ruta: str

PROMPT_ROUTER = (
    "Elegi que agente debe responder la ultima solicitud:\n"
    "- fiscal: datos fiscales o impositivos de un cliente o CUIT (razon social, condicion impositiva, "
    "domicilio fiscal, actividad, estado)\n"
    "- datos: catalogo de telas, precios, stock por sucursal, pedidos y su seguimiento, credito de clientes, "
    "politicas de devolucion, envio y distribuidores\n"
    "- web: informacion externa o actual de internet, y consultas sobre insumos o proyectos "
    "(que telas conviene usar para una prenda o trabajo y si las tenemos disponibles)\n"
    "- general: saludos o preguntas que no requieren herramientas"
)




def crear_orquestador(checkpointer: BaseCheckpointSaver | None = None):
    llm = obtener_llm()
    router = llm.with_structured_output(Ruta)
    ctx = contexto()

    # Los subagentes no llevan checkpointer: la memoria la maneja el grafo padre.
    subagentes = {
        "fiscal": crear_agente(
            [buscar_datos_internos, consultar_cuit],
            f"{ctx}\nSos el especialista fiscal. Si te dan el nombre de un cliente y no su CUIT, "
            "buscalo primero en los datos internos (seccion clientes) y despues consulta el CUIT.",
            nombre="fiscal",
        ),
        "datos": crear_agente(
            [buscar_datos_internos],
            f"{ctx}\nSos el especialista en datos internos: catalogo, stock, clientes, pedidos y politicas. "
            "Para precios usa precio_final_ars. Para devoluciones compara la fecha de entrega con hoy.",
            nombre="datos",
        ),
        "web": crear_agente(
            [buscar_web, buscar_datos_internos],
            f"{ctx}\nSos el especialista en consultas externas y en proyectos o insumos. "
            "Para informacion externa o actual usa buscar_web. "
            "Para un proyecto (por ejemplo, que telas conviene usar para una prenda): "
            "1) usa buscar_web para saber que tipo de tela es adecuada; "
            "2) usa buscar_datos_internos con seccion 'productos' y busca por categoria, una por vez "
            "(categorias del catalogo: gabardinas, linos, punto, denim); "
            "3) responde que telas del catalogo sirven, con precio_final_ars y stock por sucursal, "
            "e indica claramente cuales no tienen stock. No recomiendes telas que no esten en el catalogo.",
            nombre="web",
        ),
    }

    def nodo_router(estado: Estado) -> dict:
        ruta = router.invoke([SystemMessage(content=PROMPT_ROUTER), *recortar(estado["messages"])])
        return {"ruta": ruta.agente}

    def nodo_general(estado: Estado) -> dict:
        return {"messages": [llm.invoke([SystemMessage(content=ctx), *recortar(estado["messages"])])]}

    def nodo_subagente(nombre: str):
        def _nodo(estado: Estado) -> dict:
            resultado = subagentes[nombre].invoke({"messages": estado["messages"]})
            return {"messages": [resultado["messages"][-1]]}

        return _nodo

    grafo = StateGraph(Estado)
    grafo.add_node("router", nodo_router)
    grafo.add_node("general", nodo_general)
    for nombre in subagentes:
        grafo.add_node(nombre, nodo_subagente(nombre))

    grafo.add_edge(START, "router")
    grafo.add_conditional_edges("router", lambda e: e["ruta"], ["fiscal", "datos", "web", "general"])
    for nodo in (*subagentes, "general"):
        grafo.add_edge(nodo, END)

    return grafo.compile(checkpointer=checkpointer)

