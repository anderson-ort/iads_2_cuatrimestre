import json
from typing import Optional

from chroma_repository import OrtelanaCatalogRepository


class OrtelanaCatalogService:
    """
    Servicio de alto nivel que coordina la lógica del negocio.
    Aquí se inyecta el repositorio OrtelanaCatalogRepository.
    """

    def __init__(self, repository: OrtelanaCatalogRepository):
        self.repository = repository

    def cargar_catalogo_desde_archivo(self, path_json: str):
        """
        Lee el catálogo limpio y guarda en la base de datos sólo los nuevos registros.
        """
        with open(path_json, "r", encoding="utf-8") as f:
            catalogo = json.load(f)

        ids_existentes = self.repository.get_existing_ids()
        nuevos = [r for r in catalogo if r["id"] not in ids_existentes]

        if not nuevos:
            print(
                f"El catálogo ya está actualizado. Total: {self.repository.count()} registros."
            )
            return

        self.repository.create_or_upsert_batch(
            ids=[r["id"] for r in nuevos],
            documents=[r["descripcion_semantica"] for r in nuevos],
            metadatas=[r["metadatos"] for r in nuevos],
        )
        print(
            f"Cargados {len(nuevos)} registros nuevos. Total en base de datos: {self.repository.count()}"
        )

    def actualizar_stock_por_evento(self, id_tela: str, nuevo_estado_stock: bool):
        """
        Simula el evento de negocio donde cambia el stock de una tela específica.
        """
        try:
            self.repository.update_metadata_fields(
                id_tela, {"en_stock": nuevo_estado_stock}
            )
            print(
                f"Evento procesado: Stock de '{id_tela}' actualizado a en_stock={nuevo_estado_stock}."
            )
        except ValueError as e:
            print(f"Error procesando evento: {e}")

    def buscar_telas_para_vendedores(
        self,
        query_semantica: str,
        filtro_sucursal: Optional[str] = None,
        solo_con_stock: bool = True,
        n_results: int = 2,
    ) -> dict:
        """
        Realiza la búsqueda híbrida traduciendo parámetros de negocio
        a filtros de persistencia (where clauses).
        """
        condiciones = []
        where = {}

        if filtro_sucursal:
            condiciones.append({"sucursal_disponible": {"$eq": filtro_sucursal}})
        if solo_con_stock:
            condiciones.append({"en_stock": {"$eq": True}})

        if len(condiciones) == 1:
            where = condiciones[0]
        elif len(condiciones) > 1:
            where = {"$and": condiciones}

        return self.repository.query_hybrid(
            query_text=query_semantica, where_filter=where, n_results=n_results
        )
