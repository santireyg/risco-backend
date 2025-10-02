"""
Endpoint de exportación de datos financieros a Excel
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from app.core.auth import get_current_user
from app.models.users import User
from app.services.export_xlsx import generate_excel_export, generate_filename
from app.core.database import docs_collection
from app.main import limiter
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/export_xlsx/{docfile_id}", summary="Exportar documento a Excel")
@limiter.limit("10/minute")
async def export_xlsx(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Exporta los datos financieros de un documento a formato Excel (.xlsx).
    
    **Validaciones:**
    - El documento debe existir
    - Debe pertenecer al tenant del usuario actual
    - Debe estar en estado 'Analizado' o 'Exportado'
    - Debe tener información de la empresa (company_info)
    - Debe tener datos financieros (balance_data y/o income_statement_data)
    
    **Respuesta:**
    - Archivo Excel descargable con extensión .xlsx
    - Nombre del archivo: {company_name}_{periodo_actual}.xlsx
    
    **Estructura del Excel:**
    - Hoja 1: Situación Patrimonial (si hay balance_data)
    - Hoja 2: Estado de Resultados (si hay income_statement_data)
    - Hoja 3: Cuentas Principales (si hay datos disponibles)
    """
    # Generar el archivo Excel (incluye todas las validaciones)
    excel_bytes = await generate_excel_export(docfile_id, current_user)
    
    # Obtener documento para generar nombre de archivo
    document = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
    filename = generate_filename(document)
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
