# ------------------------------------------------------------------------------------
# GRAPH DEFINITION - Sistema Principal de LangGraph
# ------------------------------------------------------------------------------------
"""
Sistema principal de procesamiento de documentos basado en LangGraph.
Permite enrutamiento condicional y mejor observabilidad.
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, END

from app.services.graph_state import DocumentProcessingState
from app.services.graph_router import route_operation, router_node, get_operation_description
from app.services.graph_nodes.n0_start_end import start_node, end_node, error_node
from app.services.graph_nodes.n1_upload_convert import upload_convert_node
from app.services.graph_nodes.n2_recognize import recognize_node
from app.services.graph_nodes.n3_extract import extract_node
from app.services.graph_nodes.n4_validate import validate_node
from app.models.users import UserPublic

logger = logging.getLogger(__name__)

# Variable global para instancia del graph (patrón singleton)
_document_processing_graph = None

# Alias para facilitar imports
document_graph = None  # Se inicializará al final del archivo





# ------------------------------------------------------------------------------------
# FUNCIONES DE ENRUTAMIENTO CONDICIONAL
# ------------------------------------------------------------------------------------
def route_from_router(state: DocumentProcessingState) -> str:
    """Enrutamiento desde el router basado en _next_node."""
    return state.get("_next_node", "error_node")


def route_after_upload_convert(state: DocumentProcessingState) -> str:
    """Enrutamiento después de upload_convert - siempre va a recognize."""
    if state.get("error_message"):
        return "error_node"
    return "recognize_node"


def route_after_recognize(state: DocumentProcessingState) -> str:
    """Enrutamiento después de recognize - siempre va a extract."""
    if state.get("error_message"):
        return "error_node"
    return "extract_node"


def route_after_extract(state: DocumentProcessingState) -> str:
    """Enrutamiento después de extract - siempre va a validate."""
    if state.get("error_message"):
        return "error_node"
    return "validate_node"


def route_after_validate(state: DocumentProcessingState) -> str:
    """Enrutamiento después de validate - va a end."""
    if state.get("error_message"):
        return "error_node"
    return "end_node"


def route_from_error(state: DocumentProcessingState) -> str:
    """Enrutamiento desde error - siempre va a end."""
    return "end_node"


# ------------------------------------------------------------------------------------
# CREACIÓN DEL GRAPH
# ------------------------------------------------------------------------------------
def create_document_processing_graph():
    """
    Crea y configura el graph principal de procesamiento de documentos.
    
    Returns:
        Graph: Graph compilado listo para usar
    """
    # Crear el graph con el estado tipado
    graph = StateGraph(DocumentProcessingState)
    
    # ------------------------------------------------------------------------------------
    # AGREGAR NODOS
    # ------------------------------------------------------------------------------------
    graph.add_node("start_node", start_node)
    graph.add_node("router_node", router_node)
    graph.add_node("upload_convert_node", upload_convert_node)
    graph.add_node("recognize_node", recognize_node)
    graph.add_node("extract_node", extract_node)
    graph.add_node("validate_node", validate_node)
    graph.add_node("error_node", error_node)
    graph.add_node("end_node", end_node)
    
    # ------------------------------------------------------------------------------------
    # DEFINIR FLUJO - SECUENCIA PRINCIPAL
    # ------------------------------------------------------------------------------------
    
    # Entrada del graph
    graph.set_entry_point("start_node")
    
    # Desde start siempre va a router
    graph.add_edge("start_node", "router_node")
    
    # El router decide el primer nodo según la operación
    graph.add_conditional_edges(
        "router_node",
        route_from_router,
        {
            "upload_convert_node": "upload_convert_node",
            "recognize_node": "recognize_node", 
            "extract_node": "extract_node",
            "validate_node": "validate_node",
            "error_node": "error_node"
        },
    )
    
    # Flujo después de upload_convert
    graph.add_conditional_edges(
        "upload_convert_node",
        route_after_upload_convert,
        {
            "recognize_node": "recognize_node",
            "error_node": "error_node"
        },
    )
    
    # Flujo después de recognize
    graph.add_conditional_edges(
        "recognize_node",
        route_after_recognize,
        {
            "extract_node": "extract_node",
            "error_node": "error_node"
        },
    )
    
    # Flujo después de extract
    graph.add_conditional_edges(
        "extract_node",
        route_after_extract,
        {
            "validate_node": "validate_node",
            "error_node": "error_node"
        },
    )
    
    # Flujo después de validate
    graph.add_conditional_edges(
        "validate_node",
        route_after_validate,
        {
            "end_node": "end_node",
            "error_node": "error_node"
        },
    )
    
    # Flujo desde error
    graph.add_conditional_edges(
        "error_node",
        route_from_error,
        {
            "end_node": "end_node"
        },
    )
    
    # Finalización del graph
    graph.add_edge("end_node", END)
    
    # Compilar el graph
    compiled_graph = graph.compile()
    
    logger.info("Graph de procesamiento de documentos creado y compilado exitosamente")
    
    return compiled_graph


# ------------------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# ------------------------------------------------------------------------------------
async def process_document(
    operation: Literal["validate", "extract", "recognize_extract", "complete_process"],
    docfile_id: str,
    requester: UserPublic,
    filename: str = None,
    file_content: bytes = None
) -> DocumentProcessingState:
    """
    Función principal para procesar un documento usando el graph de LangGraph.
    
    Args:
        operation: Tipo de operación a realizar
        docfile_id: ID del documento a procesar
        requester: Usuario que solicita el procesamiento
        filename: Nombre del archivo (requerido para complete_process)
        file_content: Contenido del archivo (requerido para complete_process)
        
    Returns:
        DocumentProcessingState: Estado final del procesamiento
    """
    # Crear estado inicial
    initial_state: DocumentProcessingState = {
        "docfile_id": docfile_id,
        "requester": requester,
        "operation": operation,
        "filename": filename,
        "file_content": file_content,
        "pages": None,
        "total_pages": None,
        "stop": None,
        "balance_data": None,
        "income_data": None,
        "company_info": None,
        "progress": 0.0,
        "error_message": None,
        "current_user": None,
        "_next_node": None
    }
    
    # Crear y ejecutar el graph
    graph = create_document_processing_graph()
    
    try:
        # Ejecutar el graph
        final_state = await graph.ainvoke(initial_state)
        return final_state
        
    except Exception as e:
        logger.error(f"Error ejecutando graph para documento {docfile_id}: {str(e)}")
        return {
            **initial_state,
            "error_message": f"Error en ejecución del graph: {str(e)}"
        }


# ------------------------------------------------------------------------------------
# INSTANCIA GLOBAL DEL GRAPH (OPCIONAL)
# ------------------------------------------------------------------------------------
# Se puede crear una instancia global si se prefiere reutilizar el graph compilado
_document_processing_graph = None


def get_document_processing_graph():
    """
    Obtiene la instancia global del graph (patrón singleton).
    
    Returns:
        Graph: Instancia compilada del graph
    """
    global _document_processing_graph
    if _document_processing_graph is None:
        _document_processing_graph = create_document_processing_graph()
    return _document_processing_graph


# ------------------------------------------------------------------------------------
# INICIALIZACIÓN DEL GRAPH
# ------------------------------------------------------------------------------------
# Inicializar el graph global para facilitar imports
document_graph = get_document_processing_graph()