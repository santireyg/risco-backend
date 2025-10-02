# app/tenants/default/prompts.py
"""
Prompts personalizados para el tenant DEFAULT.
Estos son los prompts actuales del sistema migrados desde app/utils/prompts.py.
"""

PROMPT_EXTRACT_BALANCE = """
INSTRUCCIONES (LEER TODO ANTES DE EMPEZAR)

Tarea
------
Vas a extraer información de un Estado de Situación Patrimonial (Balance General). Debes devolver **exclusivamente** un JSON con la estructura definida en “Formato de salida”. No incluyas texto adicional, explicaciones ni comentarios.

Alcance
-------
1) Extrae **todos** los renglones con importes de los cuadros de Activo, Pasivo y Patrimonio Neto.
2) Conserva **exactamente** la terminología del documento (incluye “(Nota X)”/“(Anexo X)” cuando se muestren).
3) Si un renglón es un prefijo de otro, usa el nombre completo más informativo (puedes concatenar de forma inteligente) para que no queden conceptos truncos.
4) **No** listes resúmenes que combinen Pasivo y Patrimonio (p.ej. “Total pasivo y patrimonio neto”).
5) Si una misma partida aparece en varias páginas, **no la dupliques**: quédate con la versión más detallada/reciente dentro del documento.

Normalización de montos
-----------------------
- Los valores con “-” o entre paréntesis se interpretan como **negativos**.
- Detecta si el informe indica unidades (“en miles”, “en millones”, etc.). **Escala** todos los importes al valor absoluto real.
- Quita separadores de miles y convierte comas/puntos según el formato local del documento.
- Los importes deben ser **números** (no strings), en la misma moneda del documento (no incluyas el símbolo).
- Si falta un período anterior, usa `0` para montos anteriores y `null` para `periodo_anterior`.

Identificación de períodos y empresa
------------------------------------
- `periodo_actual` y `periodo_anterior` deben estar en formato `YYYY-MM-DD`.
- Si el documento sólo da mes/año, usa el último día de ese mes (p.ej. “Marzo 2024” → `2024-03-31`).
- Extrae `empresa` si aparece (razón social, encabezado, pie de página, tapa).

Categorización para resultados_principales
------------------------------------------
Debes calcular estos agregados (sin duplicar partidas):

- **disponibilidades**: caja, bancos, equivalentes de efectivo y colocaciones a muy corto plazo (p.ej., fondos money market) **no restringidas**. Excluir inventarios, créditos comerciales, inversiones de largo plazo.
- **bienes_de_cambio**: existencias/inventarios vinculados al giro del negocio (mercaderías, materias primas, productos en proceso/terminados, ganado para venta, etc.). 
  - Considera la actividad de la empresa: si es industrial, MP/PP/PT suelen ser bienes de cambio; si es inmobiliaria, “Propiedades para la venta” también; si es agrícola, “Granos a comercializar” o similares; si es petrolera, “Crudo/derivados” inventarios, etc.
- **activo_corriente**, **activo_no_corriente**, **activo_total**
- **pasivo_corriente**, **pasivo_no_corriente**, **pasivo_total**
- **patrimonio_neto**

Reglas adicionales para "detalles_*"
------------------------------------
- En **"detalles_*"**, **jamás** sumes ni restes partidas; sólo vuelca lo que figura en el balance tal como figura.
- Si un renglón funciona como prefijo de otro, usa el **nombre completo** más informativo (puedes concatenar de forma inteligente). No consideres como prefijo los títulos como "Pasivo", "Pasivo corriente", "Activo", "Activo no corriente", o semejantes.
Ejemplo:
`PATRIMONIO NETO
(Según estado respectivo)`
pasa a --> `(PATRIMONIO NETO - Según estado respectivo)`

Orden de extracción y deduplicación
-----------------------------------
1) Detecta la sección (Activo/Pasivo/Patrimonio Neto) y el sub-bloque (Corriente/No corriente) si existe.
2) Extrae filas con importe para período actual y anterior.
3) Normaliza signos/escala.
4) Agrega a `detalles_*` en el orden de aparición.
5) Calcula `resultados_principales`.
6) Elimina duplicados exactos, y evita incluir “Total pasivo y patrimonio neto”.

Formato de salida (JSON)
------------------------
Debes responder **sólo** con un JSON que cumpla este formato exacto (sin claves extra, sin comentarios):

{
  "informacion_general": {
    "empresa": "Nombre de la empresa o null",
    "periodo_actual": "YYYY-MM-DD",
    "periodo_anterior": "YYYY-MM-DD" | null
  },
  "resultados_principales": [
    {
      "concepto_code": "disponibilidades",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "bienes_de_cambio",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "activo_corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "activo_no_corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "activo_total",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "pasivo_corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "pasivo_no_corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "pasivo_total",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "patrimonio_neto",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ],
  "detalles_activo": [
    {
      "concepto": "Nombre del concepto",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ],
  "detalles_pasivo": [
    {
      "concepto": "Nombre del concepto",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ],
  "detalles_patrimonio_neto": [
    {
      "concepto": "Nombre del concepto",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ]
}

Validaciones antes de responder
-------------------------------
- El JSON debe ser válido y parseable.
- `concepto_code` en snake_case y del conjunto definido (no inventes otros).
- No repitas partidas ni en `detalles_*` ni en `resultados_principales`.
- Todos los importes son números; si no hay dato del período anterior, usa 0.
- Respeta los signos: “( )” o “-” → negativo.
- Garantiza que estas devolviendo sólo el JSON.

En caso de duda
---------------
- Prefiere **no duplicar** valores y mantén la terminología textual del documento.
- Si algo no aparece, deja el campo en `null` (empresa/fecha) o `0` (montos anteriores).

ENTRADA
-------
Se te proveerán imágenes con el Balance.

SALIDA
------
Responde **sólo** con el JSON final (sin prosa adicional).

- IMPORTANTÍSIMO!!!: Si el documento declara unidades (“miles/millones”), verifica que los importes ya estén escalados (agrega 000 o 000000, según corresponda).
"""

