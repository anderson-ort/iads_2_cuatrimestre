# Clase 7: RAG Avanzado y Stress Queries

## Objetivo de la sesion

Diagnosticar las debilidades del pipeline RAG construido en la Clase 6 usando Stress Queries como instrumento formal de evaluacion adversarial, e implementar tres tecnicas de mejora concretas: chunking con solapamiento, reranking post-recuperacion, y compresion contextual. Al terminar esta clase, el pipeline va a resistir los cuatro tipos de ataque que describe el material de lectura.

## Herramientas a usar

- `langchain.text_splitter.RecursiveCharacterTextSplitter` (chunking con solapamiento)
- `sentence-transformers` CrossEncoder multilingue (reranking)
- `langchain.retrievers.ContextualCompressionRetriever` + `LLMChainExtractor` (compresion)
- `langchain-google-genai` `ChatGoogleGenerativeAI` (el mismo LLM de la Clase 6)
- `EmbeddingFunctionGemini` y `GeminiEmbeddingsLangchain` de las Clases 5 y 6
- LangSmith (trazabilidad de las corridas comparativas)

---

## El Eslabon del Proyecto (Entregable Asincrono)

### Contexto: por que la Clase 6 no alcanza

El `rag_chain.py` de la Clase 6 recupera documentos completos de ChromaDB. Las fichas tecnicas del catalogo de Ortelana son cortas (un parrafo por tela), pero los documentos reales de onboarding (reglamentos, politicas de credito, criterios de revision manual) tienen secciones interrelacionadas que un chunking ingenuo rompe en lugares inconvenientes. El material de lectura de esta clase describe exactamente ese escenario como "Stress por Fragmentacion o Multi-hop": la respuesta no esta en un solo fragmento y el retriever simple no la encuentra.

Antes de mejorar el pipeline, vas a medir cuanto falla el que tenes. Esa medicion es el punto de partida cuantitativo de esta clase, y la evidencia que justifica cada tecnica que vas a implementar.

---

### Parte 1 - Diagnostico: las cuatro categorias de Stress Query sobre tu RAG

Construis el dataset de diagnostico aplicando las cuatro categorias del material de lectura al dominio real de Ortelana. Estas no son preguntas de ejercicio: son los casos que tu sistema va a encontrar en produccion.


[stress_queries_dataset.py](src/stress_queries_dataset.py)


#### Ejercicio para el alumno

Ejecuta este script para confirmar que el dataset carga sin errores, y despues corre manualmente cada pregunta contra tu `chain_con_fuentes` de la Clase 6. Para cada una, registra en una tabla:

| ID     | Categoria              | El RAG basico resistio? | Fallo observado |
| ------ | ---------------------- | ----------------------- | --------------- |
| SQ-001 | out_of_scope           | ?                       | ?               |
| SQ-002 | multi_hop              | ?                       | ?               |
| SQ-003 | contradiccion_temporal | ?                       | ?               |
| SQ-004 | prompt_injection       | ?                       | ?               |

Estos cuatro resultados son tu linea de base. Al final de la clase, volveras a correr el mismo dataset contra el RAG avanzado para comparar.



### Parte 2 - Chunking con solapamiento para documentos largos

El catalogo de telas de la Clase 5 tiene fichas cortas (un parrafo). Pero el
sistema de onboarding de Ortelana tambien maneja documentos largos: el reglamento
de distribuidores, las politicas de credito, los criterios de revision manual.
Esta parte indexa esos documentos con chunking robusto.

```bash
pip install langchain langchain-google-genai langchain-chroma sentence-transformers
```

