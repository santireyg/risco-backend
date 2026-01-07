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
import time
from app.services.report_graph.graph_state import ReportProcessingState
from app.utils.status_notifier import update_status
from app.core.database import docs_collection

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------
# NODOS DE CONTROL
# ------------------------------------------------------------------------------------
async def start_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Nodo inicial del graph de reportes.
    
    Valida los parámetros de entrada y prepara el estado.
    Actualiza el status del documento a 'Reporte IA'.
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
        user_id = str(requester.id)
        docfile_id = state["docfile_id"]
        
        logger.info(f"[REPORT_GRAPH] [TENANT: {tenant_id}] Documento {docfile_id}: Iniciando generación de reporte")
        
        # Actualizar status del documento a 'Reporte IA'
        await update_status(
            collection=docs_collection,
            docfile_id=docfile_id,
            new_status="Reporte IA",
            user_id=user_id,
            update_db=True,
            send_progress_ws=False
        )
        
        logger.info(f"[REPORT_GRAPH] Documento {docfile_id} actualizado a status 'Reporte IA'")
        
        # Inicializar campos
        updated_state = state.copy()
        updated_state["tenant_id"] = tenant_id
        updated_state["progress"] = 0.0
        updated_state["error_message"] = None
        updated_state["start_time"] = time.perf_counter()  # Iniciar medición de tiempo
        
        return updated_state
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error en start_node: {str(e)}")
        return {**state, "error_message": f"Error en inicialización: {str(e)}"}


async def end_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Nodo final del graph de reportes.
    
    Actualiza el status del documento a 'Analizado' y el status del reporte a 'Finalizado'.
    Realiza limpieza y logging del resultado.
    """
    from app.core.database import reports_collection
    from bson import ObjectId
    import json
    from app.websockets.manager import manager
    
    docfile_id = state["docfile_id"]
    report_id = state.get("report_id")
    requester = state.get("requester")
    start_time = state.get("start_time")
    
    if state.get("error_message"):
        logger.error(f"[REPORT_GRAPH] Generación completada con errores - Documento: {docfile_id} - Error: {state['error_message']}")
    else:
        logger.info(f"[REPORT_GRAPH] Reporte generado exitosamente - Documento: {docfile_id} - Report ID: {report_id}")
        
        try:
            # Calcular duración total del proceso de reporting
            duration = None
            if start_time:
                duration = time.perf_counter() - start_time
                logger.info(f"[REPORT_GRAPH] Tiempo de generación de reporte: {duration:.2f}s")
            # Actualizar status del documento a 'Analizado'
            user_id = str(requester.id) if requester else None
            if user_id:
                await update_status(
                    collection=docs_collection,
                    docfile_id=docfile_id,
                    new_status="Analizado",
                    user_id=user_id,
                    update_db=True,
                    send_progress_ws=False
                )
                logger.info(f"[REPORT_GRAPH] Documento {docfile_id} actualizado a status 'Analizado'")
            
            # Actualizar status del reporte a 'Finalizado' y notificar por websocket
            if report_id:
                # Preparar actualización del reporte
                report_update = {"status": "Finalizado"}
                if duration is not None:
                    report_update["report_processing_time"] = duration
                
                await reports_collection.update_one(
                    {"_id": ObjectId(report_id)},
                    {"$set": report_update}
                )
                logger.info(f"[REPORT_GRAPH] Reporte {report_id} actualizado a status 'Finalizado'")
                
                # Actualizar report_status y processing_time.reporting en el documento usando update_status
                from app.models.docs_processing_time import ProcessingTime
                
                # Obtener documento para actualizar processing_time
                document = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
                if document and duration is not None:
                    # Obtener o crear processing_time
                    processing_time_data = document.get("processing_time", {})
                    processing_time = ProcessingTime(**processing_time_data) if processing_time_data else ProcessingTime()
                    
                    # Actualizar el tiempo de reporting (no afecta el total)
                    processing_time.reporting = duration
                    
                    # Actualizar usando update_status para notificar via websocket
                    await update_status(
                        collection=docs_collection,
                        docfile_id=docfile_id,
                        new_status="Analizado",
                        user_id=user_id,
                        report_status="Finalizado",
                        processing_time=processing_time.model_dump(),
                        update_db=True,
                        send_progress_ws=False
                    )
                    logger.info(f"[REPORT_GRAPH] Documento {docfile_id} actualizado con report_status: 'Finalizado' y tiempo de reporting: {duration:.2f}s (notificado vía websocket)")
                else:
                    # Actualizar solo report_status usando update_status
                    await update_status(
                        collection=docs_collection,
                        docfile_id=docfile_id,
                        new_status="Analizado",
                        user_id=user_id,
                        report_status="Finalizado",
                        update_db=True,
                        send_progress_ws=False
                    )
                    logger.info(f"[REPORT_GRAPH] Documento {docfile_id} actualizado con report_status: 'Finalizado' (notificado vía websocket)")
                    
        except Exception as e:
            logger.error(f"[REPORT_GRAPH] Error actualizando status final: {str(e)}")
    
    return state


async def error_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Nodo de manejo de errores para el graph de reportes.
    
    Actualiza el estado del reporte a "Error" y del documento a "Analizado" en la base de datos.
    Notifica via websocket.
    """
    from app.core.database import reports_collection
    from bson import ObjectId
    import json
    from app.websockets.manager import manager
    
    report_id = state.get("report_id")
    docfile_id = state.get("docfile_id")
    requester = state.get("requester")
    error_message = state.get("error_message", "Error desconocido en generación de reporte")
    
    logger.error(f"[REPORT_GRAPH] Error en generación de reporte: {error_message}")
    
    try:
        user_id = str(requester.id) if requester else None
        
        # Actualizar estado del reporte a Error si existe
        if report_id:
            await reports_collection.update_one(
                {"_id": ObjectId(report_id)},
                {"$set": {"status": "Error", "error_message": error_message}}
            )
            logger.info(f"[REPORT_GRAPH] Reporte {report_id} marcado con status Error")
            
            # Actualizar report_status en el documento usando update_status
            if docfile_id and user_id:
                await update_status(
                    collection=docs_collection,
                    docfile_id=docfile_id,
                    new_status="Analizado",
                    user_id=user_id,
                    report_status="Error",
                    error_message=error_message,
                    update_db=True,
                    send_progress_ws=False
                )
                logger.info(f"[REPORT_GRAPH] Documento {docfile_id} actualizado a status 'Analizado' con report_status: 'Error' (notificado vía websocket)")
        
        # Si no hay report_id, solo actualizar status del documento
        elif docfile_id and user_id:
            await update_status(
                collection=docs_collection,
                docfile_id=docfile_id,
                new_status="Analizado",
                user_id=user_id,
                update_db=True,
                send_progress_ws=False
            )
            logger.info(f"[REPORT_GRAPH] Documento {docfile_id} actualizado a status 'Analizado' tras error")
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error actualizando status de error para reporte {report_id}: {str(e)}")
    
    return {**state, "error_message": error_message}
