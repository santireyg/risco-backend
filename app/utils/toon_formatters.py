# ------------------------------------------------------------------------------------
# TOON FORMATTERS - Formateadores de datos a formato tabla TOON (markdown)
# ------------------------------------------------------------------------------------
"""
Módulo con funciones para convertir datos de reportes a formato tabla TOON (markdown).
Utilizados principalmente para preparar datos para análisis de IA.
"""

from datetime import datetime


def parse_period_yyyymm_to_mm_yyyy(period_str: str) -> str:
    """
    Convierte un período en formato YYYYMM a MM/YYYY.
    
    Args:
        period_str: Período en formato YYYYMM (ej: "202510")
    
    Returns:
        Período en formato MM/YYYY (ej: "10/2025")
    """
    if not period_str or not isinstance(period_str, str):
        return "N/A"
    
    try:
        # Validar que tenga 6 caracteres
        if len(period_str) != 6:
            return period_str
        
        year = period_str[:4]
        month = period_str[4:6]
        
        return f"{month}/{year}"
    except Exception:
        return period_str


def format_date(date_obj) -> str:
    """Formatea una fecha para mostrar."""
    if not date_obj:
        return "N/A"
    
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%d/%m/%Y")
    
    return str(date_obj)


def format_indicators_to_toon(indicators: list) -> str:
    """Convierte indicadores a formato tabla TOON (markdown)."""
    if not indicators:
        return "No hay indicadores disponibles."
    
    table = "| Código | Indicador | Descripción | Valor Actual | Valor Anterior | Variación | Clasificación Actual | Clasificación Anterior |\n"
    table += "|--------|-----------|-------------|--------------|----------------|-----------|----------------------|------------------------|\n"
    
    for ind in indicators:
        code = ind.get("code", "N/A")
        name = ind.get("name", "N/A")
        description = ind.get("description", "N/A")
        value_current = ind.get("value_current")
        value_previous = ind.get("value_previous")
        variation = ind.get("variation")
        class_current = ind.get("classification_current", "N/A")
        class_previous = ind.get("classification_previous", "N/A")
        
        # Formatear valores numéricos
        val_curr_str = f"{value_current:.2f}" if value_current is not None else "N/A"
        val_prev_str = f"{value_previous:.2f}" if value_previous is not None else "N/A"
        var_str = f"{variation:+.2f}%" if variation is not None else "N/A"
        
        table += f"| {code} | {name} | {description} | {val_curr_str} | {val_prev_str} | {var_str} | {class_current} | {class_previous} |\n"
    
    return table


def format_balance_resultados_principales_to_toon(resultados: list) -> str:
    """Convierte resultados principales del balance a formato tabla TOON."""
    if not resultados:
        return "No hay datos disponibles."
    
    table = "| Concepto | Código | Monto Actual | Monto Anterior |\n"
    table += "|----------|--------|--------------|----------------|\n"
    
    for item in resultados:
        concepto = item.get("concepto", "N/A")
        code = item.get("concepto_code", "")
        monto_actual = item.get("monto_actual")
        monto_anterior = item.get("monto_anterior")
        
        monto_act_str = f"{monto_actual:,.2f}" if monto_actual is not None else "N/A"
        monto_ant_str = f"{monto_anterior:,.2f}" if monto_anterior is not None else "N/A"
        
        table += f"| {concepto} | {code} | {monto_act_str} | {monto_ant_str} |\n"
    
    return table


def format_balance_detalles_to_toon(detalles: list, titulo: str) -> str:
    """Convierte detalles del balance (activo, pasivo, patrimonio) a formato tabla TOON."""
    if not detalles:
        return f"No hay detalles de {titulo}."
    
    table = f"#### {titulo}\n\n"
    table += "| Concepto | Código | Monto Actual | Monto Anterior |\n"
    table += "|----------|--------|--------------|----------------|\n"
    
    for item in detalles:
        concepto = item.get("concepto", "N/A")
        code = item.get("concepto_code", "")
        monto_actual = item.get("monto_actual")
        monto_anterior = item.get("monto_anterior")
        
        monto_act_str = f"{monto_actual:,.2f}" if monto_actual is not None else "N/A"
        monto_ant_str = f"{monto_anterior:,.2f}" if monto_anterior is not None else "N/A"
        
        table += f"| {concepto} | {code} | {monto_act_str} | {monto_ant_str} |\n"
    
    return table