```python
# chunking_documentos.py
"""
Chunking con solapamiento para documentos largos de Ortelana.
Complementa el catalogo de telas (Clase 5) con los documentos de politicas
de onboarding, que son multi-parrafo y requieren solapamiento para no romper
frases criticas en los limites de chunk.
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter

# Chroma y GeminiEmbeddingsLangchain ya NO se importan aqui.
# indexar_politicas_en_chroma usa OrtelanaCatalogRepository (interfaz ChromaDB)
# directamente, no el Retriever de LangChain. Cada capa usa su contrato correcto.

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
        "metadatos": {"tipo": "politica", "categoria": "habilitacion", "version": "2024-03"}
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
        "metadatos": {"tipo": "politica", "categoria": "comercial", "version": "2024-02"}
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
        "metadatos": {"tipo": "politica", "categoria": "proceso", "version": "2024-03"}
    },
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

    chunks_resultado = []
    for doc in documentos:
        fragmentos = splitter.split_text(doc["texto"])
        for i, fragmento in enumerate(fragmentos):
            chunks_resultado.append({
                "id": f"{doc['id']}-chunk-{i:02d}",
                "texto": fragmento,
                "metadatos": {
                    **doc["metadatos"],
                    "doc_origen": doc["id"],
                    "titulo_origen": doc["titulo"],
                    "chunk_index": i,
                    "total_chunks": len(fragmentos),
                }
            })

    return chunks_resultado


def indexar_politicas_en_chroma(chunks: list[dict]):
    """
    Indexa los chunks de politicas en ChromaDB reutilizando
    OrtelanaCatalogRepository de la Clase 5.

    Por que este diseno y no Chroma/_collection directamente:

    1. _collection es API privada de ChromaDB: puede cambiar entre versiones
       sin aviso. El Repository encapsula esa superficie de riesgo en un
       unico punto del codigo.

    2. El Repository ya expone get_existing_ids(), create_or_upsert_batch()
       y count(), exactamente las tres operaciones que necesita esta funcion.
       No hay razon para reimplementarlas.

    3. EmbeddingFunctionGemini (interfaz chromadb.EmbeddingFunction) es la
       funcion correcta para el Repository. GeminiEmbeddingsLangchain
       (interfaz langchain_core.embeddings.Embeddings) es para el Retriever
       de LangChain. Son dos contratos distintos sobre la misma API de Gemini:
       mezclarlos en el mismo objeto genera confusion de responsabilidades.
       Cada capa usa su propio contrato.
    """
    from utils.embedding_function import EmbeddingFunctionGemini
    from utils.chroma_repository import OrtelanaCatalogRepository

    # task_type=RETRIEVAL_DOCUMENT: los chunks de politicas son documentos
    # a indexar, no consultas. Consistente con como se indexo el catalogo
    # de telas en la Clase 5.
    fn_embedding = EmbeddingFunctionGemini(task_type="RETRIEVAL_DOCUMENT")
    repository = OrtelanaCatalogRepository(embedding_function=fn_embedding)

    ids_existentes = repository.get_existing_ids()
    nuevos = [c for c in chunks if c["id"] not in ids_existentes]

    if not nuevos:
        print(f"Todos los chunks ya estaban indexados ({len(chunks)} total).")
        return repository

    repository.create_or_upsert_batch(
        ids=[c["id"] for c in nuevos],
        documents=[c["texto"] for c in nuevos],
        metadatas=[c["metadatos"] for c in nuevos],
    )
    print(f"Indexados {len(nuevos)} chunks nuevos de politicas.")
    print(f"Total en coleccion: {repository.count()} registros.")
    return repository


if __name__ == "__main__":
    chunks = chunkear_documentos(DOCUMENTOS_POLITICAS)

    print(f"Documentos originales: {len(DOCUMENTOS_POLITICAS)}")
    print(f"Chunks generados: {len(chunks)}\n")

    for chunk in chunks:
        print(f"  [{chunk['id']}] {len(chunk['texto'])} chars | "
              f"chunk {chunk['metadatos']['chunk_index']+1}/"
              f"{chunk['metadatos']['total_chunks']}")

    indexar_politicas_en_chroma(chunks)
```

#### Ejercicio para el alumno

1. Ejecuta el script y compara `Documentos originales` vs `Chunks generados`.
   Confirma que POL-002 (el mas largo) genera mas chunks que POL-001.

2. Cambia `chunk_overlap=80` a `chunk_overlap=0` y vuelve a correr
   (con IDs distintos para no pisar los existentes). Busca en ChromaDB
   la frase "a partir de la cuarta operacion" con ambas versiones.
   Con solapamiento, esa frase aparece completa en algun chunk aunque
   caiga en el limite. Sin solapamiento, puede quedar cortada.
   Documenta el resultado: eso es la demostracion empirica del problema
   que el solapamiento resuelve.

3. El parametro `add_start_index=True` agrega la posicion del chunk
   dentro del documento original como metadato. Imprime ese metadato
   para los chunks de POL-002 y explicá para que sirve ese dato
   si quisies recuperar el parrafo anterior o siguiente a un resultado.

