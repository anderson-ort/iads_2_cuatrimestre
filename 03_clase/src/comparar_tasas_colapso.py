"""
Re-ejecuta el lote de 15 mensajes de la Clase 2 (lote_stress_semantico.py)
contra el extractor validado con Google GenAI + Pydantic, y compara la tasa
de fallo contra reporte_contrato_roto.json.
"""

import json
import time

from extractor_validado import extraer_con_structured_outputs

# importar desde lote_stress_semantico.py (se pude usar tambien un archivo JSON )
from lote_stress_semantico import LOTE_MENSAJES


def ejecutar_lote_validado():
    resultados = []
    for caso in LOTE_MENSAJES:
        print(
            f"\n[{caso['id']:02d}] Falla esperada (Clase 2): {caso['tipo_falla_esperada']}"
        )

        resultado = extraer_con_structured_outputs(caso["mensaje"])
        resultado["id"] = caso["id"]
        resultado["tipo_falla_esperada_clase2"] = caso["tipo_falla_esperada"]

        fallo = resultado["colapso_proveedor"] or resultado["colapso_aplicacion"]
        print(
            f"  Colapso: {fallo}" + (f" -> {resultado['error']}" if fallo else " -> OK")
        )

        resultados.append(resultado)
        # Un pequeño delay estratégico para cuidar la cuota por minuto de la API gratuita
        time.sleep(2)

    with open("reporte_post_pydantic.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    return resultados


def comparar_con_clase2(resultados_nuevos: list):
    try:
        with open("reporte_contrato_roto.json", "r", encoding="utf-8") as f:
            resultados_viejos = json.load(f)
    except FileNotFoundError:
        print(
            "\nNo se encontro reporte_contrato_roto.json de la Clase 2. "
            "Sin ese archivo no se puede comparar tasas. Copialo a esta carpeta."
        )
        return

    total = len(resultados_nuevos)
    fallos_viejo = sum(
        1 for r in resultados_viejos if r["colapso"] or r["problemas_silenciosos"]
    )
    fallos_nuevo = sum(
        1
        for r in resultados_nuevos
        if r["colapso_proveedor"] or r["colapso_aplicacion"]
    )

    print("\n" + "-" * 60)
    print("COMPARACION DE TASAS DE COLAPSO (GEMINI ECOSYSTEM)")
    print("-" * 60)
    print(
        f"Clase 2 (json.loads() crudo):       {fallos_viejo}/{total} fallaron ({fallos_viejo / total * 100:.1f}%)"
    )
    print(
        f"Clase 3 (Gemini Structured Out):    {fallos_nuevo}/{total} fallaron ({fallos_nuevo / total * 100:.1f}%)"
    )

    reduccion = fallos_viejo - fallos_nuevo
    print(f"\nReduccion absoluta de casos fallidos: {reduccion}")

    if fallos_nuevo > 0:
        print("\nCasos que SIGUEN fallando incluso con Pydantic/Structured Outputs:")
        for r in resultados_nuevos:
            if r["colapso_proveedor"] or r["colapso_aplicacion"]:
                print(
                    f"  [{r['id']:02d}] {r['tipo_falla_esperada_clase2']}: {r['error']}"
                )


if __name__ == "__main__":
    resultados_nuevos = ejecutar_lote_validado()
    comparar_con_clase2(resultados_nuevos)
