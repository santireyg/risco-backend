# ------------------------------------------------------------------------------------
# N4 GENERATE AI REPORT - Genera reporte de IA con análisis de riesgo
# ------------------------------------------------------------------------------------
"""
Nodo que genera un reporte de análisis de riesgo usando IA.
Procesa datos contables, indicadores y datos del BCRA para generar un análisis estructurado.
"""

import logging
from bson import ObjectId
from app.services.report_graph.graph_state import ReportProcessingState
from app.core.database import reports_collection
from app.models.report import AIReport
from langchain_openai import ChatOpenAI
from app.utils.toon_formatters import (
    format_indicators_to_toon,
    format_balance_data_to_toon,
    format_income_data_to_toon,
    format_bcra_data_to_toon,
    format_company_info,
    format_date
)
from app.utils.prompts_ai_report import PROMPT_INSTRUCCIONES

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------
# NODO PRINCIPAL
# ------------------------------------------------------------------------------------
async def generate_ai_report_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Genera reporte de IA con análisis de riesgo.
    
    Pasos:
    1. Obtiene datos del reporte actual
    2. Formatea datos en tablas TOON
    3. Construye prompt con indicaciones y datos
    4. Llama al LLM (gpt-5.2) con structured output
    5. Actualiza el reporte con ai_report
    """
    report_id = state.get("report_id")
    docfile = state.get("docfile")
    indicators = state.get("indicators")
    bcra_data = state.get("bcra_data")
    
    if not report_id:
        return {**state, "error_message": "report_id no encontrado en el estado"}
    
    logger.info(f"[REPORT_GRAPH] Generando reporte IA para reporte: {report_id}")
    
    try:
        # Extraer datos necesarios del docfile
        company_info = docfile.get("company_info", {}) if docfile else {}
        balance_data = docfile.get("balance_data", {}) if docfile else {}
        income_statement_data = docfile.get("income_statement_data", {}) if docfile else {}
        statement_date = docfile.get("balance_date") if docfile else None
        statement_date_previous = docfile.get("balance_date_previous") if docfile else None
        
        # Formatear datos a TOON
        logger.info(f"[REPORT_GRAPH] Formateando datos a TOON para reporte {report_id}")
        
        indicators_toon = format_indicators_to_toon(indicators or [])
        balance_toon = format_balance_data_to_toon(balance_data)
        income_toon = format_income_data_to_toon(income_statement_data)
        bcra_toon = format_bcra_data_to_toon(bcra_data or {})
        company_info_str = format_company_info(company_info)
        
        # Construir prompt completo
        prompt_text = f"""
        {PROMPT_INSTRUCCIONES}

        ---

        ## DATOS DE LA EMPRESA

        {company_info_str}

        ---

        ## ESTADOS CONTABLES

        ### Fechas de los Estados Contables
        - **Período actual:** {format_date(statement_date)}
        - **Período anterior:** {format_date(statement_date_previous)}

        ### Balance

        {balance_toon}

        ### Estado de Resultados

        {income_toon}

        ---

        ## INDICADORES FINANCIEROS

        {indicators_toon}

        ---

        ## INFORMACIÓN BCRA

        ### Datos de la Consulta
        - **Identificación (CUIT):** {bcra_data.get('identificacion', 'N/A') if bcra_data else 'N/A'}
        - **Denominación:** {bcra_data.get('denominacion', 'N/A') if bcra_data else 'N/A'}
        - **Fecha de consulta:** {format_date(bcra_data.get('fecha_consulta')) if bcra_data else 'N/A'}

        ### Datos del BCRA

        {bcra_toon}

        ---
        """
        
        logger.info(f"[REPORT_GRAPH] Invocando LLM gpt-5.2 para reporte {report_id}")
        
        # Crear modelo LLM con structured output
        # Usar el método por defecto (function calling) que es más robusto para structured output
        model = ChatOpenAI(
            model="gpt-5.2",
            temperature=0,
            max_retries=2
        ).with_structured_output(AIReport)
        
        # Invocar modelo
        ai_report = await model.ainvoke(prompt_text)
        
        # Convertir a dict para MongoDB
        ai_report_dict = ai_report.model_dump()
        
        logger.info(f"[REPORT_GRAPH] Reporte IA generado exitosamente para reporte {report_id}")
        
        # Actualizar reporte en MongoDB
        await reports_collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"ai_report": ai_report_dict}}
        )
        
        logger.info(f"[REPORT_GRAPH] Reporte {report_id} actualizado con ai_report")
        
        # Actualizar estado
        updated_state = state.copy()
        updated_state.update({
            "ai_report": ai_report_dict,
            "progress": 0.88
        })
        
        # Liberar memoria
        del prompt_text
        del ai_report
        
        return updated_state
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error generando reporte IA: {str(e)}", exc_info=True)
        return {**state, "error_message": f"Error generando reporte IA: {str(e)}"}
