# ------------------------------------------------------------------------------------
# N0 START END - Nodos de Control para Report Graph
# ------------------------------------------------------------------------------------
"""
Nodos de control del graph de generación de reportes:
- start_node: Inicialización y validaciones básicas
- end_node: Finalización y limpieza
- error_node: Manejo centralizado de errores
"""

import logging
from app.services.report_graph.graph_state import ReportProcessingState

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------
# NODOS DE CONTROL
# ------------------------------------------------------------------------------------
async def start_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Nodo inicial del graph de reportes.
    
    Valida los parámetros de entrada y prepara el estado.
    """
    logger.info(f"[REPORT_GRAPH] Iniciando generación de reporte - Documento: {state['docfile_id']}")
    
    try:
        # Validaciones básicas
        if not state.get("docfile_id"):
            return {**state, "error_message": "docfile_id es requerido"}
        
        if not state.get("requester"):
            return {**state, "error_message": "requester es requerido"}
        
        # Obtener tenant_id del usuario
        requester = state["requester"]
        tenant_id = getattr(requester, "tenant_id", "default")
        
        logger.info(f"[REPORT_GRAPH] [TENANT: {tenant_id}] Documento {state['docfile_id']}: Iniciando generación de reporte")
        
        # Inicializar campos
        updated_state = state.copy()
        updated_state["tenant_id"] = tenant_id
        updated_state["progress"] = 0.0
        updated_state["error_message"] = None
        
        return updated_state
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error en start_node: {str(e)}")
        return {**state, "error_message": f"Error en inicialización: {str(e)}"}


async def end_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Nodo final del graph de reportes.
    
    Realiza limpieza y logging del resultado.
    """
    docfile_id = state["docfile_id"]
    report_id = state.get("report_id")
    
    if state.get("error_message"):
        logger.error(f"[REPORT_GRAPH] Generación completada con errores - Documento: {docfile_id} - Error: {state['error_message']}")
    else:
        logger.info(f"[REPORT_GRAPH] Reporte generado exitosamente - Documento: {docfile_id} - Report ID: {report_id}")
    
    return state


async def error_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Nodo de manejo de errores para el graph de reportes.
    
    Actualiza el estado del reporte a "Error" en la base de datos.
    """
    from app.core.database import reports_collection
    from bson import ObjectId
    
    report_id = state.get("report_id")
    error_message = state.get("error_message", "Error desconocido en generación de reporte")
    
    logger.error(f"[REPORT_GRAPH] Error en generación de reporte: {error_message}")
    
    try:
        # Actualizar estado del reporte a Error si existe
        if report_id:
            await reports_collection.update_one(
                {"_id": ObjectId(report_id)},
                {"$set": {"status": "Error", "error_message": error_message}}
            )
            logger.info(f"[REPORT_GRAPH] Reporte {report_id} marcado con status Error")
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error actualizando status de error para reporte {report_id}: {str(e)}")
    
    return {**state, "error_message": error_message}
