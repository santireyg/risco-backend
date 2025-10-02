# ------------------------------------------------------------------------------------
# GRAPH ROUTER - Lógica de Enrutamiento para LangGraph
# ------------------------------------------------------------------------------------
"""
Sistema de enrutamiento inteligente para el procesamiento de documentos.
Determina la secuencia de ejecución basada en la operación solicitada y 
valida que el estado tenga los datos requeridos para cada operación.
"""

from app.services.graph_state import DocumentProcessingState
from app.core.database import docs_collection
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------
# ENRUTADOR PRINCIPAL
# ------------------------------------------------------------------------------------
async def route_operation(state: DocumentProcessingState) -> str:
    """
    Enruta la ejecución basada en la operación solicitada.
    
    Determina cuál debe ser el siguiente nodo en el graph basado en:
    1. El tipo de operación solicitada
    2. Las validaciones de estado requeridas
    3. La disponibilidad de datos en el documento
    
    Args:
        state: Estado actual del procesamiento
        
    Returns:
        str: Nombre del próximo nodo a ejecutar
    """
    operation = state["operation"]
    
    try:
        # Validar que el docfile_id exista
        if not await _validate_docfile_exists(state["docfile_id"]):
            logger.error(f"Documento {state['docfile_id']} no encontrado")
            return "error_node"
        
        # Enrutamiento basado en operación
        if operation == "complete_process":
            return await _route_complete_process(state)
        elif operation == "recognize_extract":
            return await _route_recognize_extract(state)
        elif operation == "extract":
            return await _route_extract(state)
        elif operation == "validate":
            return await _route_validate(state)
        else:
            logger.error(f"Operación desconocida: {operation}")
            return "error_node"
            
    except Exception as e:
        logger.error(f"Error en route_operation: {str(e)}")
        return "error_node"


# ------------------------------------------------------------------------------------
# ENRUTADORES ESPECÍFICOS POR OPERACIÓN
# ------------------------------------------------------------------------------------
async def _route_complete_process(state: DocumentProcessingState) -> str:
    """
    Enrutamiento para complete_process.
    Requiere filename y file_content para comenzar con upload_convert.
    """
    if not state.get("filename") or not state.get("file_content"):
        logger.error("complete_process requiere filename y file_content")
        return "error_node"
    
    return "upload_convert_node"


async def _route_recognize_extract(state: DocumentProcessingState) -> str:
    """
    Enrutamiento para recognize_extract.
    Requiere que el documento tenga páginas convertidas (imágenes).
    """
    if not await _validate_pages_converted(state["docfile_id"]):
        logger.error(f"Documento {state['docfile_id']} no tiene páginas convertidas")
        return "error_node"
    
    return "recognize_node"


async def _route_extract(state: DocumentProcessingState) -> str:
    """
    Enrutamiento para extract.
    Requiere que el documento tenga páginas reconocidas (OCR completado).
    """
    if not await _validate_pages_recognized(state["docfile_id"]):
        logger.error(f"Documento {state['docfile_id']} no tiene páginas reconocidas")
        return "error_node"
    
    return "extract_node"


async def _route_validate(state: DocumentProcessingState) -> str:
    """
    Enrutamiento para validate.
    Requiere que el documento tenga datos extraídos.
    """
    if not await _validate_data_extracted(state["docfile_id"]):
        logger.error(f"Documento {state['docfile_id']} no tiene datos extraídos")
        return "error_node"
    
    return "validate_node"


# ------------------------------------------------------------------------------------
# FUNCIONES DE VALIDACIÓN DE ESTADO
# ------------------------------------------------------------------------------------
async def _validate_docfile_exists(docfile_id: str) -> bool:
    """
    Valida que el documento exista en la base de datos.
    
    Args:
        docfile_id: ID del documento a validar
        
    Returns:
        bool: True si el documento existe, False en caso contrario
    """
    try:
        doc = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
        return doc is not None
    except Exception as e:
        logger.error(f"Error validando existencia del documento {docfile_id}: {str(e)}")
        return False


async def _validate_pages_converted(docfile_id: str) -> bool:
    """
    Valida que el documento tenga páginas convertidas a imágenes.
    
    Verifica que:
    1. El documento tenga páginas
    2. Cada página tenga image_path
    
    Args:
        docfile_id: ID del documento a validar
        
    Returns:
        bool: True si tiene páginas convertidas, False en caso contrario
    """
    try:
        doc = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
        if not doc:
            return False
        
        pages = doc.get("pages", [])
        if not pages:
            return False
        
        # Verificar que todas las páginas tengan image_path
        for page in pages:
            if not page.get("image_path"):
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validando páginas convertidas del documento {docfile_id}: {str(e)}")
        return False


