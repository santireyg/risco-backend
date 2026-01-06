# ------------------------------------------------------------------------------------
# REPORT GRAPH DEFINITION - Sistema de Generación de Reportes con LangGraph
# ------------------------------------------------------------------------------------
"""
Sistema de generación de reportes financieros basado en LangGraph.
Procesa documentos de balances ya analizados para crear reportes con:
- Información de la empresa
- Indicadores financieros
- Datos del BCRA (deudas, historial, cheques rechazados)
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, END

from app.services.report_graph.graph_state import ReportProcessingState
from app.services.report_graph.nodes.n0_start_end import start_node, end_node, error_node
from app.services.report_graph.nodes.n1_create_report_object import create_report_object_node
from app.services.report_graph.nodes.n2_calculate_indicators import calculate_indicators_node
from app.services.report_graph.nodes.n3_get_bcra_data import get_bcra_data_node
from app.services.report_graph.nodes.n4_generate_ai_report import generate_ai_report_node
from app.models.users import UserPublic

logger = logging.getLogger(__name__)

# Variable global para instancia del graph (patrón singleton)
_report_processing_graph = None


# ------------------------------------------------------------------------------------
# FUNCIONES DE ENRUTAMIENTO
# ------------------------------------------------------------------------------------
def route_after_start(state: ReportProcessingState) -> str:
    """Enrutamiento después del nodo start."""
    if state.get("error_message"):
        return "error_node"
    return "create_report_object_node"


def route_after_create_report(state: ReportProcessingState) -> str:
    """Enrutamiento después de crear el objeto reporte."""
    if state.get("error_message"):
        return "error_node"
    return "calculate_indicators_node"


def route_after_indicators(state: ReportProcessingState) -> str:
    """Enrutamiento después de calcular indicadores."""
    if state.get("error_message"):
        return "error_node"
    return "get_bcra_data_node"


def route_after_bcra(state: ReportProcessingState) -> str:
    """Enrutamiento después de obtener datos BCRA."""
    if state.get("error_message"):
        return "error_node"
    return "generate_ai_report_node"


def route_after_ai_report(state: ReportProcessingState) -> str:
    """Enrutamiento después de generar reporte IA."""
    if state.get("error_message"):
        return "error_node"
    return "end_node"


def route_from_error(state: ReportProcessingState) -> str:
    """Enrutamiento desde error - siempre va a end."""
    return "end_node"


# ------------------------------------------------------------------------------------
# CREACIÓN DEL GRAPH
# ------------------------------------------------------------------------------------
def create_report_processing_graph():
    """
    Crea y configura el graph de generación de reportes.
    
    Returns:
        Graph: Graph compilado listo para usar
    """
    # Crear el graph con el estado tipado
    graph = StateGraph(ReportProcessingState)
    
    # ------------------------------------------------------------------------------------
    # AGREGAR NODOS
    # ------------------------------------------------------------------------------------
    graph.add_node("start_node", start_node)
    graph.add_node("create_report_object_node", create_report_object_node)
    graph.add_node("calculate_indicators_node", calculate_indicators_node)
    graph.add_node("get_bcra_data_node", get_bcra_data_node)
    graph.add_node("generate_ai_report_node", generate_ai_report_node)
    graph.add_node("error_node", error_node)
    graph.add_node("end_node", end_node)
    
    # ------------------------------------------------------------------------------------
    # DEFINIR FLUJO
    # ------------------------------------------------------------------------------------
    
    # Entrada del graph
    graph.set_entry_point("start_node")
    
    # Flujo lineal con manejo de errores
    graph.add_conditional_edges(
        "start_node",
        route_after_start,
        {
            "create_report_object_node": "create_report_object_node",
            "error_node": "error_node"
        }
    )
    
    graph.add_conditional_edges(
        "create_report_object_node",
        route_after_create_report,
        {
            "calculate_indicators_node": "calculate_indicators_node",
            "error_node": "error_node"
        }
    )
    
    graph.add_conditional_edges(
        "calculate_indicators_node",
        route_after_indicators,
        {
            "get_bcra_data_node": "get_bcra_data_node",
            "error_node": "error_node"
        }
    )
    
    graph.add_conditional_edges(
        "get_bcra_data_node",
        route_after_bcra,
        {
            "generate_ai_report_node": "generate_ai_report_node",
            "error_node": "error_node"
        }
    )
    
    graph.add_conditional_edges(
        "generate_ai_report_node",
        route_after_ai_report,
        {
            "end_node": "end_node",
            "error_node": "error_node"
        }
    )
    
    graph.add_conditional_edges(
        "error_node",
        route_from_error,
        {
            "end_node": "end_node"
        }
    )
    
    # Finalización del graph
    graph.add_edge("end_node", END)
    
    # Compilar el graph
    compiled_graph = graph.compile()
    
    logger.info("Graph de generación de reportes creado y compilado exitosamente")
    
    return compiled_graph


# ------------------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# ------------------------------------------------------------------------------------
async def process_report(
    docfile_id: str,
    requester: UserPublic
) -> ReportProcessingState:
    """
    Función principal para generar un reporte usando el graph de LangGraph.
    
    Args:
        docfile_id: ID del documento (balance) a partir del cual generar el reporte
        requester: Usuario que solicita el reporte
        
    Returns:
        ReportProcessingState: Estado final del procesamiento
    """
    # Obtener tenant_id del usuario
    tenant_id = getattr(requester, "tenant_id", "default")
    
    # Crear estado inicial
    initial_state: ReportProcessingState = {
        "docfile_id": docfile_id,
        "requester": requester,
        "report_id": None,
        "tenant_id": tenant_id,
        "docfile": None,
        "indicators": None,
        "bcra_data": None,
        "ai_report": None,
        "progress": 0.0,
        "error_message": None,
        "_next_node": None
    }
    
    # Crear y ejecutar el graph
    graph = create_report_processing_graph()
    
    try:
        # Ejecutar el graph
        final_state = await graph.ainvoke(initial_state)
        return final_state
        
    except Exception as e:
        logger.error(f"Error ejecutando graph de reporte para documento {docfile_id}: {str(e)}")
        return {
            **initial_state,
            "error_message": f"Error en ejecución del graph de reporte: {str(e)}"
        }


# ------------------------------------------------------------------------------------
# INSTANCIA GLOBAL DEL GRAPH (SINGLETON)
# ------------------------------------------------------------------------------------
def get_report_processing_graph():
    """
    Obtiene la instancia global del graph (patrón singleton).
    
    Returns:
        Graph: Instancia compilada del graph
    """
    global _report_processing_graph
    if _report_processing_graph is None:
        _report_processing_graph = create_report_processing_graph()
    return _report_processing_graph


# ------------------------------------------------------------------------------------
# INICIALIZACIÓN
# ------------------------------------------------------------------------------------
report_graph = get_report_processing_graph()
