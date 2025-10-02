# app/tenants/default/prompts.py
"""
Prompts personalizados para el tenant DEFAULT.
Estos son los prompts actuales del sistema migrados desde app/utils/prompts.py.
"""

PROMPT_EXTRACT_BALANCE = """
A continuación se encuentra un Estado de Situación Patrimonial (Balance), tu tarea es extraer la información solicitada. 
Debes detallar todos los registros que figuran en la tabla. 
Todos los montos deben ser extraidos con su correspondiente signo positivo o negativo. 
Los valores con "-" o con paréntesis deben ser extraidos como negativos.

En "detalles_activo", "detalles_pasivo" y "detalles_patrimonio" debes volcar todos y cada uno de los registros y calculos que están presentes en el correspondiente cuadro,
Los conceptos en detalles de P, A y PN deberán incluir, si las hubiera, las referencias a Notas/Anexos, -ej: "Inversiones (Nota 5)"-.
Sé inteligente al detectar y nombrar éstos conceptos, no todos los renglones son propiamente conceptos (algunas líneas pueden ser prefijos de otros conceptos, si así fuera puede que debas usar el prefijo para completar el nombre de estos conceptos de forma inteligente). Usa exactamente la termología que figura en el documento.

ACLARACIONES IMPORTANTES para "resultados_principales":
-> Para determinar "bienes_de_cambio" y "disponibilidades", 
considera qué actividad realiza la empresa y qué tipo de empresa es, ya que esto define qué montos corresponden a cada uno de estos conceptos. 

Responde en un JSON como el siguiente:
{
  "informacion_general": {
    "empresa": "Nombre de la empresa, si es que figura",
    "periodo_actual": "YYYY-MM-DD",
    "periodo_anterior": "YYYY-MM-DD"
    },
  "resultados_principales": [
    {
      "concepto_code": "disponibilidades",
      "concepto": "Disponibilidades o equivalentes",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "bienes_de_cambio",
      "concepto": "Bienes de cambio o equivalentes",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "activo_corriente",
      "concepto": "Activo corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "activo_no_corriente",
      "concepto": "Activo no corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "activo_total",
      "concepto": "Activo total",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "disponibilidades",
      "concepto": "Disponibilidades",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "bienes_de_cambio",
      "concepto": "Bienes de cambio",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "pasivo_corriente",
      "concepto": "Pasivo corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "pasivo_no_corriente",
      "concepto": "Pasivo no corriente",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "pasivo_total",
      "concepto": "Pasivo total",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "patrimonio_neto",
      "concepto": "Patrimonio neto",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ],
    "detalles_activo": [
      {
        "concepto": "Nombre del concepto",
        "monto_actual": 0,
        "monto_anterior": 0
      },
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
      },
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
      },
    ]
}
Los valores con "-" o con paréntesis deben ser extraidos como negativos.
Debes expresar los valores de los períodos en términos: ANUALES HASTA LA FECHA.
Si encuentras que una misma información esta en dos páginas distintas, no la repitas.
Si no encuentras datos de "perído anterior" en la imagen, puedes dejar los campos en 0, y "periodo_anterior" como None.

ATENCIÓN:
- En caso de que una cuenta sea "Total pasivo y patrimonio neto" (o un nombre análogo, que englobe ambos totales),
no la vuelques en "detalles_pasivo" ni en "detalles_patrimonio_neto", ya que es un resumen de ambos.
- Debes identificar si la página indica que los valores son "en miles" o "en millones", y, de ser así, ajustar los montos para que representen el valor real total.
- El campo "concepto_code" debe seguir el formato snake_case y ser consistente (ej: "disponibilidades", "bienes_de_cambio", "activo_total")
- El campo "concepto" es opcional y debe contener el nombre legible del concepto
"""
PROMPT_EXTRACT_INCOME = """
A continuación se encuentra un Estado de Resultados, tu tarea es extraer la información solicitada. 
Debes detallar todos los ingresos y gastos que figuran en la imagen. 
Todos los montos deben ser extraidos con su correspondiente signo positivo o negativo. 
Los valores con "-" o con paréntesis deben ser extraidos como negativos.

En "detalles_estado_resultados" debes volcar todos y cada uno de los registros y calculos que están presentes en el cuadro de Estado de Resultados.
Los conceptos en "detalles_estado_resultados" deberán incluir, si las hubiera, las referencias a Notas/Anexos, -ej: "Resultados financieros (Nota 5)"-.
Sé inteligente al detectar y nombrar éstos conceptos, no todos los renglones son propiamente conceptos (algunas líneas pueden ser prefijos de otros conceptos, si así fuera puede que debas usar el prefijo para completar el nombre de estos conceptos de forma inteligente). Usa exactamente la termología que figura en el documento.

Responde en un JSON como el siguiente:
{
  "informacion_general": {
    "empresa": "Nombre de la empresa, si es que figura",
    "periodo_actual": "YYYY-MM-DD",
    "periodo_anterior": "YYYY-MM-DD"
    },
  "resultados_principales": [
    {
      "concepto_code": "ingresos_por_venta",
      "concepto": "Ingresos por venta o equivalentes",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "resultados_antes_de_impuestos",
      "concepto": "Resultados antes de impuestos",
      "monto_actual": 0,
      "monto_anterior": 0
    },
    {
      "concepto_code": "resultados_del_ejercicio",
      "concepto": "Resultados del ejercicio",
      "monto_actual": 0,
      "monto_anterior": 0
    }
  ],
    "detalles_estado_resultados": [
      {
        "concepto": "Nombre del concepto",
        "monto_actual": 0,
        "monto_anterior": 0
      },
      {
        "concepto": "Nombre del concepto",
        "monto_actual": 0,
        "monto_anterior": 0
      },
      {
        "concepto": "Nombre del concepto",
        "monto_actual": 0,
        "monto_anterior": 0
      }
    ]
}

Los valores con "-" o con paréntesis deben ser extraidos como negativos.
Debes expresar los valores de los períodos en términos: ANUALES HASTA LA FECHA.
Si encuentras que una misma información esta en dos páginas distintas, no la repitas.
No respondas nada más que el JSON.

ATENCIÓN:
- Debes identificar si la página indica que los valores son "en miles" o "en millones", y, de ser así, ajustar los montos para que representen el valor real total.
- "ingresos_por_venta" incluye ventas, ingresos operativos de la empresa, ingresos por servicios, etc.
- El campo "concepto_code" debe seguir el formato snake_case y ser consistente (ej: "ingresos_por_venta", "resultados_antes_de_impuestos")
- El campo "concepto" es opcional y debe contener el nombre legible del concepto
"""
