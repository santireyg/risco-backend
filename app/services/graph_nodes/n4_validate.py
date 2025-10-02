# path: app/services/s4_validate.py

# Imports de LangChain legacy eliminados

from app.core.database import docs_collection
from app.models.docs_validation import Validation
# TimingCallbackHandler legacy eliminado
from bson import ObjectId
from app.utils.status_notifier import update_status

# Importes para LangGraph
from app.services.graph_state import DocumentProcessingState

TOLERANCIA_ERROR = 0.0005 # 0.05%

# Colección de documentos sobre la que vamos a trabajar
collection = docs_collection


# ------------------------------------------------------------------------------- 
# RUNNABLE 1: VALIDAR CUENTAS ELEMENTALES DE LA CONTABILIDAD 
# -------------------------------------------------------------------------------

async def set_validation_sin_datos(state: DocumentProcessingState):
    """Establece validación 'Sin datos' cuando no hay información suficiente."""
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)
    invalid_status = "Sin datos"
    invalid_messages = [
        "No se han detectado en el documento las páginas de Estado de Resultados y/o Estado de Situación Patrimonial.\nPor favor, revisar el documento de balance."
    ]
    invalid_validation = Validation(status=invalid_status, message=invalid_messages)
    await update_status(collection, docfile_id, "Analizado", user_id, progress=100, validation=invalid_validation.model_dump(), send_progress_ws=True)
    return state

