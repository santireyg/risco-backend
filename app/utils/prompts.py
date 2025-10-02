# path: app/prompts.py

prompt_recognize_pages = """
Para la imagen debes extraer la siguiente información:
- is_balance_sheet (bool): si la página en cuestión contiene una tabla de Situación Patrimonial consolidado (Activo completo, Pasivo completo y/o PN completo) de la empresa.
- is_income_statement_sheet (bool): si la página  contiene una tabla de Estado de Resultados (o análogo) consolidado completa (ingresos + gastos + resultado/utilidad) de la empresa.
- is_appendix (bool): si la página en cuestión figura como una pagina auxiliar, o un anexo, o una nota explicativa.
- original_orientation_degrees (int): si la tabla no se encuentra horizontal, cuántos grados debo rotarla antihorario para leerla bien (0, 90, 180, 270). 
- has_company_cuit (bool): si la página contiene el CUIT de la empresa.
- has_company_name (bool): si la página contiene el nombre de la empresa.
- has_company_address (bool): si la página contiene la dirección de registro la empresa.
- has_company_activity (bool): si la página especifica claramente la Actividad Económica Principal de la empresa.
- audit_report (bool): si contiene el Informe Independiente de Auditoría Contable.

Debes analizar (leer) manualmente, y responder en el siguiente formato JSON:
{
  "is_balance_sheet": False,
  "is_income_statement_sheet": False,
  "is_appendix": False,
  "original_orientation_degrees": 0,
  "has_company_cuit": False,
  "has_company_name": False,
  "has_company_address": False,
  "has_company_activity": False,
  "audit_report": False
}

Solo puedes considerar is_income_statement_sheet cuando la tabla contiene en simultáneo ingresos, costos, y gastos, culminando en la utilidad neta o pérdida neta (resultado del ejercicio o análogos). 
Y debe ser el cuadro CONSOLIDADO TOTAL, No deben ser anexos.

Solo puedes considerar is_balance_sheet cuando la tabla contiene TODO el Activo, y/o Todo el Pasivo y/o Todo el Patrimonio Neto.
No debes considerar is_balance_sheet si la tabla es auxiliar o muestra un desagregado de cuentas.

Recuerda no considerar True en "is_income_statement_sheet" y "is_balance_sheet" si es un anexo o tabla auxiliar.
Responde sólo con el JSON.
"""

prompt_extract_income_statement_data = """
A continuación se encuentra un Estado de Resultados, tu tarea es extraer la información solicitada. 
Debes detallar todos los ingresos y gastos que figuran en la imagen. 
Todos los montos deben ser extraidos con su correspondiente signo positivo o negativo. 
Los valores con "-" o con paréntesis deben ser extraidos como negativos.

En "detalles_estado_resultados" debes volcar todos y cada uno de los registros y calculos que están presentes en el cuadro de Estado de Resultados.

Responde en un JSON como el siguiente:
{
  "informacion_general": {
    "empresa": "Nombre de la empresa, si es que figura",
    "periodo_actual": "YYYY-MM-DD",
    "periodo_anterior": "YYYY-MM-DD"
    },
  "resultados_principales": {
    "ingresos_operativos_empresa_actual": 0,
    "ingresos_operativos_empresa_anterior": 0,
    "resultados_antes_de_impuestos_actual": 0,
    "resultados_antes_de_impuestos_anterior": 0,
    "resultados_del_ejercicio_actual": 0,
    "resultados_del_ejercicio_anterior": 0
    },
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

En caso de que no se te brinde una imagen, no inventes datos, y deja los campos de resultados_principales en 0 y las fechas en 1900-01-01.

ATENCIÓN:
- Debes identificar si la página indica que los valores son "en miles" o "en millones", y, de ser así, ajustar los montos para que representen el valor real total.
- "ingresos_operativos_empresa" es como el equivalente a "ventas" o análogos.
"""

prompt_extract_balance_data = """
A continuación se encuentra un Estado de Situación Patrimonial (Balance), tu tarea es extraer la información solicitada. 
Debes detallar todos los registros que figuran en la tabla. 
Todos los montos deben ser extraidos con su correspondiente signo positivo o negativo. 
Los valores con "-" o con paréntesis deben ser extraidos como negativos.

En "detalles_activo", "detalles_pasivo" y "detalles_patrimonio" debes volcar todos y cada uno de los registros y calculos que están presentes en el correspondiente cuadro.

ACLARACIONES IMPORTANTES para "resultados_principales":
-> Para determinar "bienes_de_cambio_o_equivalentes" y "disponibilidades_caja_banco_o_equivalentes", 
considera qué actividad realiza la empresa y qué tipo de empresa es, ya que esto define qué montos corresponden a cada uno de estos conceptos. 

Responde en un JSON como el siguiente:
{
  "informacion_general": {
    "empresa": "Nombre de la empresa, si es que figura",
    "periodo_actual": "YYYY-MM-DD",
    "periodo_anterior": "YYYY-MM-DD"
    },
  "resultados_principales": {
    "disponibilidades_caja_banco_o_equivalentes_actual": 0,
    "disponibilidades_caja_banco_o_equivalentes_anterior": 0,
    "bienes_de_cambio_o_equivalentes_actual": 0,
    "bienes_de_cambio_o_equivalentes_anterior": 0,
    "activo_corriente_actual": 0,
    "activo_corriente_anterior": 0,
    "activo_no_corriente_actual": 0,
    "activo_no_corriente_anterior": 0,
    "activo_total_actual": 0,
    "activo_total_anterior": 0,
    "pasivo_corriente_actual": 0,
    "pasivo_corriente_anterior": 0,
    "pasivo_no_corriente_actual": 0,
    "pasivo_no_corriente_anterior": 0,
    "pasivo_total_actual": 0,
    "pasivo_total_anterior": 0,
    "patrimonio_neto_actual": 0,
    "patrimonio_neto_anterior": 0,
    },
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
"""

prompt_extract_company_info = """
A continuación se encuentra un documento, tu tarea es extraer la información solicitada.
Debes extraer la siguiente información:
- company_cuit (str): CUIT de la empresa, sin guiones ni espacios (string de 11 dígitos numéricos siempre, o None).
- company_name (str): Nombre de la empresa o razón social.
- company_address (str): Dirección o domicilio legal de la empresa o compañía (sólo si está presente en las imágenes).
- company_activity (str): Descripción de la Actividad Económica Principal de la empresa (sólo si está presente en las imágenes).

Sólo debes responder si la información está presente de forma explicita en el documento.

La descripción de la actividad económica principal debe ser breve y concisa.

Responde en un JSON como el siguiente:
{
  "company_cuit": 0,
  "company_name": "Nombre de la empresa",
  "company_address": "Dirección o domicilio",
  "company_activity": "Descripción de la actividad económica principal"
}

En caso de no encontrar la información de company_activity o company_address, puedes dejar el campo como None.

Si las imágenes no contienen la actividad económica principal, o la dirección de la empresa, deja los campos como None.

Si no encuentras el CUIT de la empresa, deja el campo de CUIT con None.
"""