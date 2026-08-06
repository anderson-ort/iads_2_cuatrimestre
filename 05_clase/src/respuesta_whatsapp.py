"""
Generador de respuestas de WhatsApp con logica condicional pura vs Servicio Semantico.
Objetivo pedagogico (segun el PDF): este script NO debe escalar bien.
La idea es chocar contra la pared de los condicionales antes de la
Clase 6, que introduce el LLM como "Sintetizador Semantico".
"""

from utils.chroma_repository import OrtelanaCatalogRepository
from utils.chroma_service import OrtelanaCatalogService
from utils.embedding_function import EmbeddingFunctionGemini

MENSAJES_DE_PRUEBA = [
    "Hola, tengo un casamiento en enero al mediodia y transpiro mucho, que llevo?",
    "Necesito retapizar un sillon pero tengo dos gatos que lo destruyen todo, que me recomiendan? Vivo en Salta.",
    "Busco algo con mucha caida, bien brillante para un vestido de noche, pero que sea lo mas barato posible.",
    "Quiero hacer delantales para un taller mecanico, se van a manchar con grasa todo el tiempo.",
    "Hola, busco seda natural. Me hacen descuento si llevo 50 metros?",
    "Soy alergica a los materiales sinteticos, necesito algo 100% transpirable para ropa de cama.",
]


def generar_respuesta_control_flujo(
    mensaje_cliente: str, service: OrtelanaCatalogService
) -> str:
    """
    ESTRATEGIA 1: Intento de mapeo manual con if/else antes de buscar.
    Demuestra la fragilidad de las palabras clave hardcodeadas.
    """
    mensaje_lower = mensaje_cliente.lower()

    # Intento 1: deteccion de palabras clave para armar una query semantica
    if (
        "casamiento" in mensaje_lower
        or "vestido de noche" in mensaje_lower
        or "gala" in mensaje_lower
    ):
        query = "tela elegante fresca para eventos"
    elif "sillon" in mensaje_lower or "tapizar" in mensaje_lower:
        query = "tela resistente para tapiceria"
    elif "delantal" in mensaje_lower or "taller mecanico" in mensaje_lower:
        query = "tela resistente a manchas e industrial"
    elif "ropa de cama" in mensaje_lower or "sintetico" in mensaje_lower:
        query = "tela natural transpirable"
    else:
        query = mensaje_cliente  # fallback: usar el mensaje crudo

    # Intento de detectar sucursal
    filtro_sucursal = None
    if "salta" in mensaje_lower:
        filtro_sucursal = "filial_salta"
    elif "cordoba" in mensaje_lower:
        filtro_sucursal = "filial_cordoba"
    elif "buenos aires" in mensaje_lower:
        filtro_sucursal = "central_buenos_aires"

    # Llamada al servicio usando la query "mutilada" por el if/else
    resultados = service.buscar_telas_para_vendedores(
        query_semantica=query,
        filtro_sucursal=filtro_sucursal,
        solo_con_stock=True,
        n_results=1,
    )

    documentos = resultados.get("documents", [[]])[0]
    if not documentos:
        return "Hola! Por el momento no encontramos una opcion exacta para tu consulta."

    return f"Hola! Te recomendamos: {documentos[0][:120]}..."


def generar_respuesta_usando_servicio(
    mensaje_cliente: str, service: OrtelanaCatalogService
) -> str:
    """
    ESTRATEGIA 2: Enfoque semántico puro delegando en el Servicio.
    Pasamos el mensaje crudo del cliente para que los Embeddings hagan su trabajo.
    """
    # Dejamos que ChromaDB entienda el contexto completo del mensaje sin ifs intermedios
    resultados = service.buscar_telas_para_vendedores(
        query_semantica=mensaje_cliente,
        filtro_sucursal=None,  # El servicio idealmente procesaría metadatos o busqueda general
        solo_con_stock=True,
        n_results=1,
    )

    documentos = resultados.get("documents", [[]])[0]
    if not documentos:
        return "Hola! No pudimos encontrar lo que buscás en nuestro catálogo actual."

    # Aquí se nota la pared de la clase 5: La búsqueda es excelente, pero
    # la respuesta sigue siendo un string hardcodeado, frío y robótico.
    return f"Hola! Según tu consulta, encontramos esto: {documentos[0][:120]}..."


def main():
    # Inicialización de la arquitectura según tu repositorio
    embedding_function = EmbeddingFunctionGemini(task_type="SEMANTIC_SIMILARITY")
    repo = OrtelanaCatalogRepository(embedding_function=embedding_function)
    service = OrtelanaCatalogService(repo)

    print("... Ejercicio de frustracion controlada: respuestas WhatsApp ...\n")

    for i, mensaje in enumerate(MENSAJES_DE_PRUEBA, 1):
        print(f"{'.' * 70}")
        print(f"Mensaje {i}: '{mensaje}'\n")

        # Lógica 1: Control de flujo manual
        r_control = generar_respuesta_control_flujo(mensaje, service)
        print(f"[CONTROL FLUJO] -> {r_control}")

        # Lógica 2: Uso directo del servicio semántico
        r_servicio = generar_respuesta_usando_servicio(mensaje, service)
        print(f"[PURE SERVICE]  -> {r_servicio}")
        print()


if __name__ == "__main__":
    main()