---

### Parte 3 - Reranking post-recuperacion

El reranking es la segunda etapa del retriever: primero recuperas 10 candidatos
por similitud vectorial (rapido pero impreciso), despues un CrossEncoder los
reordena por relevancia especifica a la consulta (lento pero preciso).
El CrossEncoder no usa embeddings: lee el par (consulta, documento) completo
y da un score de relevancia directa.

```python
# reranker.py
"""
Reranking con CrossEncoder multilingue para el pipeline RAG de Ortelana.
Dos etapas:
  1. Recuperacion amplia con ChromaDB (n_candidatos=10, rapido)
  2. Reordenamiento con CrossEncoder (n_finales=3, preciso)
"""

from sentence_transformers import CrossEncoder
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_wrapper import GeminiEmbeddingsLangchain

MODELO_RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class RerankerOrtelana:
    """
    Retriever de dos etapas con CrossEncoder multilingue.
    Se integra como reemplazo del retriever MMR de la Clase 6.
    """

    def __init__(
        self,
        vectorstore: Chroma,
        n_candidatos: int = 10,
        n_finales: int = 3,
    ):
        self.vectorstore = vectorstore
        self.n_candidatos = n_candidatos
        self.n_finales = n_finales
        self._reranker = CrossEncoder(MODELO_RERANKER)

    def recuperar(self, consulta: str) -> list[Document]:
        # Etapa 1: recuperacion amplia por similitud vectorial
        candidatos = self.vectorstore.similarity_search(
            consulta, k=self.n_candidatos
        )

        if not candidatos:
            return []

        # Etapa 2: reranking con CrossEncoder
        pares = [(consulta, doc.page_content) for doc in candidatos]
        scores = self._reranker.predict(pares)

        candidatos_con_score = sorted(
            zip(candidatos, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        return [doc for doc, _ in candidatos_con_score[:self.n_finales]]

    # Interfaz compatible con el retriever de LangChain para usarlo en LCEL
    def invoke(self, consulta: str) -> list[Document]:
        return self.recuperar(consulta)

    def get_relevant_documents(self, consulta: str) -> list[Document]:
        return self.recuperar(consulta)


def construir_reranker() -> RerankerOrtelana:
    embeddings = GeminiEmbeddingsLangchain()
    vectorstore = Chroma(
        collection_name="catalogo_telas",
        embedding_function=embeddings,
        persist_directory="./ortelana_vector_db",
    )
    return RerankerOrtelana(vectorstore)


if __name__ == "__main__":
    reranker = construir_reranker()

    consulta = (
        "distribuidor monotributista categoria B con 8 meses de antiguedad, "
        "requisitos habilitacion cuenta mayorista"
    )

    print(f"Consulta: {consulta}\n")
    resultados = reranker.recuperar(consulta)

    for i, doc in enumerate(resultados, 1):
        print(f"Resultado {i} (post-reranking):")
        print(f"  {doc.page_content[:120]}...")
        print(f"  Metadatos: {doc.metadata}\n")
```

#### Ejercicio para el alumno

1. Ejecuta `reranker.py` con la consulta del monotributista categoria B.
   Anota cuales 3 documentos quedaron en el top despues del reranking.

2. Modifica temporalmente el script para imprimir los 10 candidatos
   iniciales (antes del reranking) con sus scores de similitud vectorial,
   y los 3 finales (despues del reranking) con sus scores de CrossEncoder.
   Compara el orden: el ranking cambio? El documento que quedo primero
   despues del reranking era el primero antes? Si cambio, explica en una
   frase por que el CrossEncoder puede diferir del ranking vectorial.

3. Esta consulta del monotributista es el caso SQ-002 en el dataset de
   stress (multi-hop). Despues de hacer el reranking, vuelve a correr
   esa stress query contra el pipeline actualizado y completa la columna
   correspondiente de tu tabla de diagnostico.

---

### Parte 4 - Compresion contextual

El retriever de la Clase 6 pasaba documentos enteros al LLM. Si una ficha
tecnica tiene 5 parrafos y solo 1 es relevante para la consulta, los otros 4
consumen tokens sin aportar precision. La compresion contextual resuelve eso:
recupera documentos completos y despues extrae solo los fragmentos relevantes.