def format_balance_data_to_toon(balance_data: dict) -> str:
    """Convierte datos del balance a formato tabla TOON."""
    if not balance_data:
        return "No hay datos de balance disponibles."
    
    output = "### Resultados Principales del Balance\n\n"
    output += format_balance_resultados_principales_to_toon(
        balance_data.get("resultados_principales", [])
    )
    output += "\n\n"
    
    # Detalles
    detalles_activo = balance_data.get("detalles_activo", [])
    detalles_pasivo = balance_data.get("detalles_pasivo", [])
    detalles_patrimonio = balance_data.get("detalles_patrimonio_neto", [])
    
    if detalles_activo:
        output += format_balance_detalles_to_toon(detalles_activo, "Detalles del Activo")
        output += "\n\n"
    
    if detalles_pasivo:
        output += format_balance_detalles_to_toon(detalles_pasivo, "Detalles del Pasivo")
        output += "\n\n"
    
    if detalles_patrimonio:
        output += format_balance_detalles_to_toon(detalles_patrimonio, "Detalles del Patrimonio Neto")
        output += "\n\n"
    
    return output


def format_income_data_to_toon(income_data: dict) -> str:
    """Convierte datos del estado de resultados a formato tabla TOON."""
    if not income_data:
        return "No hay datos de estado de resultados disponibles."
    
    output = "### Resultados Principales del Estado de Resultados\n\n"
    output += format_balance_resultados_principales_to_toon(
        income_data.get("resultados_principales", [])
    )
    output += "\n\n"
    
    # Detalles
    detalles = income_data.get("detalles_estado_resultados", [])
    if detalles:
        output += "#### Detalles del Estado de Resultados\n\n"
        output += "| Concepto | Código | Monto Actual | Monto Anterior |\n"
        output += "|----------|--------|--------------|----------------|\n"
        
        for item in detalles:
            concepto = item.get("concepto", "N/A")
            code = item.get("concepto_code", "")
            monto_actual = item.get("monto_actual")
            monto_anterior = item.get("monto_anterior")
            
            monto_act_str = f"{monto_actual:,.2f}" if monto_actual is not None else "N/A"
            monto_ant_str = f"{monto_anterior:,.2f}" if monto_anterior is not None else "N/A"
            
            output += f"| {concepto} | {code} | {monto_act_str} | {monto_ant_str} |\n"
        
        output += "\n\n"
    
    return output


def format_bcra_deudas_ultimo_periodo_to_toon(periodo: dict) -> str:
    """Convierte deudas del último período del BCRA a formato tabla TOON."""
    if not periodo or not periodo.get("entidades"):
        return "No hay deudas en el último período."
    
    # Parsear período
    periodo_str = periodo.get('periodo', 'N/A')
    mes_periodo = parse_period_yyyymm_to_mm_yyyy(periodo_str)
    
    table = f"**Mes Período:** {mes_periodo}\n\n"
    table += "| Entidad | Situación | Fecha Sit. | Monto | Días Atraso | Refinanc. | Recat. Oblig. | Sit. Jurídica | Irrec. Disp. Téc. | En Revisión | Proceso Jud. |\n"
    table += "|---------|-----------|------------|-------|-------------|-----------|---------------|---------------|-------------------|-------------|-------------|\n"
    
    for entidad_data in periodo.get("entidades", []):
        entidad = entidad_data.get("entidad", "N/A")
        situacion = entidad_data.get("situacion", "N/A")
        fecha_sit = entidad_data.get("fecha_sit", "N/A")
        monto = entidad_data.get("monto", 0)
        dias_atraso = entidad_data.get("dias_atraso_pago", 0)
        refinanciaciones = "Sí" if entidad_data.get("refinanciaciones") else "No"
        recat = "Sí" if entidad_data.get("recategorizacion_oblig") else "No"
        sit_jur = "Sí" if entidad_data.get("situacion_juridica") else "No"
        irrec = "Sí" if entidad_data.get("irrec_disposicion_tecnica") else "No"
        revision = "Sí" if entidad_data.get("en_revision") else "No"
        proc_jud = "Sí" if entidad_data.get("proceso_jud") else "No"
        
        monto_str = f"{monto:,.2f}"
        
        table += f"| {entidad} | {situacion} | {fecha_sit} | {monto_str} | {dias_atraso} | {refinanciaciones} | {recat} | {sit_jur} | {irrec} | {revision} | {proc_jud} |\n"
    
    return table


