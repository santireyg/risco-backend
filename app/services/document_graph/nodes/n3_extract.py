from bson import ObjectId
import gc

from app.core.database import docs_collection
from app.utils.status_notifier import update_status

# Importes para LangGraph
from app.services.document_graph.graph_state import DocumentProcessingState

# Imports de LangChain legacy eliminados
from app.services.document_graph.nodes.n3_extract_balance import extract_balance
from app.services.document_graph.nodes.n3_extract_income import extract_income
from app.services.document_graph.nodes.n3_extract_company_info import extract_company_info
# TimingCallbackHandler legacy eliminado
from app.utils.memory_cleanup import try_malloc_trim  ##🧹 MALLOC_TRIM para extract

# Colección de documentos sobre la que vamos a trabajar
collection = docs_collection


# ------------------------------------------------------------------------------------
# FUNCIÓN 1: VERIFICA EXISTENCIA DE PÁGINAS RELEVANTES (ESP Y ER)
# ------------------------------------------------------------------------------------
async def check_relevant_pages(state: DocumentProcessingState) -> DocumentProcessingState:
    """Verifica si hay páginas relevantes (ESP o ER) para realizar extracción."""
    # Este fragmento verifica si el pipeline debe detenerse si no hay páginas relevantes (ESP o ER)
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)

    # Obtener el documento desde la base de datos
    doc = await collection.find_one({"_id": ObjectId(docfile_id)})

    pages = doc["pages"]
    has_balance = any(p.get("recognized_info", {}).get("is_balance_sheet") for p in pages)
    has_income = any(p.get("recognized_info", {}).get("is_income_statement_sheet") for p in pages)

    if not (has_balance or has_income):
        # Si no hay páginas de ER o ESP detectadas, marcar el pipeline como detenido
        updated_state = state.copy()
        updated_state.update({
            "stop": True  # Marca el pipeline como detenido
        })
        return updated_state

    # Continuar normalmente si hay páginas relevantes
    return state