```python
# rag_avanzado.py
"""
Pipeline RAG avanzado de Ortelana - Clase 7.
Integra reranking + compresion contextual sobre el chain_rag de la Clase 6.
Produce respuestas mas precisas con menos tokens consumidos.
"""

import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_wrapper import GeminiEmbeddingsLangchain
from reranker import RerankerOrtelana

load_dotenv()

# --- COMPONENTES (iguales a Clase 6, excepto el retriever) ---

embeddings = GeminiEmbeddingsLangchain()

vectorstore = Chroma(
    collection_name="catalogo_telas",
    embedding_function=embeddings,
    persist_directory="./ortelana_vector_db",
)

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODELO_LLM", "gemini-2.0-flash-lite"),
    temperature=0,
)

# --- RETRIEVER AVANZADO: reranking + compresion ---

# Paso 1: el reranker de dos etapas reemplaza el retriever MMR de la Clase 6
reranker = RerankerOrtelana(vectorstore, n_candidatos=10, n_finales=4)

# Paso 2: el compresor extrae solo los fragmentos relevantes de cada documento
# Esto resuelve el problema de documentos largos que el reranking solo
# recupera pero no filtra internamente.
compressor = LLMChainExtractor.from_llm(llm)

retriever_avanzado = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=reranker,
)

# --- PROMPT (mismo que Clase 6, sin cambios: los guardrails ya funcionan) ---

PROMPT_RAG = ChatPromptTemplate.from_template("""
Sos el Asistente de Ventas por WhatsApp de Ortelana Textil.
Tu objetivo es responder a las consultas de los clientes basandote UNICAMENTE
en los fragmentos de nuestro catalogo provistos abajo.

REGLAS ESTRICTAS (GUARDRAILS):
1. Si la respuesta no puede deducirse DIRECTAMENTE del contexto, responde:
   "No poseo informacion oficial sobre esa solicitud".
2. Queda terminantemente PROHIBIDO confirmar descuentos, promociones,
   convenios verbales o precios que no esten explicitamente escritos
   en el contexto. No asumas nada.
3. Si el cliente menciona una ciudad o provincia, usa tu conocimiento
   geografico para identificar cual es la sucursal de Ortelana mas cercana
   SEGUN LO QUE FIGURE en el contexto. No inventes sucursales.

Contexto del catalogo:
{context}

Pregunta del cliente: {question}

Respuesta de WhatsApp (tono cordial, una o dos oraciones):
""")


def formatear_contexto(docs: list[Document]) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


# --- CADENA AVANZADA ---

chain_avanzado = (
    {"context": retriever_avanzado | formatear_contexto, "question": RunnablePassthrough()}
    | PROMPT_RAG
    | llm
    | StrOutputParser()
)

chain_avanzado_con_fuentes = RunnableParallel(
    respuesta=chain_avanzado,
    fuentes=retriever_avanzado,
)


if __name__ == "__main__":
    # La misma consulta del cliente de Salta que fallaba en la Clase 5 y
    # mejoro en la Clase 6. Con reranking + compresion deberia ser mas precisa.
    pregunta = (
        "Necesito retapizar un sillon pero tengo dos gatos que lo destruyen "
        "todo, que me recomiendan? Vivo en Salta."
    )

    print(f"Cliente: {pregunta}\n")
    resultado = chain_avanzado_con_fuentes.invoke(pregunta)

    print(f"Ortelana Bot: {resultado['respuesta']}")
    print("\nFuentes usadas (post-compresion):")
    for doc in resultado["fuentes"]:
        print(f"  -> {doc.page_content[:80]}...")
        print(f"     Metadatos: {doc.metadata}")
```

#### Ejercicio para el alumno

1. Ejecuta `rag_avanzado.py` con la consulta de Salta y compara la respuesta
   con la que generaba `rag_chain.py` de la Clase 6. Anota las diferencias
   en precision y en los documentos que se usaron como fuente.

2. Activa el tracing de LangSmith agregando estas tres lineas al inicio
   del script (despues de `load_dotenv()`):

```python
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = "ortelana-clase7"
```

   Corre la misma consulta y abre LangSmith. Verifica que podes ver:
   cuantos candidatos recupero el reranker antes de comprimir, cuanto
   texto le llego al LLM despues de la compresion, y cuantos tokens
   consumio la cadena completa vs la version sin compresion.

