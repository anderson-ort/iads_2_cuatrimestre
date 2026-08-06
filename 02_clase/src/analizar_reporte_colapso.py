"""
Laboratorio "El Contrato Roto" - Clase 2
Lee reporte_contrato_roto.json y genera las metricas que el alumno
debe exponer al inicio de la Clase 3.
"""

import json
from collections import Counter


def generar_metricas(path_reporte: str = "reporte_contrato_roto.json") -> dict:
    with open(path_reporte, "r", encoding="utf-8") as f:
        resultados = json.load(f)

    total = len(resultados)
    colapsos_duros = [r for r in resultados if r["colapso"]]
    con_problemas_silenciosos = [r for r in resultados if r["problemas_silenciosos"]]
    casos_limpios = [
        r for r in resultados if not r["colapso"] and not r["problemas_silenciosos"]
    ]

    tipos_de_error = Counter(r["tipo_error"] for r in colapsos_duros if r["tipo_error"])

    metricas = {
        "total_casos": total,
        "colapsos_duros_json_invalido": len(colapsos_duros),
        "casos_con_problemas_silenciosos": len(con_problemas_silenciosos),
        "casos_completamente_limpios": len(casos_limpios),
        "tasa_de_colapso_duro_pct": round(len(colapsos_duros) / total * 100, 1),
        "tasa_de_fallo_total_pct": round(
            (len(colapsos_duros) + len(con_problemas_silenciosos)) / total * 100, 1
        ),
        "distribucion_tipos_de_error": dict(tipos_de_error),
    }

    return metricas


if __name__ == "__main__":
    metricas = generar_metricas()

    print("--- REPORTE DE TASA DE COLAPSO - Clase 2 ---\n")
    for clave, valor in metricas.items():
        print(f"{clave}: {valor}")

    print(
        "\nConclusion esperada: el prompt engineering puro, sin Pydantic ni "
        "validacion estructural, NO garantiza un contrato de datos confiable "
        "en produccion. Esta cifra es el punto de partida cuantitativo de la Clase 3."
    )
