# app/services/download_service.py

from typing import Optional
from bson import ObjectId
from fastapi import HTTPException
from urllib.parse import urlparse

from app.core.database import docs_collection
from app.core.s3_client import generate_presigned_url
from app.models.users import User


async def get_document_download_url(
    docfile_id: str, 
    current_user: User,
    expiration: int = 900  # 15 minutos por defecto
) -> str:
    """
    Genera una URL pre-firmada para descargar el archivo PDF original de un documento.
    
    Args:
        docfile_id: ID del documento en MongoDB
        current_user: Usuario autenticado actual
        expiration: Tiempo de expiración de la URL en segundos (por defecto 15 minutos)
    
    Returns:
        str: URL pre-firmada para descarga directa desde S3
        
    Raises:
        HTTPException: Si el documento no existe, no tiene archivo o hay errores de acceso
    """
    # Validar ObjectId
    try:
        object_id = ObjectId(docfile_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de documento inválido")
    
    # Buscar el documento en la base de datos
    document = await docs_collection.find_one({"_id": object_id})
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Verificar que el documento tenga un archivo PDF
    upload_path = document.get("upload_path")
    if not upload_path:
        raise HTTPException(
            status_code=404, 
            detail="El documento no tiene un archivo PDF asociado"
        )
    
    # Extraer la clave S3 del upload_path
    try:
        parsed_url = urlparse(upload_path)
        s3_key = parsed_url.path.lstrip("/")
        
        if not s3_key:
            raise HTTPException(
                status_code=500, 
                detail="Ruta del archivo inválida"
            )
        
        # Generar URL pre-firmada
        presigned_url = generate_presigned_url(s3_key, expiration)
        return presigned_url
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al generar la URL de descarga: {str(e)}"
        )


def get_document_filename(document: dict) -> str:
    """
    Genera un nombre de archivo apropiado para la descarga basado en los datos del documento.
    
    Args:
        document: Documento de MongoDB
        
    Returns:
        str: Nombre de archivo sugerido para la descarga
    """
    # Usar el nombre original del documento si está disponible
    if document.get("name"):
        filename = document["name"]
        # Asegurar que termine con .pdf
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        return filename
    
    # Fallback usando el ID del documento
    doc_id = str(document.get("_id", "documento"))
    return f"documento_{doc_id}.pdf"
