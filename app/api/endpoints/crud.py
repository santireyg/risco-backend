# app/api/endpoints/crud.py

import asyncio
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel
from math import ceil
from urllib.parse import urlparse
import unicodedata
import re

from app.core.database import docs_collection
from app.models.users import User
from app.core.auth import get_current_user
from app.core.s3_client import get_presigned_url_from_image_path, s3_client, S3_BUCKET_NAME
from app.models.docs import DocFile
from app.services.graph_nodes.n4_validate import validate
from app.services.download_service import get_document_download_url, get_document_filename
from app.main import limiter
from app.utils.accent_regex import build_accent_insensitive_regex

router = APIRouter()

class DocsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[dict]


# -------------------------------------------------------------------------------------
# /documents: ENDPOINT PARA LISTAR LOS DOCUMENTOS Y FILTRARLOS
# -------------------------------------------------------------------------------------
@router.get("/documents", response_model=DocsListResponse, summary="Obtiene documentos procesados")
@limiter.limit("30/minute")
async def list_documents(
    q: Optional[str] = Query(
        None,
        description="Búsqueda por nombre del documento, autor, nombre de empresa o CUIT"
    ),
    status: Optional[str] = Query(
        None,
        description="Filtra los documentos por su status"
    ),
    validation_status: Optional[str] = Query(
        None,
        description="Filtra los documentos por el status de validación"
    ),
    sort_field: Optional[str] = Query(
        "upload_date",
        description="Campo para ordenar (permitidos: id, name, status, upload_date, uploaded_by, balance_date, validation, error_message, company_name)"
    ),
    sort_order: Optional[str] = Query(
        "desc",
        description="Orden de la ordenación: 'asc' o 'desc'"
    ),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(10, ge=1, le=100, description="Cantidad de documentos por página"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    allowed_sort_fields = ["id", "name", "status", "upload_date", "uploaded_by", "balance_date", "validation", "error_message", "company_name"]
    if sort_field not in allowed_sort_fields:
        sort_field = "upload_date"
    if sort_field == "id":
        db_sort_field = "_id"
    elif sort_field == "validation":
        db_sort_field = "validation.status"
    elif sort_field == "company_name":
        db_sort_field = "company_info.company_name"
    else:
        db_sort_field = sort_field

    sort_direction = 1 if sort_order.lower() == "asc" else -1

    # Filtrar por tenant del usuario
    tenant_id = current_user.tenant_id
    query_filter = {"tenant_id": tenant_id}
    
    if q:
        accent_regex = build_accent_insensitive_regex(q)
        query_filter["$or"] = [
            {"name": {"$regex": accent_regex, "$options": "i"}},
            {"uploaded_by": {"$regex": accent_regex, "$options": "i"}},
            {"company_info.company_name": {"$regex": accent_regex, "$options": "i"}},
            {"company_info.company_cuit": {"$regex": accent_regex, "$options": "i"}},
        ]
    if status:
        query_filter["status"] = status
    if validation_status:
        query_filter["validation.status"] = validation_status

    total = await docs_collection.count_documents(query_filter, collation={"locale": "es", "strength": 1})
    total_pages = ceil(total / page_size) if total > 0 else 1
    skip = (page - 1) * page_size

    projection = {
        "_id": 1,
        "name": 1,
        "status": 1,
        "upload_date": 1,
        "uploaded_by": 1,
        "balance_date": 1,
        "validation": 1,
        "error_message": 1,
        "company_info.company_name": 1,
        "company_info.company_cuit": 1,
        "processing_time": 1,
        "page_count": 1
    }

    cursor = (
        docs_collection.find(query_filter, projection, collation={"locale": "es", "strength": 1})
        .sort(db_sort_field, sort_direction)
        .skip(skip)
        .limit(page_size)
    )
    docs_list = await cursor.to_list(length=page_size)

    for doc in docs_list:
        doc["id"] = str(doc.pop("_id"))
        if "company_info" in doc:
            doc["company_info"] = {
                k: v for k, v in doc["company_info"].items() if k in ["company_name", "company_cuit"]
            }

    return DocsListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=docs_list
    )


# -------------------------------------------------------------------------------------
# /document/{docfile_id}:   ENDPOINT PARA RETRIBUIR UN DOC POR SU ID.
#                           DEVUELVE SUS IMGS DE S3 PRE-FIRMADAS PARA SU RENRERIZACIÓN.
# -------------------------------------------------------------------------------------
@router.get("/document/{docfile_id}")
@limiter.limit("30/minute")
async def get_document(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    try:
        object_id = ObjectId(docfile_id)
        tenant_id = current_user.tenant_id
        
        # Verificar que el documento pertenece al tenant del usuario
        # Usar agregación para filtrar solo páginas relevantes
        pipeline = [
            {
                "$match": {
                    "_id": object_id,
                    "tenant_id": tenant_id
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "status": 1,
                    "upload_date": 1,
                    "uploaded_by": 1,
                    "balance_date": 1,
                    "balance_date_previous": 1,
                    "validation": 1,
                    "error_message": 1,
                    "company_info": 1,
                    "processing_time": 1,
                    "page_count": 1,
                    "upload_path": 1,
                    "balance_data": 1,
                    "income_statement_data": 1,
                    "company_info": 1,
                    "tenant_id": 1,
                    # Filtrar solo páginas relevantes
                    "pages": {
                        "$filter": {
                            "input": "$pages",
                            "as": "page",
                            "cond": {
                                "$or": [
                                    {"$eq": [{"$ifNull": ["$$page.recognized_info.is_balance_sheet", False]}, True]},
                                    {"$eq": [{"$ifNull": ["$$page.recognized_info.is_income_statement_sheet", False]}, True]},
                                    {"$ne": [{"$ifNull": ["$$page.company_info", None]}, None]}
                                ]
                            }
                        }
                    }
                }
            }
        ]
        
        cursor = docs_collection.aggregate(pipeline)
        documents = await cursor.to_list(length=1)
        
        if not documents:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        document = documents[0]
        document["id"] = str(document.pop("_id"))
        
        # Generar URLs pre-firmadas en paralelo para mejor rendimiento
        if "pages" in document and document["pages"]:
            async def generate_presigned_url_async(page):
                """Genera URL pre-firmada de forma asíncrona"""
                if "image_path" in page:
                    try:
                        # Ejecutar la función síncrona en un thread separado
                        page["image_path"] = await asyncio.to_thread(
                            get_presigned_url_from_image_path, 
                            page["image_path"]
                        )
                    except Exception as e:
                        # Mantener la URL original si falla
                        pass
                return page
            
            # Procesar todas las páginas en paralelo
            document["pages"] = await asyncio.gather(
                *[generate_presigned_url_async(page) for page in document["pages"]]
            )
        
        return document
    except HTTPException:
        # Re-lanzar excepciones HTTP ya manejadas
        raise
    except Exception as e:
        if "Invalid ObjectId" in str(e):
            raise HTTPException(status_code=400, detail="ID de documento inválido")
        raise HTTPException(status_code=500, detail=f"Error al obtener el documento: {str(e)}")


# -------------------------------------------------------------------------------------
# /document/{docfile_id}/download: ENDPOINT PARA DESCARGAR EL PDF ORIGINAL
# -------------------------------------------------------------------------------------
@router.get("/document/{docfile_id}/download")
@limiter.limit("10/minute")
async def download_document_pdf(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Genera una URL pre-firmada para descargar el archivo PDF original del documento.
    
    La URL generada permite acceso directo al archivo en S3 por un tiempo limitado (15 minutos).
    Esto evita que el archivo pase por el servidor backend, mejorando el rendimiento.
    """
    try:
        # Obtener la URL pre-firmada del servicio
        download_url = await get_document_download_url(docfile_id, current_user)
        
        # Obtener información del documento para generar un nombre de archivo apropiado
        object_id = ObjectId(docfile_id)
        tenant_id = current_user.tenant_id
        document = await docs_collection.find_one({
            "_id": object_id,
            "tenant_id": tenant_id
        })
        filename = get_document_filename(document) if document else f"documento_{docfile_id}.pdf"
        
        return {
            "download_url": download_url,
            "filename": filename,
            "expires_in": 900  # 15 minutos en segundos
        }
        
    except HTTPException:
        # Re-lanzar excepciones HTTP ya manejadas en el servicio
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno del servidor: {str(e)}"
        )


# Nuevo endpoint para actualizar el documento
@router.put("/update_docfile/{docfile_id}", response_model=dict)
@limiter.limit("10/minute")
async def update_docfile(
    docfile_id: str,
    updated_data: dict,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    try:
        object_id = ObjectId(docfile_id)
        tenant_id = current_user.tenant_id
        
        docfile_obj = DocFile(**updated_data)
        update_dict = docfile_obj.model_dump(exclude_unset=True)
        
        # Solo permitir actualizar documentos del propio tenant
        result = await docs_collection.update_one(
            {"_id": object_id, "tenant_id": tenant_id},
            {"$set": update_dict}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        updated_document = await docs_collection.find_one({
            "_id": object_id,
            "tenant_id": tenant_id
        })
        if updated_document:
            updated_document["id"] = str(updated_document.pop("_id"))
        await validate({
            "docfile_id": docfile_id,
            "collection": docs_collection,
            "current_user": current_user.model_dump() if hasattr(current_user, 'model_dump') else dict(current_user)
        })
        return updated_document
    except Exception as e:
        if "Invalid ObjectId" in str(e):
            raise HTTPException(status_code=400, detail="ID de documento inválido")
        raise HTTPException(status_code=500, detail=f"Error al actualizar el documento: {str(e)}")


# -------------------------------------------------------------------------------
# /document/{docfile_id}  – ELIMINAR DOCUMENTO Y ARCHIVOS ASOCIADOS
# -------------------------------------------------------------------------------
@router.delete(
    "/document/{docfile_id}",
    response_model=dict,
    summary="Elimina un documento (DB) y sus archivos en S3",
    status_code=200,
)
@limiter.limit("5/minute")
async def delete_document(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    """
    Borra el DocFile de la base de datos **y** todos los objetos ligados en S3:
    - PDF subido (`upload_path`)
    - Imágenes asociadas a cada página
    """
    try:
        object_id = ObjectId(docfile_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de documento inválido")

    tenant_id = current_user.tenant_id
    
    # Solo permitir borrar documentos del propio tenant
    document = await docs_collection.find_one({
        "_id": object_id,
        "tenant_id": tenant_id
    })
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    def extract_key(full_url: str) -> str:
        return urlparse(full_url).path.lstrip("/")

    s3_keys: list[str] = []

    if document.get("upload_path"):
        s3_keys.append(extract_key(document["upload_path"]))

    for page in document.get("pages", []):
        if page.get("image_path"):
            s3_keys.append(extract_key(page["image_path"]))

    delete_errors = []
    if s3_keys:
        for i in range(0, len(s3_keys), 1000):
            batch = [{"Key": k} for k in s3_keys[i : i + 1000]]
            resp = await asyncio.to_thread(
                s3_client.delete_objects,
                Bucket=S3_BUCKET_NAME,
                Delete={"Objects": batch},
            )
            delete_errors.extend(resp.get("Errors", []))

    await docs_collection.delete_one({"_id": object_id})

    return {
        "message": "Documento eliminado correctamente",
        "docfile_id": docfile_id,
        "s3_deleted": len(s3_keys) - len(delete_errors),
        "s3_errors": delete_errors,
    }
