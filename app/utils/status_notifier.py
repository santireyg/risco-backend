# app/utils/status_notifier.py

import json
from bson import ObjectId
from app.websockets.manager import manager

async def update_status(
    collection,
    docfile_id,
    new_status,
    user_id=None,
    progress=None,
    processing_time=None,
    error_message=None,
    upload_date=None,
    page_count=None,
    company_info=None,
    balance_date=None,
    validation=None,
    ai_report=None,
    update_db=True,  # Si es False, se envía el webhook sin actualizar la BD.
    send_progress_ws=False  # Si es True, se envía el progress vía WebSocket.
):
    """
    Actualiza el estado y otros campos opcionales de un documento en la BD y envía la actualización vía WebSocket.
    
    :param collection: Colección de la base de datos.
    :param docfile_id: ID del documento.
    :param new_status: Nuevo estado del documento.
    :param progress: Porcentaje de progreso (0-100).
    :param processing_time: Tiempo de procesamiento del documento (opcional).
    :param user_id: Identificador del usuario (por ejemplo, username o ID) para enviar el WebSocket.
    :param error_message: Mensaje de error, en caso de existir.
    :param upload_date: Fecha de carga del documento.
    :param page_count: Cantidad de páginas del documento (opcional).
    :param company_info: Información de la empresa.
    :param balance_date: Fecha del balance.
    :param validation: Información de validación.
    :param ai_report: Reporte generado por IA.
    :param update_db: Booleano que indica si se actualiza la BD (True por defecto).
    :param send_progress_ws: Booleano que indica si se envía el progress en el mensaje WebSocket (False por defecto).
    """
    update_data = {"status": new_status}
    if progress is not None:
        update_data["progress"] = progress
    if processing_time is not None:
        update_data["processing_time"] = processing_time
    if error_message:
        update_data["error_message"] = error_message
    if upload_date is not None:
        update_data["upload_date"] = upload_date
    if balance_date is not None:
        update_data["balance_date"] = balance_date
    if validation is not None:
        update_data["validation"] = validation
    if ai_report is not None:
        update_data["ai_report"] = ai_report

    # Actualiza la BD solo si update_db es True
    if update_db:
        await collection.update_one({"_id": ObjectId(docfile_id)}, {"$set": update_data})

    # Construir el payload para enviar vía WebSocket
    if user_id:
        message_payload = {
            "id": str(docfile_id),
            "status": new_status,
        }
        if send_progress_ws:
            message_payload["progress"] = progress if progress is not None else None
        if upload_date is not None:
            message_payload["upload_date"] = (upload_date.isoformat() if hasattr(upload_date, "isoformat") else upload_date)
        if page_count is not None:
            message_payload["page_count"] = page_count
        if balance_date is not None: 
            message_payload["balance_date"] = (balance_date.isoformat() if hasattr(balance_date, "isoformat") else balance_date)
        if company_info is not None:
            message_payload["company_info"] = company_info
        if validation is not None:
            message_payload["validation"] = validation
        if ai_report is not None:
            message_payload["ai_report"] = ai_report
        if processing_time is not None:
            message_payload["processing_time"] = processing_time
        if error_message:
            message_payload["error_message"] = error_message

        message = json.dumps(message_payload)
        await manager.broadcast(user_id, message)
