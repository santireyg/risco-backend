# ------------------------------------------------------------------------------------
# N1 CREATE REPORT OBJECT - Crea el objeto de reporte en MongoDB
# ------------------------------------------------------------------------------------
"""
Nodo que crea el documento inicial del reporte en la colección 'reports'.
Obtiene datos del docfile original y estructura el reporte inicial.
"""

import logging
from datetime import datetime
from bson import ObjectId
from app.services.report_graph.graph_state import ReportProcessingState
from app.core.database import docs_collection, reports_collection
from app.models.report import (
    Report, CreatedBy, CompanyInfoReport, 
    StatementData, BalanceDataSummary, IncomeDataSummary
)

logger = logging.getLogger(__name__)


async def create_report_object_node(state: ReportProcessingState) -> ReportProcessingState:
    """
    Crea el objeto de reporte inicial en MongoDB.
    
    Pasos:
    1. Obtiene el documento (docfile) de la base de datos
    2. Extrae company_info, balance_data, income_statement_data
    3. Crea el documento de reporte con status "Creando reporte"
    4. Guarda el report_id en el estado
    """
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    tenant_id = state.get("tenant_id", "default")
    
    logger.info(f"[REPORT_GRAPH] Creando objeto de reporte para documento: {docfile_id}")
    
    try:
        # PASO 1: Obtener el documento de la base de datos
        docfile = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
        
        if not docfile:
            return {**state, "error_message": f"Documento no encontrado: {docfile_id}"}
        
        # Verificar que el documento pertenece al mismo tenant
        if docfile.get("tenant_id") != tenant_id:
            return {**state, "error_message": "El documento no pertenece al tenant del usuario"}
        
        # PASO 2: Extraer datos del documento
        company_info_data = docfile.get("company_info", {})
        balance_data = docfile.get("balance_data", {})
        income_statement_data = docfile.get("income_statement_data", {})
        balance_date = docfile.get("balance_date")
        balance_date_previous = docfile.get("balance_date_previous")
        
        # Validar que tenga datos mínimos
        if not balance_data and not income_statement_data:
            return {**state, "error_message": "El documento no tiene datos de balance ni estado de resultados"}
        
        # PASO 3: Preparar la estructura del reporte
        company_name = company_info_data.get("company_name", docfile.get("name", "Sin nombre"))
        company_cuit = company_info_data.get("company_cuit")
        
        # Crear estructura created_by
        created_by = CreatedBy(
            user_id=str(requester.id),
            name=f"{getattr(requester, 'first_name', '')} {getattr(requester, 'last_name', '')}".strip() or "Usuario",
            tenant_id=tenant_id
        )
        
        # Crear estructura company_info para el reporte
        company_info_report = None
        if company_info_data:
            company_info_report = CompanyInfoReport(
                company_cuit=company_info_data.get("company_cuit"),
                company_name=company_info_data.get("company_name", company_name),
                company_activity=company_info_data.get("company_activity"),
                company_address=company_info_data.get("company_address")
            )
        
        # Crear estructura statement_data
        balance_summary = None
        if balance_data:
            balance_summary = BalanceDataSummary(
                resultados_principales=balance_data.get("resultados_principales", []),
                detalles_activo=balance_data.get("detalles_activo", []),
                detalles_pasivo=balance_data.get("detalles_pasivo", []),
                detalles_patrimonio_neto=balance_data.get("detalles_patrimonio_neto", [])
            )
        
        income_summary = None
        if income_statement_data:
            income_summary = IncomeDataSummary(
                resultados_principales=income_statement_data.get("resultados_principales", []),
                detalles_estado_resultados=income_statement_data.get("detalles_estado_resultados", [])
            )
        
        statement_data = StatementData(
            statement_date=balance_date,
            statement_date_previous=balance_date_previous,
            balance_data=balance_summary,
            income_statement_data=income_summary
        )
        
        # PASO 4: Crear el documento de reporte
        report = Report(
            tenant_id=tenant_id,
            docfile_id=docfile_id,
            status="Creando reporte",
            company_name=company_name,
            company_cuit=company_cuit,
            company_info=company_info_report,
            created_at=datetime.utcnow(),
            created_by=created_by,
            statement_data=statement_data,
            indicators=None,
            bcra_data=None
        )
        
        # Insertar en la base de datos
        report_dict = report.model_dump()
        result = await reports_collection.insert_one(report_dict)
        report_id = str(result.inserted_id)
        
        logger.info(f"[REPORT_GRAPH] Reporte creado con ID: {report_id}")
        
        # Actualizar estado con datos obtenidos
        updated_state = state.copy()
        updated_state.update({
            "report_id": report_id,
            "docfile": docfile,
            "progress": 0.33
        })
        
        return updated_state
        
    except Exception as e:
        logger.error(f"[REPORT_GRAPH] Error creando objeto de reporte: {str(e)}")
        return {**state, "error_message": f"Error creando reporte: {str(e)}"}