# ------------------------------------------------------------------------------------
# FUNCIÓN 2: ACTUALIZA EL STATUS A "ANALIZANDO" (SETEA STATUS INICIAL DE EXTRACCIÓN)
# ------------------------------------------------------------------------------------
async def update_status_init(state: DocumentProcessingState) -> DocumentProcessingState:
    """Actualiza el status del documento a 'Analizando' al iniciar extracción."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state

    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)
    # Update Status: Analizando
    await update_status(collection, docfile_id, "Analizando", user_id, progress=0, send_progress_ws=True)
    return state


# ------------------------------------------------------------------------------------
# FUNCIÓN 3: EJECUTA EXTRACCIONES EN PARALELO
# ------------------------------------------------------------------------------------
async def extract_parallel(state: DocumentProcessingState) -> DocumentProcessingState:
    """Ejecuta las extracciones de balance, estado de resultados e info de empresa en paralelo."""
    import asyncio
    
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)
    
    try:
        # Reportar progreso inicial (33%)
        await update_status(collection, docfile_id, "Analizando", user_id, progress=33, update_db=False, send_progress_ws=True)
        
        # Ejecutar las tres extracciones en paralelo
        balance_task = extract_balance(state)
        income_task = extract_income(state)
        company_info_task = extract_company_info(state)
        
        # Esperar a que todas las tareas terminen
        balance_result, income_result, company_info_result = await asyncio.gather(
            balance_task, income_task, company_info_task
        )
        
        # Reportar progreso intermedio (66%)
        await update_status(collection, docfile_id, "Analizando", user_id, progress=66, update_db=False, send_progress_ws=True)
        
        # Consolidar resultados en el estado principal
        updated_state = state.copy()
        
        # Verificar si alguna extracción tuvo errores
        if balance_result.get("error_message") or income_result.get("error_message") or company_info_result.get("error_message"):
            error_messages = []
            if balance_result.get("error_message"):
                error_messages.append(f"Balance: {balance_result['error_message']}")
            if income_result.get("error_message"):
                error_messages.append(f"Income: {income_result['error_message']}")
            if company_info_result.get("error_message"):
                error_messages.append(f"Company Info: {company_info_result['error_message']}")
            
            return {**state, "error_message": "; ".join(error_messages)}
        
        # Consolidar datos extraídos
        updated_state.update({
            "balance_date": balance_result.get("balance_date"),
            "balance_date_previous": balance_result.get("balance_date_previous"),
            "extracted_company_info": company_info_result.get("extracted_company_info"),
        })
        
        return updated_state
        
    except Exception as e:
        import logging
        logging.error(f"Error en extract_parallel: {str(e)}")
        return {**state, "error_message": f"Error en extracciones paralelas: {str(e)}"}


# ------------------------------------------------------------------------------------
# FUNCIÓN 4: ACTUALIZA EL STATUS A "ANALIZADO" (SETEA STATUS FINAL DE EXTRACCIÓN)
# ------------------------------------------------------------------------------------
async def update_status_complete(state: DocumentProcessingState) -> DocumentProcessingState:
    """Actualiza el status final del documento a 'Analizado' con los datos extraídos."""
    # Si alguna extracción falló, manejar el error
    if state.get("error_message"):
        return state
    
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)
    
    balance_date = state.get("balance_date")
    company_info = state.get("extracted_company_info")

    # Update Status: Analizado
    await update_status(collection, docfile_id, "Analizado", user_id, progress=100, balance_date=balance_date, company_info=company_info, send_progress_ws=True)
    
    # Forzar garbage collection al final del procesamiento de extracción
    gc.collect()
    
    # 🧹🔥 MALLOC_TRIM después de extracción LLM - combatir memoria zombie
    try_malloc_trim()
    
    return state



# ------------------------------------------------------------------------------------
# NODO LANGGRAPH: EXTRACT NODE
# ------------------------------------------------------------------------------------
async def extract_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo LangGraph para extracción de datos contables.
    
    Ejecuta el proceso completo de:
    1. Verificación de páginas relevantes (ESP/ER)
    2. Extracción paralela de balance, estado de resultados e info de empresa
    3. Actualización del documento en MongoDB con datos extraídos
    
    Args:
        state: Estado actual del procesamiento
        
    Returns:
        DocumentProcessingState: Estado actualizado con datos extraídos
    """
    import logging
    import time
    from app.models.docs_processing_time import ProcessingTime
    
    # Iniciar tracking de tiempo
    start_time = time.perf_counter()
    
    try:
        # PASO 1: Verificar páginas relevantes
        state = await check_relevant_pages(state)
        if state.get("stop"):
            return {**state, "error_message": "No se encontraron páginas relevantes (ESP/ER)"}
        
        # PASO 2: Actualizar status inicial
        state = await update_status_init(state)
        
        # PASO 3: Ejecutar extracciones en paralelo
        state = await extract_parallel(state)
        if state.get("error_message"):
            return state
        
        # PASO 4: Completar actualización de status
        state = await update_status_complete(state)
        
        # Obtener datos actualizados del documento para el estado final
        doc = await collection.find_one({"_id": ObjectId(state["docfile_id"])})
        if not doc:
            return {**state, "error_message": "Documento no encontrado después de extracción"}
        
        # Calcular duración
        duration = time.perf_counter() - start_time
        
        # Actualizar processing_time en la BD y notificar vía WebSocket
        docfile_id = state.get("docfile_id")
        requester = state.get("requester")
        if docfile_id and requester:
            user_id = str(requester.id)
            try:
                # Obtener o crear processing_time
                processing_time_data = doc.get("processing_time", {})
                processing_time = ProcessingTime(**processing_time_data) if processing_time_data else ProcessingTime()
                
                # Actualizar el tiempo de extract
                processing_time.extract = duration
                processing_time.update_total()
                
                # Guardar en BD y notificar vía WebSocket
                from app.utils.status_notifier import update_status
                current_status = doc.get("status", "Procesando")
                await update_status(
                    collection=collection,
                    docfile_id=docfile_id,
                    new_status=current_status,
                    user_id=user_id,
                    processing_time=processing_time.model_dump(),
                    update_db=True
                )
                
                logging.info(f"Tiempo extract para {docfile_id}: {duration:.2f}s - Notificado vía WebSocket")
            except Exception as e:
                logging.error(f"Error actualizando processing_time para extract: {e}")
        
        # Actualizar estado con datos extraídos de la BD
        updated_state = state.copy()
        updated_state.update({
            "balance_data": doc.get("balance_data"),
            "income_data": doc.get("income_statement_data"),
            "company_info": doc.get("company_info"),
        })
        
        return updated_state
        
    except Exception as e:
        logging.error(f"Error en extract_node: {str(e)}")
        return {**state, "error_message": f"Error en extracción: {str(e)}"}
