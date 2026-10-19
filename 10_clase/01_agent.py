"""Agente con LangChain (LCEL).

Cadena LCEL (prompt | llm con tools) + bucle que ejecuta las tools pedidas.
La memoria es la lista de mensajes que se le pasa a ejecutar().
"""
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import MAX_PASOS, contexto, obtener_llm, recortar
from src.tools import HERRAMIENTAS, TOOLS_POR_NOMBRE

PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "{contexto}\n"
     "Herramientas: buscar_datos_internos (catalogo, stock, clientes, pedidos y politicas), "
     "consultar_cuit (datos fiscales en Supabase) y buscar_web (informacion externa). "
     "Si te piden datos fiscales de un cliente por nombre, busca primero su CUIT en los datos internos. "
     "Para devoluciones compara la fecha de entrega con hoy."),
    MessagesPlaceholder("messages"),
])


def crear_agente_simple():
    """Cadena LCEL: prompt | llm con las 3 tools enlazadas."""
    return PROMPT | obtener_llm().bind_tools(HERRAMIENTAS)


def ejecutar(
    cadena, pregunta: str, historial: list[BaseMessage] | None = None
) -> tuple[str, list[BaseMessage]]:
    """Bucle ReAct manual: llama a la cadena, ejecuta las tools pedidas y repite."""
    mensajes = [*(historial or []), HumanMessage(content=pregunta)]

    for _ in range(MAX_PASOS):
        ia = cadena.invoke({"contexto": contexto(), "messages": recortar(mensajes)})
        mensajes.append(ia)

        if not ia.tool_calls:  # el modelo ya tiene la respuesta final
            return ia.content, mensajes

        for llamada in ia.tool_calls:
            resultado = TOOLS_POR_NOMBRE[llamada["name"]].invoke(llamada["args"])
            mensajes.append(ToolMessage(content=str(resultado), tool_call_id=llamada["id"]))

    return "No pude resolver la consulta en el maximo de pasos.", mensajes


if __name__ == "__main__":
    cadena = crear_agente_simple()

    respuesta, historial = ejecutar(
        cadena, "Textiles Norpatagonia es distribuidor? Que domicilio fiscal tiene?"
    )
    print(respuesta)

    # Seguimiento: la memoria es la lista que se le pasa
    respuesta, historial = ejecutar(cadena, "Y cuanto stock de denim tienen en Cordoba?", historial)
    print(respuesta)
