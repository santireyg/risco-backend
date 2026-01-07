# ------------------------------------------------------------------------------------
# PROMPTS AI REPORT - Prompts para generación de reportes de IA
# ------------------------------------------------------------------------------------
"""
Prompts utilizados en la generación de reportes de análisis de riesgo con IA.
"""

PROMPT_INSTRUCCIONES = """
Realiza un reporte de análisis de riesgo para una empresa de seguros de caución, utilizando estos datos: los valores de sus estados contables, la información del BCRA (incluyendo el estado de deudas y si existen cheques rechazados), y cualquier otro dato relevante proporcionado. El objetivo es orientar la toma de decisiones sobre riesgos asociados a la empresa.
Enfócate en razonar el análisis, cruzando los distintos datos de manera lógica y fundamentando cada observación antes de llegar a las conclusiones. Explica tus pasos analíticos primero (por ejemplo: interpretación de estados contables, análisis de la situación de deuda, evaluación de antecedentes de pagos), antes de avanzar a cualquier síntesis o recomendación. Solo al final expón las conclusiones y aspectos clave.

# Instrucciones específicas
- El reporte debe estar en formato Markdown.
- Inicio: realiza el análisis descriptivo en párrafos breves, siguiendo este orden lógico:
1. Explica cómo analizas los estados contables y qué observas a partir de ellos.
2. Reseña la información del BCRA sobre deudas y cheques rechazados y su posible impacto.
3. Relaciona los diferentes datos encontrados (análisis cruzado) y extrae inferencias lógicas.
4. Solo después, presenta un resumen ejecutivo (máx. 400 palabras), priorizando un enfoque cualitativo y orientado a la toma de decisiones. Si usas indicadores, solo para reforzar teorías o conclusiones. Si usas bullets, que sean max. 4. El usuario ya conoce los indicadores.
- Luego incluye una sección titulada **Key Insights**, con ítems concretos: separa entre "Puntos fuertes", "Alertas" y "Alarmas" (cada uno en un renglón o dos, máximo). Haz listas breves con insights accionables, útiles para el analista decisor.
- Mantén un tono profesional, directo y enfocado en la utilidad para la toma de decisión. Evita explicaciones innecesarias sobre metodología.
- Si algún dato clave del EECC falta, señala cómo podría influir en la evaluación de riesgo.
- Si cheques rechazados está vacío, es porque no los hay.

# Formato de salida
- El output debe ser un documento en formato Markdown, dentro de un JSON.
- El análisis debe ser en español.
- Primer bloque: análisis razonado (no mas de 600 palabras). Estilo: "Analizo el...".
- Segundo bloque: resumen ejecutivo (no más de 400 palabras).
- Tercer bloque: Key Insights, dividido en Puntos Fuertes, Alertas, Alarmas (bullets, renglón breve).
- No utilices más de dos niveles de jerarquía de títulos.
- Inicia el reporte directamente, omite títulos del estilo "Reporte de análisis de riesgo" o "Empresa Construir SA" o semejantes.

# Recordatorio
El objetivo es guiar al usuario en la toma de decisión respecto al riesgo, a partir de un análisis razonado y estructurado de los datos brindados, con conclusiones claras y útiles, y una sección de Key Insights concreta y accionable.
"""
