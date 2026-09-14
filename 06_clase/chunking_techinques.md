El *chunking* consiste en dividir textos largos en fragmentos procesables para optimizar la precisión de la búsqueda vectorial y no saturar la ventana de contexto del LLM. Seleccionar la técnica adecuada depende del formato del documento, la complejidad semántica de los datos y el equilibrio entre costo y rendimiento.

| Técnica | Criterio de División | Cuándo Usarla |
| --- | --- | --- |
| **Fijo (Fixed-Size)** | Número exacto de caracteres o tokens. | Prototipos rápidos, textos muy homogéneos o baja capacidad de cómputo. |
| **Recursivo** | Jerarquía de separadores (`\n\n`, `\n`, espacio). | Textos generales, artículos, reportes y PDFs (es la opción por defecto). |
| **Estructural** | Sintaxis del documento (Markdown, HTML, Código). | Documentación técnica, páginas web e ingeniería de software. |
| **Semántico** | Variación en la similitud de embeddings entre oraciones. | Documentos donde los temas cambian drásticamente sin seguir párrafos rígidos. |
| **Agéntico** | Un LLM determina los puntos de corte o extrae proposiciones. | RAG de alta precisión donde el costo y la latencia no son restrictivos. |

---

**1. Chunking Fijo (Fixed-Size)**
División rígida basada en una cantidad fija de caracteres o tokens (ej. 500 caracteres con 50 de solapamiento).

* **Uso recomendado:** Pruebas de concepto iniciales o sistemas donde se requiere mínima latencia de procesamiento.
* **Limitación:** Corta oraciones o ideas por la mitad, destruyendo el contexto.

**2. Chunking Recursivo (Recursive Character)**
Intenta dividir secuencialmente por párrafos (`\n\n`); si el bloque supera el límite, intenta por líneas (`\n`), luego por espacios y finalmente por caracteres.

* **Uso recomendado:** El estándar general para la mayoría de aplicaciones RAG (manuales, libros, PDFs empresariales). Mantiene juntas las oraciones y párrafos siempre que sea posible.

**3. Chunking Estructurado (Document-Specific)**
Aprovecha los marcadores del formato original (encabezados `#`, `##` en Markdown, etiquetas `<div>` o `<article>` en HTML, o funciones mediante AST en Python/JS).

* **Uso recomendado:** Repositorios de código fuente, documentación oficial o contenido extraído de la web mediante *scraping*.

**4. Chunking Semántico**
Calcula la distancia semántica entre oraciones consecutivas mediante un modelo de embeddings. Inserta un corte cuando la diferencia entre una oración y la siguiente supera un umbral determinado.

* **Uso recomendado:** Textos complejos o investigaciones donde un mismo párrafo abarca múltiples conceptos desconectados.

**5. Chunking Agéntico / Basado en LLM**
Aplica un modelo de lenguaje para analizar la estructura semántica completa y dividir el texto en proposiciones lógicas e independientes.

* **Uso recomendado:** Casos de uso críticos (legal, médico, financiero) donde perder un detalle por mal fragmentado representa un riesgo alto.

**Recomendaciones de configuración**

* **Fragmentos Pequeños (128–300 tokens):** Ideales para búsqueda de datos puntuales (fechas, nombres, valores).
* **Fragmentos Grandes (500–1000+ tokens):** Necesarios para tareas que exigen sintetizar o comparar contextos amplios.
* **Solapamiento (*Overlap* de 10%–20%):** Evita perder información en las fronteras de los cortes entre un bloque y el siguiente.