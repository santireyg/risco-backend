# ------------------------------------------------------------------------------------
# N3 GET BCRA DATA - Obtiene datos del BCRA
# ------------------------------------------------------------------------------------
"""
Nodo que consulta la API del BCRA para obtener:
- Deudas del último período
- Historial de deudas (24 meses)
- Cheques rechazados

Actualiza el reporte con bcra_data y cambia status a "Reporte creado".
"""

import logging
from datetime import datetime
from bson import ObjectId
from app.services.report_graph.graph_state import ReportProcessingState
from app.core.database import reports_collection
from app.utils.bcra_client import get_all_bcra_data, BCRAClientError

logger = logging.getLogger(__name__)


async def get_bcra_data_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Obtiene datos del BCRA para el reporte.
    
    Pasos:
    1. Obtiene el CUIT de company_info del docfile
    2. Consulta las 3 APIs del BCRA (deudas, históricas, cheques)
    3. Actualiza el reporte en MongoDB con bcra_data
    4. Cambia el status del reporte a "Reporte creado"
    """
    report_id = state.get("report_id")
    docfile = state.get("docfile")
    
    if not report_id:
        return {**state, "error_message": "report_id no encontrado en el estado"}
    
    logger.info(f"[REPORT_GRAPH] Obteniendo datos BCRA para reporte: {report_id}")
    
    try:
        # Obtener CUIT del company_info
        company_info = docfile.get("company_info", {}) if docfile else {}
        cuit = company_info.get("company_cuit")
        
        bcra_data = None
        
        if cuit:
            logger.info(f"[REPORT_GRAPH] Consultando BCRA para CUIT: {cuit}")
            
            try:
                # Obtener todos los datos del BCRA
                bcra_data = await get_all_bcra_data(cuit)
                logger.info(f"[REPORT_GRAPH] Datos BCRA obtenidos exitosamente para reporte {report_id}")
                
            except BCRAClientError as e:
                # Log del error pero continuar (no es crítico)
                logger.warning(f"[REPORT_GRAPH] Error consultando BCRA: {e.message}")
                bcra_data = {
                    "identificacion": cuit,
                    "denominacion": None,
                    "fecha_consulta": datetime.utcnow().isoformat(),
                    "deudas_ultimo_periodo": None,
                    "deudas_historia": [],
                    "cheques_rechazados": [],
                    "error": e.message
                }
        else:
            logger.warning(f"[REPORT_GRAPH] No se encontró CUIT para reporte {report_id}")
            bcra_data = {
                "identificacion": None,
                "denominacion": None,
                "fecha_consulta": datetime.utcnow().isoformat(),
                "deudas_ultimo_periodo": None,
                "deudas_historia": [],
                "cheques_rechazados": [],
                "error": "CUIT no disponible en el documento"
            }
        
        # Actualizar el reporte en la base de datos
        await reports_collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"bcra_data": bcra_data}}
        )
        
        logger.info(f"[REPORT_GRAPH] Reporte {report_id} actualizado con bcra_data")
        
        # Actualizar estado
        updated_state = state.copy()
        updated_state.update({
            "bcra_data": bcra_data,
            "progress": 1.0
        })
        
        return updated_state
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error obteniendo datos BCRA: {str(e)}")
        return {**state, "error_message": f"Error obteniendo datos BCRA: {str(e)}"}