PROMPT_EXTRACT_INCOME = """
INSTRUCCIONES (LEER TODO ANTES DE EMPEZAR)

Tarea
------
Vas a extraer información de un Estado de Resultados (Estado de Resultado Integral, si aplica). Debes devolver **exclusivamente** un JSON con la estructura definida en “Formato de salida”. No incluyas texto adicional, explicaciones ni comentarios.

Alcance
-------
1) Extrae **todos** los renglones con importes que aparezcan en el cuadro de Estado de Resultados (operaciones continuadas y discontinuadas, si las hay).
2) Conserva **exactamente** la terminología del documento e incluye referencias a notas/anexos cuando figuren (p.ej., “Resultados financieros (Nota 5)”).
3) Si un renglón funciona como prefijo de otro, usa el **nombre completo** más informativo (puedes concatenar de forma inteligente) para evitar conceptos truncos.
4) Si una misma partida aparece en más de una página, **no la dupliques**: prioriza la versión más adecuada dentro del documento.

Normalización de montos
-----------------------
- “-” o paréntesis “( )” ⇒ **negativo**.
- Detecta unidades (“en miles”, “en millones”) y **escala** todos los importes al valor real total.
- Uniforma separadores (quita puntos de miles; usa punto como decimal).
- Todos los importes deben ser **números** (no strings), en la moneda del documento (sin símbolo).
- Si falta un período anterior, usa `0` en montos anteriores y `null` en `periodo_anterior`.

Identificación de períodos y empresa
------------------------------------
- Devuelve `periodo_actual` y `periodo_anterior` en formato `YYYY-MM-DD`.
- Si sólo hay mes/año, usa el último día de ese mes (“Marzo 2024” → `2024-03-31`).
- Extrae `empresa` si aparece (encabezado, pie, carátula).

Criterios para "resultados_principales"
---------------------------------------
Debes completar estos tres agregados, sin duplicar partidas:

1) **ingresos_por_venta**:
   - Incluye ventas de bienes, ingresos por servicios, ingresos operativos del giro (p. ej., “Ventas netas”, “Ingresos por prestación de servicios”, “Ingresos por alquileres operativos” si es el giro).

2) **resultados_antes_de_impuestos** (EBT):
   - Si el cuadro muestra explícitamente “Resultado antes de impuesto a las ganancias” (o equivalente), toma ese valor.
   - Si no está explícito, calcula: **Resultado operativo** ± **Resultados financieros** ± **Resultados por tenencia/RECPAM** ± **Resultados de asociadas/joint ventures** ± **Otros resultados**, **antes** del impuesto a las ganancias.

3) **resultados_del_ejercicio** (resultado neto):
   - Prefiere “Resultado del período/ejercicio” atribuible a la entidad. 

Reglas adicionales para "detalles_estado_resultados"
----------------------------------------------------
- Si el informe presenta subtotales (p.ej., “Resultado bruto”, “Resultado operativo/EBIT”), inclúyelos en `detalles_estado_resultados` tal como aparecen.
- En **"detalles_estado_resultados"**, **jamás** sumes ni restes partidas; sólo vuelca lo que figura en el cuadro tal como figura.
- Si un renglón funciona como prefijo de otro, usa el **nombre completo** más informativo (puedes concatenar de forma inteligente).
Ejemplo:
`Gastos
Ventas y distribución`
pasa a --> `Gastos - Ventas y distribución`

Orden de extracción y deduplicación
-----------------------------------
1) Detecta secciones (continuadas/discontinuadas) y el orden natural del cuadro.
2) Extrae filas con importes para período actual y anterior.
3) Normaliza signos y escala.
4) Llena `detalles_estado_resultados` en el **mismo orden** de aparición.
5) Calcula `resultados_principales`.
6) Verifica ausencia de duplicados entre páginas/segmentos.

Formato de salida (JSON)
------------------------
Responde **sólo** con un JSON que cumpla este formato exacto (sin claves extra, sin comentarios):

{
  "informacion_general": {
    "empresa": "Nombre de la empresa o null",
    "periodo_actual": "YYYY-MM-DD",
    "periodo_anterior": "YYYY-MM-DD" | null
  },
  "resultados_principales": [
    {
      "concepto_code": "ingresos_por_venta",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "resultados_antes_de_impuestos",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "resultados_del_ejercicio",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ],
  "detalles_estado_resultados": [
    {
      "concepto": "Nombre del concepto",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ]
}

Validaciones antes de responder
-------------------------------
- El JSON resultante debe ser **válido y parseable**.
- `concepto_code` en **snake_case** y del conjunto definido (no inventes otros).
- Todos los importes son **numéricos**; si no hay dato del período anterior, usa 0.
- Signos correctos: “-” o “( )” ⇒ negativo.
- No repitas información si aparece en más de una página.
- Garantiza que estas devolviendo sólo el JSON.

ENTRADA
-------
Se te proveerán imágenes o PDF con el Estado de Resultados.

SALIDA
------
Responde **sólo** con el JSON final (sin prosa adicional).


- IMPORTANTÍSIMO!!!: Unidades escaladas (“miles/millones”) verificadas (agrega 000 o 000000, según corresponda).

"""
