# ------------------------------------------------------------------------------------
# N2 CALCULATE INDICATORS - Calcula los indicadores financieros
# ------------------------------------------------------------------------------------
"""
Nodo que calcula los 8 indicadores financieros (KPIs) para el reporte.
Usa los datos de resultados_principales del balance y estado de resultados.
"""

import logging
from bson import ObjectId
from app.services.report_graph.graph_state import ReportProcessingState
from app.core.database import reports_collection
from app.utils.indicators_calculator import calculate_indicators

logger = logging.getLogger(__name__)


async def calculate_indicators_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Calcula los indicadores financieros para el reporte.
    
    Pasos:
    1. Obtiene balance_data e income_statement_data del docfile
    2. Calcula los 8 indicadores usando indicators_calculator
    3. Actualiza el reporte en MongoDB con los indicadores
    """
    report_id = state.get("report_id")
    docfile = state.get("docfile")
    
    if not report_id:
        return {**state, "error_message": "report_id no encontrado en el estado"}
    
    if not docfile:
        return {**state, "error_message": "docfile no encontrado en el estado"}
    
    logger.info(f"[REPORT_GRAPH] Calculando indicadores para reporte: {report_id}")
    
    try:
        # Obtener datos del docfile
        balance_data = docfile.get("balance_data", {})
        income_statement_data = docfile.get("income_statement_data", {})
        
        if not balance_data and not income_statement_data:
            logger.warning(f"[REPORT_GRAPH] No hay datos para calcular indicadores en reporte {report_id}")
            # No es un error crítico, continuar sin indicadores
            return {**state, "indicators": [], "progress": 0.66}
        
        # Calcular indicadores
        indicators = calculate_indicators(balance_data, income_statement_data)
        
        # Convertir a formato dict para MongoDB
        indicators_dict = [indicator.model_dump() for indicator in indicators]
        
        logger.info(f"[REPORT_GRAPH] {len(indicators_dict)} indicadores calculados para reporte {report_id}")
        
        # Actualizar el reporte en la base de datos
        await reports_collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"indicators": indicators_dict}}
        )
        
        # Actualizar estado
        updated_state = state.copy()
        updated_state.update({
            "indicators": indicators_dict,
            "progress": 0.66
        })
        
        return updated_state
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error calculando indicadores: {str(e)}")
        return {**state, "error_message": f"Error calculando indicadores: {str(e)}"}
