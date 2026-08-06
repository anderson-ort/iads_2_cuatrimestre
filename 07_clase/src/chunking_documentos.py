"""
Chunking con solapamiento para documentos largos de Ortelana.
Complementa el catalogo de telas (Clase 5) con los documentos de politicas
de onboarding, que son multi-parrafo y requieren solapamiento para no romper
frases criticas en los limites de chunk.
"""

from itertools import chain

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_wrapper import GeminiEmbeddingsLangchain

# Documentos de politicas de onboarding de Ortelana (los mismos que aparecen
# en 04_clase.md como BASE_CONOCIMIENTO_ORTELANA, ahora con texto completo)
DOCUMENTOS_POLITICAS = [
    {
        "id": "POL-001",
        "titulo": "Habilitacion de Cuenta Mayorista - Condiciones Generales",
        "texto": (
            "Para habilitar una cuenta mayorista en Ortelana Textil, el distribuidor "
            "debe cumplir con los siguientes requisitos de forma acumulativa. "
            "Primero, condicion fiscal: el distribuidor debe estar inscripto en AFIP "
            "con condicion de Responsable Inscripto o Monotributista categoria D o "
            "superior. Los monotributistas en categorias inferiores a D pueden solicitar "
            "revision especial ante el area comercial, adjuntando documentacion que "
            "acredite volumen de ventas mensual superior a $500.000. "
            "Segundo, antiguedad del negocio: la empresa o actividad debe contar con "
            "una antiguedad minima de 6 meses a partir de la fecha de inscripcion en "
            "AFIP. Emprendimientos nuevos con menos de 6 meses de actividad pueden "
            "solicitar ingreso al programa de distribuidores en formacion, con "
            "condiciones comerciales diferenciadas. "
            "Tercero, rubro comercial: se aceptan distribuidores de los rubros listados "
            "en el Anexo A. Rubros no listados requieren evaluacion del area comercial "
            "con un plazo de hasta 5 dias habiles para la respuesta."
        ),
        "metadatos": {
            "tipo": "politica",
            "categoria": "habilitacion",
            "version": "2024-03",
        },
    },
    {
        "id": "POL-002",
        "titulo": "Condiciones de Pago y Cuenta Corriente",
        "texto": (
            "Las condiciones de pago para distribuidores nuevos de Ortelana Textil "
            "se establecen de la siguiente manera. Las primeras tres operaciones de "
            "un nuevo distribuidor mayorista son estrictamente al contado o con "
            "transferencia previa al despacho de la mercaderia. No se aceptan cheques "
            "diferidos ni ordenes de compra corporativas en esta etapa inicial. "
            "A partir de la cuarta operacion, y sujeto a historial de pago sin "
            "incidentes, el distribuidor puede solicitar habilitacion de cuenta "
            "corriente con plazo de 15 dias. La solicitud debe presentarse por escrito "
            "al area de creditos con los ultimos 3 estados de cuenta bancarios. "
            "El monto maximo de la cuenta corriente para distribuidores nuevos es de "
            "$500.000 pesos. Este limite puede revisarse a los 6 meses de operacion "
            "continua sin incidentes de pago, mediante solicitud formal al area comercial. "
            "Los distribuidores con referencias verificables de otros proveedores textiles "
            "pueden solicitar cuenta corriente desde la segunda operacion, adjuntando "
            "cartas de referencia en papel membretado."
        ),
        "metadatos": {
            "tipo": "politica",
            "categoria": "comercial",
            "version": "2024-02",
        },
    },
    {
        "id": "POL-003",
        "titulo": "Criterios de Revision Manual y Escalamiento",
        "texto": (
            "El sistema automatizado de onboarding de Ortelana Textil deriva a revision "
            "manual del equipo de administracion los siguientes casos. Primero, "
            "monotributistas en categoria C o inferior: estas solicitudes no pueden ser "
            "aprobadas de forma automatica porque el volumen de facturacion declarado "
            "puede no ser suficiente para sostener el pedido minimo. El equipo de "
            "administracion tiene 48 horas habiles para resolver. "
            "Segundo, empresas con menos de 6 meses de antiguedad que demuestren "
            "volumen de ventas comprobable: se acepta documentacion alternativa como "
            "extractos de plataformas de e-commerce o certificados de otros proveedores. "
            "Tercero, distribuidores de rubros no listados explicitamente en el Anexo A: "
            "por ejemplo, jugueterias con seccion de disfraces, o tiendas de decoracion "
            "que venden textiles para el hogar de forma secundaria. "
            "Cuarto, clientes con CUIT previamente rechazado que solicitan reconsideracion: "
            "deben adjuntar documentacion que acredite la resolucion del motivo de rechazo "
            "original. El plazo de revision en este caso es de 72 horas habiles."
        ),
        "metadatos": {"tipo": "politica", "categoria": "proceso", "version": "2024-03"},
    },
]