def format_bcra_deudas_historia_to_toon(historia: list) -> str:
    """Convierte historial de deudas del BCRA a formato tabla TOON."""
    if not historia:
        return "No hay historial de deudas disponible."
    
    table = "| Mes Período | Entidad | Situación | Monto | Días Atraso |\n"
    table += "|-------------|---------|-----------|-------|-------------|\n"
    
    for periodo_data in historia:
        periodo_str = periodo_data.get("periodo", "N/A")
        mes_periodo = parse_period_yyyymm_to_mm_yyyy(periodo_str)
        
        for entidad_data in periodo_data.get("entidades", []):
            entidad = entidad_data.get("entidad", "N/A")
            situacion = entidad_data.get("situacion", "N/A")
            monto = entidad_data.get("monto", 0)
            dias_atraso = entidad_data.get("dias_atraso_pago", 0)
            
            monto_str = f"{monto:,.2f}"
            
            table += f"| {mes_periodo} | {entidad} | {situacion} | {monto_str} | {dias_atraso} |\n"
    
    return table


def format_bcra_cheques_to_toon(cheques: list) -> str:
    """Convierte cheques rechazados del BCRA a formato tabla TOON."""
    if not cheques:
        return "No hay cheques rechazados."
    
    table = "| Causal | Entidad | Nro. Cheque | Fecha Rechazo | Monto | Fecha Pago | Estado Multa | Cta. Personal | En Revisión | Proceso Jud. |\n"
    table += "|--------|---------|-------------|---------------|-------|------------|--------------|---------------|-------------|-------------|\n"
    
    for causal_data in cheques:
        causal = causal_data.get("causal", "N/A")
        for entidad_data in causal_data.get("entidades", []):
            entidad = entidad_data.get("entidad", "N/A")
            for detalle in entidad_data.get("detalle", []):
                nro = detalle.get("nro_cheque", "N/A")
                fecha_rec = detalle.get("fecha_rechazo", "N/A")
                monto = detalle.get("monto", 0)
                fecha_pago = detalle.get("fecha_pago", "N/A")
                estado_multa = detalle.get("estado_multa", "N/A")
                cta_personal = "Sí" if detalle.get("cta_personal") else "No"
                revision = "Sí" if detalle.get("en_revision") else "No"
                proc_jud = "Sí" if detalle.get("proceso_jud") else "No"
                
                monto_str = f"{monto:,.2f}"
                
                table += f"| {causal} | {entidad} | {nro} | {fecha_rec} | {monto_str} | {fecha_pago} | {estado_multa} | {cta_personal} | {revision} | {proc_jud} |\n"
    
    return table


def format_bcra_data_to_toon(bcra_data: dict) -> str:
    """Convierte datos del BCRA a formato tabla TOON."""
    if not bcra_data:
        return "No hay datos del BCRA disponibles."
    
    output = ""
    
    # Deudas último período
    deudas_ultimo = bcra_data.get("deudas_ultimo_periodo")
    if deudas_ultimo:
        output += "#### Deudas del Último Período\n\n"
        output += format_bcra_deudas_ultimo_periodo_to_toon(deudas_ultimo)
        output += "\n\n"
    
    # Historial de deudas
    historia = bcra_data.get("deudas_historia", [])
    if historia:
        output += "#### Historial de Deudas (últimos períodos)\n\n"
        output += format_bcra_deudas_historia_to_toon(historia)
        output += "\n\n"
    
    # Cheques rechazados
    cheques = bcra_data.get("cheques_rechazados", [])
    if cheques:
        output += "#### Cheques Rechazados\n\n"
        output += format_bcra_cheques_to_toon(cheques)
        output += "\n\n"
    
    if not output:
        output = "No hay datos relevantes del BCRA disponibles."
    
    return output


def format_company_info(company_info: dict) -> str:
    """Formatea la información de la empresa."""
    if not company_info:
        return "No hay información de la empresa disponible."
    
    output = ""
    output += f"**Nombre:** {company_info.get('company_name', 'N/A')}\n"
    output += f"**CUIT:** {company_info.get('company_cuit', 'N/A')}\n"
    
    if company_info.get('company_activity'):
        output += f"**Actividad:** {company_info.get('company_activity')}\n"
    
    if company_info.get('company_address'):
        output += f"**Dirección:** {company_info.get('company_address')}\n"
    
    return output