async def validate(state: DocumentProcessingState) -> DocumentProcessingState:
    """Ejecuta las validaciones contables principales del documento."""
    # Si el pipeline fue detenido previamente, o faltan datos clave, setea validación "Sin datos" y retorna
    if state.get("stop"):
        return await set_validation_sin_datos(state)

    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)

    # Update Status: Validando
    await update_status(collection, docfile_id, "Validando", user_id, progress=0, send_progress_ws=True)

    # Obtengo el documento de la base de datos
    docfile_data = await collection.find_one({"_id": ObjectId(docfile_id)})

    # Convertir documento a formato DocFile
    # docfile = DocFile(**docfile_data)
    docfile = docfile_data

    # Obtener la información necesaria: balance (ESP) y estado de resultados (ESP)
    balance_data = docfile.get('balance_data')
    income_statement_data = docfile.get('income_statement_data')
    if not balance_data or not income_statement_data:
        return await set_validation_sin_datos(state)

    # Crear accessors para compatibilidad con estructuras antigua y nueva
    from app.utils.financial_data_accessor import create_accessor
    balance_accessor = create_accessor(balance_data['resultados_principales'])
    income_accessor = create_accessor(income_statement_data['resultados_principales'])

    # VALIDACIONES
    errors = []
    # Flags para cada tipo de error (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    error_1 = False  # A = P + PN
    error_2 = False  # A = A CORRIENTE + A NO CORRIENTE
    error_3 = False  # P = P CORRIENTE + P NO CORRIENTE
    error_4 = False  # PN actual = PN anterior + Resultado del ejercicio actual
    error_5 = False  # Disponibilidades ≤ Activo corriente
    error_6 = False  # Bienes de cambio ≤ Activo corriente
    error_7 = False  # Disponibilidades + Bienes de cambio ≤ Activo corriente
    error_8 = False  # Resultado antes de impuestos ≥ Resultado del ejercicio
    error_9 = False  # Ingresos operativos ≥ Resultado antes de impuestos
    error_10 = False  # ΔA = ΔP + ΔPN

    def is_within_tolerance(expected, actual):
        """Función para verificar si dos valores están dentro de la tolerancia."""
        if expected == 0:  # Evitar divisiones por cero
            return abs(actual) <= TOLERANCIA_ERROR
        error = abs((actual - expected) / expected)
        return error <= TOLERANCIA_ERROR

    # 1. A tot = P tot + PN
    activo_total_actual = balance_accessor.get('activo_total', 'actual')
    pasivo_total_actual = balance_accessor.get('pasivo_total', 'actual')
    patrimonio_neto_actual = balance_accessor.get('patrimonio_neto', 'actual')
    
    if activo_total_actual and pasivo_total_actual and patrimonio_neto_actual:
        if not is_within_tolerance(activo_total_actual, pasivo_total_actual + patrimonio_neto_actual):
            error_1 = True
            errors.append(
                f"A = P + PN (Período actual):\n"
                f"${activo_total_actual:,.2f} ≠ "
                f"${pasivo_total_actual:,.2f} + "
                f"${patrimonio_neto_actual:,.2f}"
            )
    
    activo_total_anterior = balance_accessor.get('activo_total', 'anterior')
    pasivo_total_anterior = balance_accessor.get('pasivo_total', 'anterior')
    patrimonio_neto_anterior = balance_accessor.get('patrimonio_neto', 'anterior')
    
    if activo_total_anterior and pasivo_total_anterior and patrimonio_neto_anterior:
        if not is_within_tolerance(activo_total_anterior, pasivo_total_anterior + patrimonio_neto_anterior):
            error_1 = True
            errors.append(
                f"A = P + PN (Período anterior):\n"
                f"${activo_total_anterior:,.2f} ≠ "
                f"${pasivo_total_anterior:,.2f} + "
                f"${patrimonio_neto_anterior:,.2f}"
            )

    # 2. A tot = A corr + A no corr
    activo_corriente_actual = balance_accessor.get('activo_corriente', 'actual')
    activo_no_corriente_actual = balance_accessor.get('activo_no_corriente', 'actual')
    
    if activo_total_actual and activo_corriente_actual and activo_no_corriente_actual:
        if not is_within_tolerance(activo_total_actual, activo_corriente_actual + activo_no_corriente_actual):
            error_2 = True
            errors.append(
                f"A = A CORRIENTE + A NO CORRIENTE (Período actual):\n"
                f"${activo_total_actual:,.2f} ≠ "
                f"${activo_corriente_actual:,.2f} + "
                f"${activo_no_corriente_actual:,.2f}"
            )
    
    activo_corriente_anterior = balance_accessor.get('activo_corriente', 'anterior')
    activo_no_corriente_anterior = balance_accessor.get('activo_no_corriente', 'anterior')
    
    if activo_total_anterior and activo_corriente_anterior and activo_no_corriente_anterior:
        if not is_within_tolerance(activo_total_anterior, activo_corriente_anterior + activo_no_corriente_anterior):
            error_2 = True
            errors.append(
                f"A = A CORRIENTE + A NO CORRIENTE (Período anterior):\n"
                f"${activo_total_anterior:,.2f} ≠ "
                f"${activo_corriente_anterior:,.2f} + "
                f"${activo_no_corriente_anterior:,.2f}"
            )

    # 3. P tot = P corr + P no corr
    pasivo_corriente_actual = balance_accessor.get('pasivo_corriente', 'actual')
    pasivo_no_corriente_actual = balance_accessor.get('pasivo_no_corriente', 'actual')
    
    if pasivo_total_actual and pasivo_corriente_actual and pasivo_no_corriente_actual:
        if not is_within_tolerance(pasivo_total_actual, pasivo_corriente_actual + pasivo_no_corriente_actual):
            error_3 = True
            errors.append(
                f"P = P CORRIENTE + P NO CORRIENTE (Período actual):\n"
                f"${pasivo_total_actual:,.2f} ≠ "
                f"${pasivo_corriente_actual:,.2f} + "
                f"${pasivo_no_corriente_actual:,.2f}"
            )
    
    pasivo_corriente_anterior = balance_accessor.get('pasivo_corriente', 'anterior')
    pasivo_no_corriente_anterior = balance_accessor.get('pasivo_no_corriente', 'anterior')
    
    if pasivo_total_anterior and pasivo_corriente_anterior and pasivo_no_corriente_anterior:
        if not is_within_tolerance(pasivo_total_anterior, pasivo_corriente_anterior + pasivo_no_corriente_anterior):
            error_3 = True
            errors.append(
                f"P = P CORRIENTE + P NO CORRIENTE (Período anterior):\n"
                f"${pasivo_total_anterior:,.2f} ≠ "
                f"${pasivo_corriente_anterior:,.2f} + "
                f"${pasivo_no_corriente_anterior:,.2f}"
            )

    # 4. PN actual = PN anterior + Resultado del ejercicio actual
    # if not is_within_tolerance(balance['patrimonio_neto_actual'], balance['patrimonio_neto_anterior'] + income['resultados_del_ejercicio_actual']):
    #     error_4 = True
    #     errors.append(
    #         f"PN actual = PN anterior + Resultado del ejercicio actual:\n"
    #         f"${balance['patrimonio_neto_actual']:,.2f} ≠ "
    #         f"${balance['patrimonio_neto_anterior']:,.2f} + "
    #         f"${income['resultados_del_ejercicio_actual']:,.2f}"
    #     )

    # 5. Disponibilidades ≤ Activo corriente (actual y anterior)
    disponibilidades_actual = balance_accessor.get('disponibilidades', 'actual')
    disponibilidades_anterior = balance_accessor.get('disponibilidades', 'anterior')
    
    if disponibilidades_actual and activo_corriente_actual:
        if disponibilidades_actual > activo_corriente_actual + TOLERANCIA_ERROR:
            error_5 = True
            errors.append(
                f"Disponibilidades (actual) > Activo corriente (actual):\n"
                f"${disponibilidades_actual:,.2f} > ${activo_corriente_actual:,.2f}"
            )
    
    if disponibilidades_anterior and activo_corriente_anterior:
        if disponibilidades_anterior > activo_corriente_anterior + TOLERANCIA_ERROR:
            error_5 = True
            errors.append(
                f"Disponibilidades (anterior) > Activo corriente (anterior):\n"
                f"${disponibilidades_anterior:,.2f} > ${activo_corriente_anterior:,.2f}"
            )

    # 6. Bienes de cambio ≤ Activo corriente (actual y anterior) - OPCIONAL
    if balance_accessor.has('bienes_de_cambio'):
        bienes_cambio_actual = balance_accessor.get('bienes_de_cambio', 'actual')
        bienes_cambio_anterior = balance_accessor.get('bienes_de_cambio', 'anterior')
        
        if bienes_cambio_actual and activo_corriente_actual:
            if bienes_cambio_actual > activo_corriente_actual + TOLERANCIA_ERROR:
                error_6 = True
                errors.append(
                    f"Bienes de cambio (actual) > Activo corriente (actual):\n"
                    f"${bienes_cambio_actual:,.2f} > ${activo_corriente_actual:,.2f}"
                )
        
        if bienes_cambio_anterior and activo_corriente_anterior:
            if bienes_cambio_anterior > activo_corriente_anterior + TOLERANCIA_ERROR:
                error_6 = True
                errors.append(
                    f"Bienes de cambio (anterior) > Activo corriente (anterior):\n"
                    f"${bienes_cambio_anterior:,.2f} > ${activo_corriente_anterior:,.2f}"
                )

        # 7. Disponibilidades + Bienes de cambio ≤ Activo corriente (actual y anterior) - Solo si tiene bienes de cambio
        if disponibilidades_actual and bienes_cambio_actual and activo_corriente_actual:
            if (disponibilidades_actual + bienes_cambio_actual) > activo_corriente_actual + TOLERANCIA_ERROR:
                error_7 = True
                errors.append(
                    f"Disponibilidades + Bienes de cambio (actual) > Activo corriente (actual):\n"
                    f"${disponibilidades_actual + bienes_cambio_actual:,.2f} > ${activo_corriente_actual:,.2f}"
                )
        
        if disponibilidades_anterior and bienes_cambio_anterior and activo_corriente_anterior:
            if (disponibilidades_anterior + bienes_cambio_anterior) > activo_corriente_anterior + TOLERANCIA_ERROR:
                error_7 = True
                errors.append(
                    f"Disponibilidades + Bienes de cambio (anterior) > Activo corriente (anterior):\n"
                    f"${disponibilidades_anterior + bienes_cambio_anterior:,.2f} > ${activo_corriente_anterior:,.2f}"
                )

    # # 8. Resultado antes de impuestos ≥ Resultado del ejercicio (actual y anterior)
    # if income['resultados_antes_de_impuestos_actual'] + TOLERANCIA_ERROR < income['resultados_del_ejercicio_actual']:
    #     error_8 = True
    #     errors.append(
    #         f"Resultado antes de impuestos (actual) < Resultado del ejercicio (actual):\n"
    #         f"${income['resultados_antes_de_impuestos_actual']:,.2f} < ${income['resultados_del_ejercicio_actual']:,.2f}"
    #     )
    # if income['resultados_antes_de_impuestos_anterior'] + TOLERANCIA_ERROR < income['resultados_del_ejercicio_anterior']:
    #     error_8 = True
    #     errors.append(
    #         f"Resultado antes de impuestos (anterior) < Resultado del ejercicio (anterior):\n"
    #         f"${income['resultados_antes_de_impuestos_anterior']:,.2f} < ${income['resultados_del_ejercicio_anterior']:,.2f}"
    #     )

    # 9. Ingresos por venta ≥ Resultado antes de impuestos (actual y anterior)
    ingresos_venta_actual = income_accessor.get('ingresos_por_venta', 'actual')
    resultados_antes_impuestos_actual = income_accessor.get('resultados_antes_de_impuestos', 'actual')
    
    if ingresos_venta_actual and resultados_antes_impuestos_actual:
        if ingresos_venta_actual + TOLERANCIA_ERROR < resultados_antes_impuestos_actual:
            error_9 = True
            errors.append(
                f"Ingresos por venta (actual) < Resultado antes de impuestos (actual):\n"
                f"${ingresos_venta_actual:,.2f} < ${resultados_antes_impuestos_actual:,.2f}"
            )
    
    ingresos_venta_anterior = income_accessor.get('ingresos_por_venta', 'anterior')
    resultados_antes_impuestos_anterior = income_accessor.get('resultados_antes_de_impuestos', 'anterior')
    
    if ingresos_venta_anterior and resultados_antes_impuestos_anterior:
        if ingresos_venta_anterior + TOLERANCIA_ERROR < resultados_antes_impuestos_anterior:
            error_9 = True
            errors.append(
                f"Ingresos por venta (anterior) < Resultado antes de impuestos (anterior):\n"
                f"${ingresos_venta_anterior:,.2f} < ${resultados_antes_impuestos_anterior:,.2f}"
            )

    # 10. ΔA = ΔP + ΔPN
    if activo_total_actual and activo_total_anterior and pasivo_total_actual and pasivo_total_anterior and patrimonio_neto_actual and patrimonio_neto_anterior:
        delta_activo = activo_total_actual - activo_total_anterior
        delta_pasivo = pasivo_total_actual - pasivo_total_anterior
        delta_pn = patrimonio_neto_actual - patrimonio_neto_anterior
        if not is_within_tolerance(delta_activo, delta_pasivo + delta_pn):
            error_10 = True
            errors.append(
                f"ΔA = ΔP + ΔPN:\n"
                f"ΔA = ${delta_activo:,.2f}  ↔  ΔP + ΔPN = ${delta_pasivo + delta_pn:,.2f}"
            )

    # Determinar status usando los flags 1-10
    if not errors:
        status = "Validado"
    elif (error_4 and not (error_1 or error_2 or error_3 or error_5 or error_6 or error_7 or error_8 or error_9 or error_10)):
        status = "Advertencia"
    else:
        status = "Advertencia"

    validation_result = Validation(
        status=status,
        message=errors if errors else ["Validación completada con éxito. No se han detectado inconsistencias en las cuentas elementales."],
    )

    # Update Status: Validado
    # Guardar el resultado de la validación en la base de datos
    await update_status(collection, docfile_id, "Analizado", user_id, progress=100, validation=validation_result.model_dump(), send_progress_ws=True)

    # finalizar el proceso y retornar estado actualizado
    return state