---

### Parte 5 - Tabla comparativa final: RAG basico vs RAG avanzado

Este es el entregable cierre de la clase, equivalente a la tabla de
comparacion de calidad que pide el `07_clase.md`:

```python
# comparacion_rag.py
"""
Comparacion sistematica entre el RAG basico (Clase 6) y el RAG avanzado
(Clase 7) sobre el dataset de Stress Queries.
Genera la tabla de evidencia para el TP1.
"""

from rag_chain import chain_con_fuentes as chain_basico
from rag_avanzado import chain_avanzado_con_fuentes as chain_avanzado
from stress_queries_dataset import STRESS_QUERIES


def evaluar_query(chain, pregunta: str) -> dict:
    resultado = chain.invoke(pregunta)
    fuentes = resultado.get("fuentes", [])
    return {
        "respuesta": resultado["respuesta"],
        "n_fuentes": len(fuentes),
        "fuentes_ids": [
            doc.metadata.get("doc_origen", doc.metadata.get("id", "?"))
            for doc in fuentes
        ],
    }


if __name__ == "__main__":
    print("=== Comparacion RAG Basico vs RAG Avanzado ===\n")

    for sq in STRESS_QUERIES:
        print(f"{'='*70}")
        print(f"[{sq['id']}] {sq['categoria'].upper()}")
        print(f"Pregunta: {sq['pregunta'][:80]}...\n")

        r_basico = evaluar_query(chain_basico, sq["pregunta"])
        r_avanzado = evaluar_query(chain_avanzado, sq["pregunta"])

        print(f"RAG BASICO  ({r_basico['n_fuentes']} fuentes): "
              f"{r_basico['respuesta'][:100]}...")
        print(f"RAG AVANZADO ({r_avanzado['n_fuentes']} fuentes): "
              f"{r_avanzado['respuesta'][:100]}...")
        print()
```

#### Ejercicio para el alumno

1. Ejecuta `comparacion_rag.py` y completa la tabla de diagnostico
   que iniciaste en la Parte 1 con la columna del RAG avanzado:

```markdown
| ID | Categoria | RAG basico resistio? | RAG avanzado resistio? | Que cambio |
|---|---|---|---|---|
| SQ-001 | out_of_scope | ? | ? | ? |
| SQ-002 | multi_hop | ? | ? | ? |
| SQ-003 | contradiccion_temporal | ? | ? | ? |
| SQ-004 | prompt_injection | ? | ? | ? |
```

2. Para la categoria `contradiccion_temporal` (SQ-003): el reranking y
   la compresion mejoran la recuperacion del fragmento correcto, pero
   el problema de fondo es que el metadato `en_stock` no siempre aparece
   en el texto del documento recuperado. Propone en una frase como
   modificarias el `formatear_contexto()` para que el LLM siempre vea
   el estado de stock explicitamente en el contexto, independientemente
   de si aparece en el texto de la descripcion.

---

## Resultado Esperado

Al cierre de esta clase, tu proyecto tiene:

- Un dataset formal de 4 Stress Queries (`stress_queries_dataset.py`)
  con las cuatro categorias del material de lectura, adaptadas al dominio
  real de Ortelana. Este dataset se reutiliza en la Clase 8 como base
  del set de evaluacion de RAGAS.

- Los documentos de politicas de onboarding indexados en ChromaDB con
  chunking de solapamiento del 20% (`chunking_documentos.py`), listos
  para ser recuperados en los escenarios de multi-hop.

- Un `RerankerOrtelana` de dos etapas que reemplaza el retriever MMR
  de la Clase 6, con interfaz compatible con LCEL (`reranker.py`).

- Un pipeline RAG avanzado (`rag_avanzado.py`) que combina reranking
  + compresion contextual y produce respuestas mas precisas con menos
  tokens, verificable en LangSmith.

- Una tabla comparativa con evidencia empirica de cuando el RAG avanzado
  mejora sobre el basico y cuando no (el SQ-004 de prompt injection
  deberia resistir igual en ambos, porque ese guardrail esta en el prompt,
  no en el retriever).

La Clase 8 toma este dataset de Stress Queries y lo convierte en un set
de evaluacion formal con RAGAS, midiendo las tres metricas de la Triada RAG
que menciona el material de lectura: Context Relevance, Groundedness,
y Answer Relevance.
