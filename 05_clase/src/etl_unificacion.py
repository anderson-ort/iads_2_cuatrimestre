"""
ETL de unificacion de catalogos - Clase 5, Bloque 1, Paso 2.
Normaliza la llave de tags (tags_regionales -> tags), resuelve la
colision de IDs prefijando con el identificador del taller, y
construye el Super-Catalogo unificado de Ortelana.
"""

import json


def normalizar_registro(registro: dict, prefijo_taller: str) -> dict:
    """
    Aplica las correcciones de ETL a un registro individual:
    - Prefija el ID con el taller para evitar colisiones (TELA-001 -> G1-TELA-001)
    - Normaliza tags_regionales a tags
    - Coacciona en_stock de string a bool si vino mal tipado
    """
    nuevo = dict(registro)
    nuevo["id"] = f"{prefijo_taller}-{registro['id']}"

    metadatos = dict(registro.get("metadatos", {}))

    if "tags_regionales" in metadatos and "tags" not in metadatos:
        metadatos["tags"] = metadatos.pop("tags_regionales")

    if isinstance(metadatos.get("en_stock"), str):
        metadatos["en_stock"] = metadatos["en_stock"].strip().lower() == "true"

    nuevo["metadatos"] = metadatos
    return nuevo


def unificar_catalogos(paths_y_prefijos: list[tuple[str, str]]) -> list[dict]:
    """
    paths_y_prefijos: lista de (ruta_json, prefijo_taller), ej:
        [("clase_5_pre-telas.json", "G1"), ("taller_2.json", "G2")]
    """
    super_catalogo = []

    for path, prefijo in paths_y_prefijos:
        with open(path, "r", encoding="utf-8") as f:
            catalogo = json.load(f)

        for registro in catalogo:
            registro_normalizado = normalizar_registro(registro, prefijo)
            super_catalogo.append(registro_normalizado)

        print(f"  {path} (prefijo {prefijo}): {len(catalogo)} registros normalizados")

    return super_catalogo


if __name__ == "__main__":
    print("... ETL de Unificacion - Super-Catalogo Ortelana ...\n")

    #    Colocar la fuente o paths correctos
    fuentes = [
        ("clase_5_pre-telas.json", "G1"),
        # Descomentar cuando exista el segundo archivo del ejercicio anterior:
        # ("taller_2.json", "G2"),
    ]

    super_catalogo = unificar_catalogos(fuentes)

    ids = [r["id"] for r in super_catalogo]
    assert len(ids) == len(set(ids)), "Colision de IDs detectada despues del ETL!"

    with open("super_catalogo_ortelana.json", "w", encoding="utf-8") as f:
        json.dump(super_catalogo, f, ensure_ascii=False, indent=2)

    print(f"\nSuper-Catalogo unificado: {len(super_catalogo)} registros.")
    print("Guardado en super_catalogo_ortelana.json")
