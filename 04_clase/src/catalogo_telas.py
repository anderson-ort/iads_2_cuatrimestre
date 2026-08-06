"""
Catalogo Tecnico de Ortelana Textil - Clase 4
15 fichas tecnicas con variedad conceptual deliberada, para forzar el
exito de la busqueda vectorial sobre los sinonimos que usan los clientes
reales (jerga, nombres comerciales, usos en lugar de nombres tecnicos).
"""

CATALOGO_ORTELANA = [
    "Ficha Tecnica - Denim 12 oz: Tela pesada compuesta por 100% algodon, "
    "armada en sarga de alta resistencia. Ideal para pantalones de trabajo "
    "pesados, camperas de invierno rigidas y ropa de seguridad industrial. "
    "Stock critico en Planta Central.",
    "Ficha Tecnica - Jersey de Algodon Premium: Tejido de punto liviano y "
    "extremadamente suave. Composicion 30/1 peinado, ideal para remeras de "
    "primera linea, indumentaria urbana de alta calidad y ropa infantil. "
    "Requiere lavado delicado.",
    "Ficha Tecnica - Gabardina Elastizada: Tela versatil compuesta por 97% "
    "algodon y 3% elastano. Ofrece excelente flexibilidad para pantalones de "
    "vestir, uniformes corporativos modernos y bermudas. Resistencia media a "
    "la traccion.",
    "Ficha Tecnica - Lona Cobertora Impermeable: Tejido sintetico recubierto "
    "con PVC. Totalmente impermeable, disenado para toldos comerciales, "
    "cerramientos exteriores y fundas de maquinaria pesada. Cero "
    "elasticidad, maxima proteccion climatica.",
    "Ficha Tecnica - Seda Natural Pura: Fibra animal de origen 100% natural, "
    "tacto sedoso y caida fluida. Utilizada en vestidos de gala, blusas de "
    "alta costura y pañuelos de lujo. Requiere lavado en seco exclusivamente.",
    "Ficha Tecnica - Friza Polar Antipilling: Tejido sintetico de "
    "poliester con pelo bilateral. Excelente retencion de calor corporal, "
    "usado en buzos de abrigo, pijamas de invierno y mantas polares. "
    "Tratamiento antipilling de fabrica.",
    "Ficha Tecnica - Lino Belga 100%: Fibra vegetal de textura irregular y "
    "transpirable. Ideal para camisas de verano, vestidos frescos y ropa de "
    "playa premium. Tiende a arrugarse con el uso, caracteristica deseada "
    "en la prenda final.",
    "Ficha Tecnica - Cuero Ecologico PU: Material sintetico con texturizado "
    "que imita cuero natural. Usado en camperas urbanas, carteras y "
    "tapizados de sillones modernos. Resistente al agua, no transpirable.",
    "Ficha Tecnica - Tul Bordado para Novias: Tejido de red fina con bordado "
    "floral aplicado. Usado exclusivamente en velos de novia, vestidos de "
    "quince anios y disenios de alta costura. Extremadamente delicado, "
    "requiere manipulacion especializada.",
    "Ficha Tecnica - Algodon Pima Egipcio: Fibra de algodon de hebra extra "
    "larga, suavidad superior al algodon comun. Utilizado en sabanas "
    "premium, camisas de vestir de lujo y ropa interior de alta gama.",
    "Ficha Tecnica - Neopreno Textil 3mm: Material sintetico esponjoso con "
    "alta elasticidad multidireccional. Usado en trajes de neoprene "
    "deportivos, fajas de compresion y accesorios de fitness.",
    "Ficha Tecnica - Microfibra Deportiva Dry-Fit: Tejido sintetico de "
    "secado rapido con tecnologia de absorcion de humedad. Ideal para "
    "remeras deportivas, ropa de gimnasio y uniformes de equipos.",
    "Ficha Tecnica - Pana Acanalada Gruesa: Tejido de algodon con relieve "
    "longitudinal pronunciado. Usada en pantalones de vestir informal, "
    "camperas de otonio y tapizados de sillas vintage.",
    "Ficha Tecnica - Toalla de Rizo Americano: Tejido de algodon con bucles "
    "absorbentes en ambas caras. Usado en toallones de bano, batas y "
    "productos de higiene textil para el hogar.",
    "Ficha Tecnica - Tafeta Brillante Sintetica: Tejido liviano de "
    "poliester con acabado brillante y caida rigida. Usado en disfraces, "
    "decoracion de eventos y forros de prendas de fiesta.",
]


if __name__ == "__main__":
    print(f"Catalogo cargado: {len(CATALOGO_ORTELANA)} fichas tecnicas.")
    for i, ficha in enumerate(CATALOGO_ORTELANA):
        titulo = ficha.split(":")[0]
        print(f"  [{i:02d}] {titulo}")
