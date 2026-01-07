# ------------------------------------------------------------------------------------
# REPORT GRAPH STATE - Estado para el Graph de Generación de Reportes
# ------------------------------------------------------------------------------------
"""
Definición del estado para el sistema de generación de reportes
basado en LangGraph.
"""

from typing import TypedDict, Optional, List, Any, Dict
from app.models.users import UserPublic


class ReportProcessingState(TypedDict):
    """
    Estado centralizado para la generación de reportes financieros.
    """
    
    # ------------------------------------------------------------------------------------
    # DATOS DE ENTRADA OBLIGATORIOS
    # ------------------------------------------------------------------------------------
    docfile_id: str                    # ID del documento (balance) en MongoDB
    requester: UserPublic              # Usuario que solicita el reporte
    
    # ------------------------------------------------------------------------------------
    # DATOS DE CONTROL
    # ------------------------------------------------------------------------------------
    report_id: Optional[str]           # ID del reporte creado en MongoDB
    tenant_id: str                     # Tenant al que pertenece el documento
    
    # ------------------------------------------------------------------------------------
    # DATOS OBTENIDOS DEL DOCFILE
    # ------------------------------------------------------------------------------------
    docfile: Optional[Dict[str, Any]]  # Documento completo de MongoDB
    
    # ------------------------------------------------------------------------------------
    # DATOS CALCULADOS
    # ------------------------------------------------------------------------------------
    indicators: Optional[List[Dict[str, Any]]]  # Indicadores calculados
    bcra_data: Optional[Dict[str, Any]]         # Datos del BCRA
    ai_report: Optional[Dict[str, Any]]         # Reporte de IA generado
    
    # ------------------------------------------------------------------------------------
    # ESTADO DEL PROCESAMIENTO
    # ------------------------------------------------------------------------------------
    progress: Optional[float]          # Progreso actual (0.0 - 1.0)
    error_message: Optional[str]       # Mensaje de error si algo falla
    start_time: Optional[float]        # Timestamp de inicio del procesamiento (para medir duración)
    
    # ------------------------------------------------------------------------------------
    # CAMPOS INTERNOS DEL GRAPH
    # ------------------------------------------------------------------------------------
    _next_node: Optional[str]          # Campo interno para enrutamiento
