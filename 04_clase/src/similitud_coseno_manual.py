"""
Traduccion a codigo del calculo manual del PDF de la Clase 4.
Eje X = Resistencia Industrial, Eje Y = Elasticidad/Suavidad.
Objetivo: validar empiricamente el resultado 0.965 antes de confiar
en la caja negra de FAISS o de cualquier proveedor de embeddings.
"""

import numpy as np


def similitud_coseno(vector_a: list[float], vector_b: list[float]) -> float:
    a = np.array(vector_a)
    b = np.array(vector_b)

    producto_escalar = np.dot(a, b)
    norma_a = np.linalg.norm(a)
    norma_b = np.linalg.norm(b)
    return producto_escalar / (norma_a * norma_b)


# Vector A: Lona de Alta Densidad (mucha resistencia, minima elasticidad)
VECTOR_LONA = [5, 1]

# Vector B: consulta del cliente "Busco lona rigida para toldos"
VECTOR_CONSULTA = [4, 2]

# Vector C: Seda Natural (poca resistencia, mucha elasticidad/suavidad),
# para mostrar el caso de BAJA similitud.
VECTOR_SEDA = [1, 5]


def ejecutar_demostracion():
    sim_lona_consulta = similitud_coseno(VECTOR_LONA, VECTOR_CONSULTA)
    sim_seda_consulta = similitud_coseno(VECTOR_SEDA, VECTOR_CONSULTA)

    print("=== Demostracion de Similitud Coseno (espacio simplificado 2D) ===\n")
    print(f"Vector A (Lona de Alta Densidad):     {VECTOR_LONA}")
    print(f"Vector B (Consulta 'lona para toldos'): {VECTOR_CONSULTA}")
    print(f"Vector C (Seda Natural):                {VECTOR_SEDA}")

    print(f"\nSimilitud Lona <-> Consulta:  {sim_lona_consulta:.4f}  (esperado ~0.965)")
    print(f"Similitud Seda <-> Consulta:  {sim_seda_consulta:.4f}  (deberia ser bajo)")

    assert abs(sim_lona_consulta - 0.965) < 0.001, (
        "El resultado no coincide con el del PDF"
    )
    print("\nValidacion OK: el resultado coincide con el calculo manual del PDF.")


if __name__ == "__main__":
    ejecutar_demostracion()
