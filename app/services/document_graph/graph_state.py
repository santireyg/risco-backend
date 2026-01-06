# ------------------------------------------------------------------------------------
# GRAPH STATE DEFINITION - LangGraph State para Procesamiento de Documentos
# ------------------------------------------------------------------------------------
"""
Definición del estado centralizado para el sistema de procesamiento de documentos
basado en LangGraph. Reemplaza el sistema de params distribuido usado anteriormente.
"""

from typing import TypedDict, Optional, List, Literal, Any
from app.models.users import UserPublic
from app.models.docs import Page
from app.models.docs_company_info import CompanyInfo


class DocumentProcessingState(TypedDict):
    """
    Estado centralizado para el procesamiento de documentos.
    
    Reemplaza el sistema anterior de params con un estado tipado que incluye
    todos los datos necesarios para el flujo completo de procesamiento.
    """
    
    # ------------------------------------------------------------------------------------
    # DATOS DE ENTRADA OBLIGATORIOS
    # ------------------------------------------------------------------------------------
    docfile_id: str                    # ID del documento en MongoDB
    requester: UserPublic              # Usuario que solicita el procesamiento (reemplaza current_user dict)
    
    # ------------------------------------------------------------------------------------
    # PARÁMETROS DE OPERACIÓN
    # ------------------------------------------------------------------------------------
    operation: Literal[
        "validate",           # Solo validación
        "extract",           # Extracción y validación
        "recognize_extract", # Reconocimiento, extracción y validación
        "complete_process"   # Proceso completo: upload → recognize → extract → validate
    ]
    
    # ------------------------------------------------------------------------------------
    # DATOS ESPECÍFICOS PARA COMPLETE_PROCESS
    # ------------------------------------------------------------------------------------
    filename: Optional[str]            # Nombre del archivo original (requerido para complete_process)
    file_content: Optional[bytes]      # Contenido del archivo PDF (requerido para complete_process)
    
    # ------------------------------------------------------------------------------------
    # ESTADO DEL PROCESAMIENTO
    # ------------------------------------------------------------------------------------
    pages: Optional[List[Page]]        # Páginas procesadas del documento
    total_pages: Optional[int]         # Número total de páginas
    stop: Optional[bool]               # Flag para detener procesamiento (usado en validaciones)
    
    # ------------------------------------------------------------------------------------
    # DATOS EXTRAÍDOS (MODELOS DINÁMICOS POR TENANT)
    # ------------------------------------------------------------------------------------
    balance_data: Optional[Any]                 # Datos del Estado de Situación Patrimonial (modelo dinámico)
    income_data: Optional[Any]                  # Datos del Estado de Resultados (modelo dinámico)
    company_info: Optional[CompanyInfo]         # Información de la empresa
    
    # ------------------------------------------------------------------------------------
    # METADATOS Y CONTROL DE ERRORES
    # ------------------------------------------------------------------------------------
    progress: Optional[float]          # Progreso actual del procesamiento (0.0 - 1.0)
    error_message: Optional[str]       # Mensaje de error si algo falla
    
    # ------------------------------------------------------------------------------------
    # COMPATIBILIDAD CON SISTEMA ACTUAL
    # ------------------------------------------------------------------------------------
    # Estos campos mantienen compatibilidad con funciones existentes que esperan
    # ciertos campos en el params dict
    current_user: Optional[dict]       # Conversión del UserPublic para compatibilidad legacy
    
    # ------------------------------------------------------------------------------------
    # MULTI-TENANT
    # ------------------------------------------------------------------------------------
    tenant_id: str                     # Identificador del tenant al que pertenece el documento
    
    # ------------------------------------------------------------------------------------
    # CAMPOS INTERNOS DEL GRAPH
    # ------------------------------------------------------------------------------------
    _next_node: Optional[str]          # Campo interno para enrutamiento del graph