"""
Auditoria de catalogos heterogeneos - Clase 5, Bloque 1.
Detecta las tres metricas de control de calidad que pide el PDF:

1. Discrepancia estructural (llaves distintas)
2. Tipificacion erronea (booleanos como strings)
3. Colision semantica de tags (distinta jerga para el mismo concepto)

Usa como insumo real tu propio archivo clase_5_pre-telas.json, que
emplea "tags_regionales", mientras que el catalogo de la Clase 4
usaba "tags". Ese es tu primer hallazgo de auditoria.

NO un error a tapar.
"""

import json

LLAVES_ESPERADAS_RAIZ = {"id", "descripcion_semantica", "metadatos"}
LLAVES_ESPERADAS_METADATOS = {"linea_textil", "sucursal_disponible", "en_stock", "tags"}


class Hallazgo:
    def __init__(self, llaves_esperadas_raiz: set, llaves_esperadas_metadatos: set):
        """
        Inicializa las reglas y estructuras esperadas de la auditoría.
        """
        self.llaves_esperadas_raiz = llaves_esperadas_raiz
        self.llaves_esperadas_metadatos = llaves_esperadas_metadatos

    def registro_treatment(self, registro: dict) -> dict:
        """
        Procesa un único registro y devuelve las discrepancias encontradas
        """
        discrepancia = None
        variante_tag = None
        tipificacion_erronea = None

        # 1. Validar llaves raíz (Simplificado calculando diferencias de conjuntos directamente)
        llaves_raiz = set(registro.keys())
        faltantes = self.llaves_esperadas_raiz - llaves_raiz
        extras = llaves_raiz - self.llaves_esperadas_raiz
        
        if faltantes or extras:
            discrepancia = {
                "id": registro.get("id", "SIN_ID"),
                "faltantes": list(faltantes),
                "extras": list(extras),
            }

        # 2. Validar tags vs tags_regionales (Colisión semántica)
        metadatos = registro.get("metadatos", {})
        
        if "tags" not in metadatos and "tags_regionales" in metadatos:
            variante_tag = "tags_regionales (en vez de 'tags')"
        
        elif "tags" in metadatos:
            variante_tag = "tags (nombre esperado)"

        # 3. Validar tipificación de en_stock
        en_stock = metadatos.get("en_stock")
        
        if isinstance(en_stock, str):
            tipificacion_erronea = {
                "id": registro.get("id", "SIN_ID"),
                "campo": "en_stock",
                "valor_recibido": en_stock,
                "tipo_recibido": "str",
                "tipo_esperado": "bool",
            }

        return {
            "discrepancia": discrepancia,
            "variante_tag": variante_tag,
            "tipificacion_erronea": tipificacion_erronea
        }

    def __call__(self, path_json: str, nombre_taller: str) -> dict:
        """
        Lee el archivo JSON especificado, ejecuta la auditoría
        sobre cada registro del catálogo y devuelve el reporte final consolidado.
        """
        with open(path_json, "r", encoding="utf-8") as f:
            catalogo = json.load(f)

        discrepancias = []
        tipificaciones = []
        variantes_tags = set()

        for registro in catalogo:
            resultado = self.registro_treatment(registro)
            
            # Recolectamos los hallazgos solo si fueron detectados en este registro
            if resultado["discrepancia"]:
                discrepancias.append(resultado["discrepancia"])
            
            if resultado["variante_tag"]:
                variantes_tags.add(resultado["variante_tag"])
                
            if resultado["tipificacion_erronea"]:
                tipificaciones.append(resultado["tipificacion_erronea"])

        return {
            "taller": nombre_taller,
            "total_registros": len(catalogo),
            "discrepancias_estructurales": discrepancias,
            "tipificaciones_erroneas": tipificaciones,
            "variantes_de_tags_detectadas": list(variantes_tags),
        }


if __name__ == "__main__":
    # Instanciamos la clase Hallazgo con las llaves que esperamos
    auditor = Hallazgo(LLAVES_ESPERADAS_RAIZ, LLAVES_ESPERADAS_METADATOS)

    # Ejecutamos la auditoría llamando directamente a la instancia
    reporte = auditor("clase_5_pre-telas.json", nombre_taller="Taller_Propio")

    print(json.dumps(reporte, ensure_ascii=False, indent=2))

    if reporte["discrepancias_estructurales"] or reporte["variantes_de_tags_detectadas"]:
        print("\nCONCLUSION: tu propio catalogo tiene al menos una discrepancia "
              "estructural respecto a la especificacion de la Clase 4. Esto es "
              "exactamente el escenario que la Clase 5 pide auditar.")