def _chunkear_documento(
    doc: dict, splitter: RecursiveCharacterTextSplitter
) -> list[dict]:
    """
    Divide un documento en fragmentos usando el splitter proporcionado.
    """

    fragmentos = splitter.split_text(doc["texto"])
    total = len(fragmentos)
    return [
        {
            "id": f"{doc['id']}-chunk-{i:02d}",
            "texto": fragmento,
            "metadatos": {
                **doc["metadatos"],
                "doc_origen": doc["id"],
                "titulo_origen": doc["titulo"],
                "chunk_index": i,
                "total_chunks": total,
            },
        }
        for i, fragmento in enumerate(fragmentos)
    ]


def chunkear_documentos(
    documentos: list[dict],
    chunk_size: int = 400,
    chunk_overlap: int = 80,
) -> list[dict]:
    """
    Divide los documentos largos en chunks con solapamiento.
    El solapamiento del 20% (80/400) garantiza que frases criticas que
    caen en el limite de un chunk aparezcan completas en al menos uno.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return list(
        chain.from_iterable(_chunkear_documento(doc, splitter) for doc in documentos)
    )


def indexar_politicas_en_chroma(chunks: list[dict]):
    """
    Indexa los chunks de politicas en la misma coleccion de ChromaDB
    que ya tiene el catalogo de telas de la Clase 5.
    Usa upsert para no duplicar si se corre mas de una vez.
    """
    embeddings = GeminiEmbeddingsLangchain()

    vectorstore = Chroma(
        collection_name="catalogo_telas",
        embedding_function=embeddings,
        persist_directory="./ortelana_vector_db",
    )

    ids_existentes = set(vectorstore._collection.get(include=[])["ids"])
    nuevos = [c for c in chunks if c["id"] not in ids_existentes]

    if not nuevos:
        print(f"Todos los chunks ya estaban indexados ({len(chunks)} total).")
        return vectorstore

    vectorstore._collection.upsert(
        ids=[c["id"] for c in nuevos],
        documents=[c["texto"] for c in nuevos],
        metadatas=[c["metadatos"] for c in nuevos],
    )
    print(f"Indexados {len(nuevos)} chunks nuevos de politicas.")
    print(f"Total en coleccion: {vectorstore._collection.count()} registros.")
    return vectorstore


if __name__ == "__main__":
    chunks = chunkear_documentos(DOCUMENTOS_POLITICAS)

    print(f"Documentos originales: {len(DOCUMENTOS_POLITICAS)}")
    print(f"Chunks generados: {len(chunks)}\n")

    for chunk in chunks:
        print(
            f"  [{chunk['id']}] {len(chunk['texto'])} chars | "
            f"chunk {chunk['metadatos']['chunk_index'] + 1}/"
            f"{chunk['metadatos']['total_chunks']}"
        )

    indexar_politicas_en_chroma(chunks)
