# path: app/services/task_queue.py

import asyncio
from app.models.users import UserPublic
from app.utils.advanced_memory_tracker import advanced_memory_monitor, advanced_memory_tracker
import logging
import gc
import tracemalloc
from typing import Literal, Optional

# Importes para LangGraph
from app.services.graph_definition import process_document

# ------------------------------------------------------------------------------------
# SISTEMA DE COLAS UNIFICADO PARA LANGGRAPH
# ------------------------------------------------------------------------------------

# Cola unificada para todas las operaciones del graph
graph_queue = asyncio.Queue()

@advanced_memory_monitor("enqueue_graph_processing")
async def enqueue_graph_processing(
    operation: Literal["validate", "extract", "recognize_extract", "complete_process"],
    docfile_id: str,
    requester: UserPublic,
    filename: Optional[str] = None,
    file_content: Optional[bytes] = None
):
    """
    Encola una tarea de procesamiento del graph con la operación especificada.
    
    Esta función unifica el sistema de colas para todas las operaciones de procesamiento,
    reemplazando el uso directo de background tasks en los endpoints.
    
    Args:
        operation: Tipo de operación ("validate", "extract", "recognize_extract", "complete_process")
        docfile_id: ID del documento a procesar
        requester: Usuario que solicita el procesamiento
        filename: Nombre del archivo (requerido solo para complete_process)
        file_content: Contenido del archivo (requerido solo para complete_process)
    """
    try:
        # Validaciones específicas por operación
        if operation == "complete_process":
            if not filename or not file_content:
                raise ValueError("complete_process requiere filename y file_content")
        
        # Crear tupla con los datos de la tarea
        task_data = (operation, docfile_id, requester, filename, file_content)
        
        await graph_queue.put(task_data)
        
        # Log detallado del encolado
        file_size_info = ""
        if file_content:
            file_size_mb = len(file_content) / (1024 * 1024)
            file_size_info = f" - Tamaño: {file_size_mb:.2f}MB"
        
        logging.info(f"[GRAPH_QUEUE] Tarea encolada: {operation} - {docfile_id}{file_size_info}")
        
        # Log estado de la cola
        queue_size = graph_queue.qsize()
        logging.info(f"[GRAPH_QUEUE] Tamaño actual de cola: {queue_size}")
        
    except Exception as e:
        logging.error(f"[GRAPH_QUEUE] Error encolando tarea {operation} para documento {docfile_id}: {e}")
        raise


@advanced_memory_monitor("graph_worker")
async def graph_worker():
    """
    Worker asíncrono unificado para procesar tareas del graph de LangGraph.
    
    Este worker reemplaza el uso de background tasks directos y procesa diferentes
    tipos de operaciones usando el sistema LangGraph con tracking de memoria avanzado.
    """
    tracking_status = "habilitado" if advanced_memory_tracker.enabled else "deshabilitado"
    logging.info(f"[GRAPH_QUEUE] Worker LangGraph iniciado con tracking de memoria {tracking_status}...")
    
    while True:
        operation = None
        docfile_id = None
        filename = None
        file_content = None
        requester = None
        
        try:
            # Obtener tarea de la cola
            operation, docfile_id, requester, filename, file_content = await graph_queue.get()
            
            # Log detallado del inicio
            file_size_info = ""
            if file_content:
                file_size_mb = len(file_content) / (1024 * 1024)
                file_size_info = f" - Tamaño: {file_size_mb:.2f}MB"
            
            logging.info(f"[GRAPH_QUEUE] Iniciando procesamiento: {operation} - {docfile_id}{file_size_info}")
            
            # Obtener memoria inicial para este documento específico
            if tracemalloc.is_tracing():
                start_snapshot = tracemalloc.take_snapshot()
                logging.info(f"[GRAPH_QUEUE] Snapshot inicial tomado para {docfile_id}")
            
            # Procesar documento usando LangGraph
            final_state = await process_document(
                operation=operation,
                docfile_id=docfile_id,
                requester=requester,
                filename=filename,
                file_content=file_content
            )
            
            # Verificar si hubo errores
            if final_state.get("error_message"):
                logging.error(f"[GRAPH_QUEUE] Error en procesamiento de {docfile_id}: {final_state['error_message']}")
            else:
                logging.info(f"[GRAPH_QUEUE] Procesamiento exitoso de {docfile_id}")
            
            # Tomar snapshot final y analizar leaks
            if tracemalloc.is_tracing():
                end_snapshot = tracemalloc.take_snapshot()
                
                # Solo analizar leaks si tracking está habilitado
                if advanced_memory_tracker.enabled:
                    top_stats = end_snapshot.compare_to(start_snapshot, 'traceback')
                    significant_leaks = [stat for stat in top_stats[:5] 
                                       if stat.size_diff > 5 * 1024 * 1024]  # > 5MB
                    
                    if significant_leaks:
                        logging.warning(f"[GRAPH_QUEUE] LEAKS DETECTADOS en {docfile_id}:")
                        for i, stat in enumerate(significant_leaks):
                            size_mb = stat.size_diff / (1024 * 1024)
                            logging.warning(f"  Leak {i+1}: {size_mb:.2f}MB")
                            if logging.getLogger().level <= logging.DEBUG:
                                logging.debug(f"  Traceback:\n{''.join(stat.traceback.format())}")
                    else:
                        logging.info(f"[GRAPH_QUEUE] Procesamiento limpio para {docfile_id}")
            
            logging.info(f"[GRAPH_QUEUE] Procesamiento completado: {operation} - {docfile_id}")
            
        except Exception as e:
            logging.error(f"[GRAPH_QUEUE] Error procesando {operation} - {docfile_id}: {e}")
            
        finally:
            # Limpieza agresiva de memoria
            try:
                # Log antes de liberar variables
                if docfile_id and operation:
                    # Solo loggear memoria si tracking está habilitado
                    if advanced_memory_tracker.enabled:
                        logging.info(f"[GRAPH_QUEUE] Iniciando limpieza de memoria para: {operation} - {docfile_id}")
                
                # Liberar variables explícitamente
                if file_content:
                    del file_content
                if filename:
                    del filename
                if requester:
                    del requester
                if operation:
                    operation_temp = operation
                    del operation
                if docfile_id:
                    docfile_id_temp = docfile_id
                    del docfile_id
                
                # Múltiples rondas de garbage collection
                for i in range(3):
                    collected = gc.collect()
                    if advanced_memory_tracker.enabled and collected > 0:
                        logging.debug(f"[GRAPH_QUEUE] GC ronda {i+1}: {collected} objetos liberados")
                
                # Log memoria después de limpieza si tracking está habilitado
                if advanced_memory_tracker.enabled:
                    try:
                        import psutil
                        current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
                        logging.info(f"[GRAPH_QUEUE] Memoria después de limpieza ({operation_temp} - {docfile_id_temp}): {current_memory:.2f}MB")
                    except:
                        pass
                
            except Exception as cleanup_error:
                logging.error(f"[GRAPH_QUEUE] Error en limpieza de memoria: {cleanup_error}")
            
            # Marcar tarea como completada
            graph_queue.task_done()


def start_graph_worker_loop():
    """Inicia el worker loop para el procesamiento LangGraph."""
    loop = asyncio.get_event_loop()
    loop.create_task(graph_worker())
