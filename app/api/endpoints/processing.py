# app/api/endpoints/processing.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Request
from typing import List
from bson import ObjectId
from app.core.database import docs_collection
from app.services.task_queue import enqueue_graph_processing
from app.core.auth import get_current_user
from app.models.users import User, UserPublic
from app.models.docs import DocFile
import logging
from app.core.limiter import limiter
from app.utils.advanced_memory_tracker import advanced_memory_monitor
import gc

router = APIRouter()


# -------------------------------------------------------------------------------------
# COMPLETE PROCESS BATCH: Upload, Convert, Recognize y Extract de múltiples archivos
# -------------------------------------------------------------------------------------
@router.post("/complete_process_batch/", response_model=dict)
@limiter.limit("3/minute")
@advanced_memory_monitor("complete_process_batch_endpoint")
async def complete_process_batch_task(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="No se pueden subir más de 5 archivos por vez.")
    
    docfile_ids = []
    
    try:
        for file in files:
            file_content = await file.read()
            
            # Crea DocFile inmediatamente
            docfile = DocFile(
                name=file.filename,
                uploaded_by=f"{current_user.first_name} {current_user.last_name}",
                status="En cola",
                progress=0
            )
            docfile_db = await docs_collection.insert_one(docfile.model_dump(by_alias=True))
            docfile_id = str(docfile_db.inserted_id)
            docfile_ids.append(docfile_id)
            
            # Log información detallada para tracking
            logging.info(f"[BATCH_PROCESS] Encolando archivo: {file.filename} - "
                        f"DocID: {docfile_id} - Tamaño: {len(file_content)} bytes")
            
            # Convertir User a UserPublic para el sistema LangGraph
            requester = UserPublic(**current_user.model_dump())
            
            # Encolar directamente en el sistema LangGraph unificado
            await enqueue_graph_processing(
                operation="complete_process",
                docfile_id=docfile_id,
                requester=requester,
                filename=file.filename,
                file_content=file_content
            )
            
            # Liberar memoria inmediatamente después de encolar
            del file_content
            gc.collect()
        
        return {"message": "Los documentos están siendo procesados.", "docfile_ids": docfile_ids}
        
    except Exception as e:
        logging.error(f"[BATCH_PROCESS] Error procesando batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando archivos: {str(e)}")
    finally:
        # Forzar limpieza final
        gc.collect()


# -------------------------------------------------------------------------------------
# RECOGNIZE AND EXTRACT: Recognize y Extract (y Validate) de un archivo según su ID
# -------------------------------------------------------------------------------------
@router.post("/recognize_and_extract/{docfile_id}", response_model=dict,
             summary="Reconocer y extraer datos",
             description="Endpoint para iniciar el reconocimiento de páginas y la extracción de datos (Balance y Estado de Resultados) de un documento."
             )
@limiter.limit("5/minute")
async def recognize_and_extract_task(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    try:
        # Convertir User a UserPublic
        requester = UserPublic(**current_user.model_dump())
        
        # Cambiar status a "En cola" inmediatamente
        await docs_collection.update_one(
            {"_id": ObjectId(docfile_id)},
            {"$set": {"status": "En cola"}}
        )
        
        # Encolar tarea en el sistema de colas unificado
        await enqueue_graph_processing(
            operation="recognize_extract",
            docfile_id=docfile_id,
            requester=requester
        )

    except Exception as e:
        logging.error(f"Error al procesar el archivo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    
    return {
        "message": "El documento está siendo procesado en segundo plano.",
        "docfile_id": docfile_id,
    }


# -------------------------------------------------------------------------------------
# EXTRACT: Extract (y Validate) de un archivo según su ID
# -------------------------------------------------------------------------------------
@router.post("/extract/{docfile_id}", response_model=dict,)
@limiter.limit("5/minute")
async def extract_task(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    try:
        # Convertir User a UserPublic
        requester = UserPublic(**current_user.model_dump())
        
        # Cambiar status a "En cola" inmediatamente
        await docs_collection.update_one(
            {"_id": ObjectId(docfile_id)},
            {"$set": {"status": "En cola"}}
        )
        
        # Encolar tarea en el sistema de colas unificado
        await enqueue_graph_processing(
            operation="extract",
            docfile_id=docfile_id,
            requester=requester
        )

    except Exception as e:
        logging.error(f"Error al extraer el archivo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al extraer el archivo: {str(e)}")
    
    return {
        "message": "El documento está siendo procesado en segundo plano.",
        "docfile_id": docfile_id,
    }



# Endpoint para realizar la validación de datos en un documento
@router.post("/validate_data/{docfile_id}")
@limiter.limit("10/minute")
async def validate_task(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    try:
        # Convertir User a UserPublic
        requester = UserPublic(**current_user.model_dump())
        
        # Cambiar status a "En cola" inmediatamente
        await docs_collection.update_one(
            {"_id": ObjectId(docfile_id)},
            {"$set": {"status": "En cola"}}
        )
        
        # Encolar tarea en el sistema de colas unificado
        await enqueue_graph_processing(
            operation="validate",
            docfile_id=docfile_id,
            requester=requester
        )
        
    except Exception as e:
        logging.error(f"Error al validar datos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al validar datos {str(e)}")
    return {
        "message": "La validación de datos está en proceso.",
        "docfile_id": docfile_id,
    }


# -------------------------------------------------------------------------------------
# GENERATE REPORT: Genera un reporte financiero a partir de un balance analizado
# -------------------------------------------------------------------------------------
@router.post("/generate_report/{docfile_id}", response_model=dict,
             summary="Generar reporte financiero",
             description="Genera un reporte financiero con indicadores y datos del BCRA a partir de un documento de balance analizado."
             )
@limiter.limit("5/minute")
async def generate_report_task(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Genera un reporte financiero a partir de un documento de balance analizado.
    
    El reporte incluye:
    - Información de la empresa
    - 8 indicadores financieros (KPIs)
    - Datos del BCRA (deudas, historial, cheques rechazados)
    """
    from app.services.task_queue import enqueue_report_processing
    
    try:
        # Verificar que el documento existe y pertenece al tenant del usuario
        document = await docs_collection.find_one({
            "_id": ObjectId(docfile_id),
            "tenant_id": current_user.tenant_id
        })
        
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        # Verificar que el documento está analizado
        if document.get("status") != "Analizado":
            raise HTTPException(
                status_code=400, 
                detail=f"El documento debe estar en estado 'Analizado' para generar un reporte. Estado actual: {document.get('status')}"
            )
        
        # Convertir User a UserPublic
        requester = UserPublic(**current_user.model_dump())
        
        # Encolar tarea de generación de reporte
        await enqueue_report_processing(
            docfile_id=docfile_id,
            requester=requester
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error al generar reporte: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar reporte: {str(e)}")
    
    return {
        "message": "El reporte está siendo generado en segundo plano.",
        "docfile_id": docfile_id,
    }

