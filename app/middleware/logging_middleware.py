# app/middleware/logging_middleware.py

import logging
import time
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from bson import ObjectId

from app.core.database import docs_collection

logger = logging.getLogger("app.http")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware personalizado para logging inteligente de peticiones HTTP.
    Filtra peticiones no deseadas y enriquece logs con información contextual.
    """
    
    # Paths que NO queremos logear
    EXCLUDED_PATHS = {
        "/me",
        "/documents",  # GET /documents
    }
    
    # Paths que queremos logear con información especial
    SPECIAL_PATHS = {
        "/login": "AUTH",
        "/export_document": "EXPORT", 
    }
    
    def should_exclude_path(self, path: str, method: str) -> bool:
        """Determina si una petición debe ser excluida del logging"""
        
        # Excluir websockets
        if "websocket" in path.lower() or "ws" in path.lower():
            return True
            
        # Excluir paths específicos
        if path in self.EXCLUDED_PATHS:
            return True
            
        # Excluir GET /documents específicamente
        if method == "GET" and path == "/documents":
            return True
            
        return False
    
    async def get_document_info(self, docfile_id: str) -> tuple[str, str]:
        """
        Obtiene información del documento para enriquecer los logs.
        Retorna (company_name_or_filename, cuit)
        """
        try:
            object_id = ObjectId(docfile_id)
            document = await docs_collection.find_one(
                {"_id": object_id}, 
                {"name": 1, "company_info.company_name": 1, "company_info.company_cuit": 1}
            )
            
            if document:
                company_name = document.get("company_info", {}).get("company_name")
                display_name = company_name if company_name else document.get("name", "Documento sin nombre")
                cuit = document.get("company_info", {}).get("company_cuit", "N/A")
                return display_name, cuit
            
        except Exception as e:
            logger.debug(f"Error obteniendo info del documento {docfile_id}: {e}")
            
        return "Documento no encontrado", "N/A"
    
    def get_username_from_request(self, request: Request) -> str:
        """Extrae el username del usuario autenticado del request"""
        try:
            # Intentar extraer el token de las cookies
            token = request.cookies.get("token")
            if not token:
                return "Usuario no autenticado"
            
            # Decodificar el token JWT
            import jwt
            from app.core.config import SECRET_KEY_AUTH, ALGORITHM
            
            payload = jwt.decode(token, SECRET_KEY_AUTH, algorithms=[ALGORITHM])
            username = payload.get("sub")
            return username if username else "Usuario desconocido"
            
        except Exception:
            return "Usuario desconocido"
    
    async def log_request(self, request: Request, response: Response, process_time: float):
        """Genera logs personalizados basados en el tipo de petición"""
        
        method = request.method
        path = request.url.path
        status_code = response.status_code
        username = self.get_username_from_request(request)
        
        # Logging para documentos específicos GET /document/{docfile_id}
        if method == "GET" and path.startswith("/document/"):
            try:
                docfile_id = path.split("/document/")[1].split("/")[0]  # Extraer ID
                display_name, cuit = await self.get_document_info(docfile_id)
                logger.info(f"[DOCUMENT] Acceso a documento: {display_name} por {username}")
                return
            except Exception:
                pass
        
        # Logging para login (solo se logeará en el endpoint si es exitoso)
        if method == "POST" and "/login" in path:
            if status_code == 200:
                # El log específico se hará en el endpoint
                return
            else:
                # Log de login fallido (ya manejado en el endpoint)
                return
        
        # Logging para exportación (se manejará en el endpoint)
        if method == "POST" and "/export_document" in path:
            return
        
        # Log genérico para otras peticiones relevantes
        if not self.should_exclude_path(path, method):
            logger.info(f"[HTTP] {method} {path} - {status_code} - {username} - {process_time:.3f}s")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Procesa la petición y genera logs apropiados"""
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Si la petición debe ser excluida, procesarla sin logging
        if self.should_exclude_path(path, method):
            return await call_next(request)
        
        # Procesar la petición
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Solo logear si no es StreamingResponse (websockets, etc.)
            if not isinstance(response, StreamingResponse):
                await self.log_request(request, response, process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"[HTTP] {method} {path} - ERROR: {str(e)} - {process_time:.3f}s")
            raise
