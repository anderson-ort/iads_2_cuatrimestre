PREGUNTAS_DEMO = [
    # Una sola tool de base de datos.
    "¿Qué telas de la categoría linos tienen stock y cuál cuesta menos?",
    # Encadenamiento: necesita el id (buscar_productos) para luego consultar_stock.
    "¿Hay frisa invisible en Buenos Aires? Si no, ¿dónde hay?",
    # RAG como herramienta + dato transaccional (el ejemplo de agents.md).
    "Según la política de devoluciones, ¿puedo devolver el pedido PED-1003? Verificá su estado.",
    # Web search: información que NO está en la base.
    "¿Qué diferencia hay entre gabardina y denim como tejido? Buscalo en la web.",
    # Falta dato obligatorio: debería pedir el número de pedido, no inventarlo.
    "¿Ya despacharon mi pedido?",
]

CASOS = [
    {"pregunta": "¿Cuál es la gabardina más barata con stock?",
     "esperadas": {"buscar_productos"}, "prohibidas": {"buscar_web"}, "contiene": "elastizada"},
    {"pregunta": "¿Cuántos metros de lino natural hay en Córdoba?",
     "esperadas": {"consultar_stock"}, "prohibidas": {"buscar_web"}, "contiene": "12"},
    {"pregunta": "¿En qué estado está el pedido PED-1001 y con qué transportista va?",
     "esperadas": {"consultar_estado_pedido"}, "prohibidas": {"buscar_web"}, "contiene": "Andreani"},
    {"pregunta": "¿Desde cuántos metros el envío es gratis?",
     "esperadas": {"buscar_politica_interna"}, "prohibidas": {"buscar_web"}, "contiene": "50"},
    {"pregunta": "¿Qué es el gramaje de una tela? Buscá una definición en internet.",
     "esperadas": {"buscar_web"}, "prohibidas": {"consultar_stock"}, "contiene": None},
    # Caso negativo: no debe llamar a consultar_estado_pedido sin número.
    {"pregunta": "Quiero saber si llegó mi pedido.",
     "esperadas": set(), "prohibidas": {"consultar_estado_pedido", "crear_ticket_soporte"},
     "contiene": None},
]


EVAL_PREGUNTAS_DEMO = [
    "¿Qué telas de punto tienen descuento y cuánto queda en Córdoba?",
    "¿Qué requisitos tengo que cumplir para ser distribuidor?",
    "¿Cuáles son las tendencias en telas para la temporada primavera-verano?",
    "¿Quién ganó el último mundial de fútbol?",
    # Pregunta mixta: el router elige UN destino, así que una parte queda sin
    # responder. Es el límite de este patrón -> orquestador-trabajadores.
    "¿Cuánto cuesta el denim en OrTelana y cuánto lo cobra la competencia?",
]




