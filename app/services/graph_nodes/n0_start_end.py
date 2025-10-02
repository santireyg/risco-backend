# ------------------------------------------------------------------------------------
# N0 START END - Nodos de Control para LangGraph
# ------------------------------------------------------------------------------------
"""
Nodos de control del graph de procesamiento de documentos:
- start_node: Inicialización y validaciones básicas
- end_node: Finalización y limpieza
- error_node: Manejo centralizado de errores
"""

import logging
from app.services.graph_state import DocumentProcessingState
from app.services.graph_router import get_operation_description

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------
# NODOS DE CONTROL
# ------------------------------------------------------------------------------------
async def start_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo inicial del graph.

    Realiza validaciones básicas y prepara el estado para el procesamiento.
    
    Args:
        state: Estado inicial del procesamiento
        
    Returns:
        DocumentProcessingState: Estado validado y preparado
    """
    logger.info(f"Iniciando procesamiento - Operación: {state['operation']} - Documento: {state['docfile_id']}")
    
    try:
        # Validaciones básicas
        if not state.get("docfile_id"):
            return {**state, "error_message": "docfile_id es requerido"}
        
        if not state.get("requester"):
            return {**state, "error_message": "requester es requerido"}
        
        if not state.get("operation"):
            return {**state, "error_message": "operation es requerida"}
        
        # Obtener tenant_id del usuario
        requester = state["requester"]
        tenant_id = getattr(requester, "tenant_id", "default")
        
        # Log de la operación que se va a ejecutar
        operation_desc = get_operation_description(state["operation"])
        logger.info(f"[TENANT: {tenant_id}] Documento {state['docfile_id']}: {operation_desc}")
        
        # Inicializar campos si no existen
        updated_state = state.copy()
        updated_state["tenant_id"] = tenant_id
        if "progress" not in updated_state:
            updated_state["progress"] = 0.0
        if "error_message" not in updated_state:
            updated_state["error_message"] = None
        
        return updated_state
        
    except Exception as e:
        logger.error(f"Error en start_node: {str(e)}")
        return {**state, "error_message": f"Error en inicialización: {str(e)}"}


async def end_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo final del graph.
    
    Realiza limpieza final y logging del completado del procesamiento.
    
    Args:
        state: Estado final del procesamiento
        
    Returns:
        DocumentProcessingState: Estado final
    """
    docfile_id = state["docfile_id"]
    operation = state["operation"]
    
    if state.get("error_message"):
        logger.error(f"Procesamiento completado con errores - Documento: {docfile_id} - Operación: {operation}")
    else:
        logger.info(f"Procesamiento completado exitosamente - Documento: {docfile_id} - Operación: {operation}")
    
    return state


async def error_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo de manejo de errores.
    
    Centraliza el manejo de errores del graph y actualiza el estado
    del documento en la base de datos.
    
    Args:
        state: Estado con error
        
    Returns:
        DocumentProcessingState: Estado con error procesado
    """
    from app.core.database import docs_collection
    from app.utils.status_notifier import update_status
    from bson import ObjectId
    
    docfile_id = state["docfile_id"]
    error_message = state.get("error_message", "Error desconocido en procesamiento")
    requester = state["requester"]
    user_id = str(requester.id)
    
    logger.error(f"Error en procesamiento del documento {docfile_id}: {error_message}")
    
    try:
        # Actualizar estado del documento a Error
        await update_status(
            docs_collection,
            docfile_id,
            "Error",
            user_id,
            error_message=error_message,
            update_db=True,
            send_progress_ws=True
        )
        
    except Exception as e:
        logger.error(f"Error actualizando status de error para documento {docfile_id}: {str(e)}")
    
    # Mantener el error en el estado
    return {**state, "error_message": error_message}