async def _validate_pages_recognized(docfile_id: str) -> bool:
    """
    Valida que el documento tenga páginas reconocidas (OCR completado).
    
    Verifica que al menos una página tenga recognized_info.
    
    Args:
        docfile_id: ID del documento a validar
        
    Returns:
        bool: True si tiene páginas reconocidas, False en caso contrario
    """
    try:
        doc = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
        if not doc:
            return False
        
        pages = doc.get("pages", [])
        if not pages:
            return False
        
        # Verificar que al menos una página tenga recognized_info
        for page in pages:
            if page.get("recognized_info"):
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error validando páginas reconocidas del documento {docfile_id}: {str(e)}")
        return False


async def _validate_data_extracted(docfile_id: str) -> bool:
    """
    Valida que el documento tenga datos extraídos.
    
    Verifica que tenga al menos uno de:
    - balance_data
    - income_statement_data
    - company_info
    
    Args:
        docfile_id: ID del documento a validar
        
    Returns:
        bool: True si tiene datos extraídos, False en caso contrario
    """
    try:
        doc = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
        if not doc:
            return False
        
        # Verificar que tenga al menos un tipo de datos extraídos
        has_balance = doc.get("balance_data") is not None
        has_income = doc.get("income_statement_data") is not None
        has_company = doc.get("company_info") is not None
        
        return has_balance or has_income or has_company
        
    except Exception as e:
        logger.error(f"Error validando datos extraídos del documento {docfile_id}: {str(e)}")
        return False


# ------------------------------------------------------------------------------------
# UTILIDADES DE ENRUTAMIENTO
# ------------------------------------------------------------------------------------
def get_operation_description(operation: str) -> str:
    """
    Obtiene una descripción legible de la operación.
    
    Args:
        operation: Nombre de la operación
        
    Returns:
        str: Descripción de la operación
    """
    descriptions = {
        "complete_process": "Proceso completo: subida → reconocimiento → extracción → validación",
        "recognize_extract": "Reconocimiento → extracción → validación",
        "extract": "Extracción → validación",
        "validate": "Solo validación de ecuaciones contables"
    }
    
    return descriptions.get(operation, f"Operación desconocida: {operation}")


def validate_operation_requirements(operation: str, docfile_id: str) -> tuple[bool, str]:
    """
    Valida que un documento cumpla con los requisitos para una operación específica.
    
    Args:
        operation: Tipo de operación a validar
        docfile_id: ID del documento
        
    Returns:
        tuple[bool, str]: (es_válido, mensaje_error)
    """
    if operation == "complete_process":
        # Para complete_process no validamos el documento porque se crea en el proceso
        return True, ""
    
    elif operation == "recognize_extract":
        if _validate_pages_converted(docfile_id):
            return True, ""
        else:
            return False, "El documento debe tener páginas convertidas a imágenes"
    
    elif operation == "extract":
        if _validate_pages_recognized(docfile_id):
            return True, ""
        else:
            return False, "El documento debe tener páginas reconocidas (OCR completado)"
    
    elif operation == "validate":
        if _validate_data_extracted(docfile_id):
            return True, ""
        else:
            return False, "El documento debe tener datos extraídos"
    
    else:
        return False, f"Operación desconocida: {operation}"


# ------------------------------------------------------------------------------------
# NODO ROUTER
# ------------------------------------------------------------------------------------
async def router_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo enrutador que determina el siguiente paso del procesamiento.
    
    Utiliza la lógica de router_operation para determinar qué nodo ejecutar
    basado en la operación solicitada y las validaciones correspondientes.
    
    Args:
        state: Estado actual del procesamiento
        
    Returns:
        DocumentProcessingState: Estado con información de enrutamiento
    """
    try:
        next_node = await route_operation(state)
        logger.info(f"Documento {state['docfile_id']}: Enrutando a {next_node}")
        
        # Agregar información de enrutamiento al estado
        updated_state = state.copy()
        updated_state["_next_node"] = next_node
        return updated_state
        
    except Exception as e:
        logger.error(f"Error en router_node: {str(e)}")
        updated_state = state.copy()
        updated_state["_next_node"] = "error_node"
        updated_state["error_message"] = f"Error en enrutamiento: {str(e)}"
        return updated_state