# Pipeline legacy eliminado - ahora trabajamos directamente con funciones async


# ------------------------------------------------------------------------------------
# NODO LANGGRAPH: VALIDATE NODE
# ------------------------------------------------------------------------------------
async def validate_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo LangGraph para validación de ecuaciones contables.
    
    Ejecuta validaciones de las ecuaciones contables fundamentales:
    - A = P + PN (activo = pasivo + patrimonio neto)
    - A = A corriente + A no corriente
    - P = P corriente + P no corriente
    - PN actual = PN anterior + Resultado del ejercicio
    - Otras validaciones de coherencia contable
    
    Args:
        state: Estado actual del procesamiento
        
    Returns:
        DocumentProcessingState: Estado actualizado con validación completada
    """
    import logging
    import time
    from app.models.docs_processing_time import ProcessingTime
    
    # Iniciar tracking de tiempo
    start_time = time.perf_counter()
    
    try:
        # PASO ÚNICO: Ejecutar validación contable
        state = await validate(state)
        
        # Calcular duración
        duration = time.perf_counter() - start_time
        
        # Actualizar processing_time en la BD y notificar vía WebSocket
        docfile_id = state.get("docfile_id")
        requester = state.get("requester")
        if docfile_id and requester:
            user_id = str(requester.id)
            try:
                # Obtener el documento actual
                document = await collection.find_one({"_id": ObjectId(docfile_id)})
                if document:
                    # Obtener o crear processing_time
                    processing_time_data = document.get("processing_time", {})
                    processing_time = ProcessingTime(**processing_time_data) if processing_time_data else ProcessingTime()
                    
                    # Actualizar el tiempo de validation
                    processing_time.validation = duration
                    processing_time.update_total()
                    
                    # Guardar en BD y notificar vía WebSocket
                    from app.utils.status_notifier import update_status
                    current_status = document.get("status", "Procesando")
                    await update_status(
                        collection=collection,
                        docfile_id=docfile_id,
                        new_status=current_status,
                        user_id=user_id,
                        processing_time=processing_time.model_dump(),
                        update_db=True
                    )
                    
                    logging.info(f"Tiempo validation para {docfile_id}: {duration:.2f}s - Notificado vía WebSocket")
            except Exception as e:
                logging.error(f"Error actualizando processing_time para validation: {e}")
        
        return state
        
    except Exception as e:
        logging.error(f"Error en validate_node: {str(e)}")
        return {**state, "error_message": f"Error en validación: {str(e)}"}
