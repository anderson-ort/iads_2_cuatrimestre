import json

from utils.chroma_repository import OrtelanaCatalogRepository
from utils.chroma_service import OrtelanaCatalogService
from utils.embedding_function import EmbeddingFunctionGemini

if __name__ == "__main__":
    # Creamos el motor de embeddings (Infraestructura) ---
    fn_embedding = EmbeddingFunctionGemini()

    # Creamos el Repositorio de datos inyectando los embeddings ---
    repository = OrtelanaCatalogRepository(embedding_function=fn_embedding)

    # Creamos el Servicio inyectando el Repositorio ---
    service = OrtelanaCatalogService(repository=repository)

    # --- PRUEBAS DE FUNCIONAMIENTO ---

    # 1. Carga
    service.cargar_catalogo_desde_archivo("super_catalogo_ortelana_limpio.json")

    # 2. Búsqueda antes del evento
    print("\n=== Búsqueda híbrida: tela pesada en Buenos Aires con stock ===")
    resultados = service.buscar_telas_para_vendedores(
        query_semantica="Necesito una tela pesada para confeccionar camperas de trabajo",
        filtro_sucursal="central_buenos_aires",
        solo_con_stock=True,
    )
    print(json.dumps(resultados, ensure_ascii=False, indent=2))

    # 3. Mutación por evento
    print("\n Simulando evento de negocio: Buenos Aires se queda sin Denim")
    service.actualizar_stock_por_evento("G1-TELA-001", nuevo_estado_stock=False)

    # 4. Búsqueda después del evento
    print("\n Repitiendo la misma búsqueda post-evento")
    resultados_post = service.buscar_telas_para_vendedores(
        query_semantica="Necesito una tela pesada para confeccionar camperas de trabajo",
        filtro_sucursal="central_buenos_aires",
        solo_con_stock=True,
    )
    print(json.dumps(resultados_post, ensure_ascii=False, indent=2))
