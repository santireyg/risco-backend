# app/services/s1_upload_convert.py

import logging
import os
import shutil
import asyncio
import gc
from pdf2image import convert_from_path
from bson import ObjectId
from pydantic import SecretBytes
from app.core.database import docs_collection
# Imports de LangChain legacy eliminados
from app.models.docs import DocFile
from app.utils.status_notifier import update_status
# TimingCallbackHandler legacy eliminado
import tempfile
from io import BytesIO
import math
from app.utils.memory_cleanup import try_malloc_trim  ##🧹 MALLOC_TRIM para upload_convert

# Importamos el cliente de S3 y configuración
from app.core.s3_client import s3_client
from app.core.config import S3_BUCKET_NAME, S3_ENVIRONMENT
from pdf2image import pdfinfo_from_path

# Importes para LangGraph
from app.services.graph_state import DocumentProcessingState
from app.models.docs import Page


# Collection de documentos sobre la que se trabaja
collection = docs_collection


# -------------------------------------------------------------------------------
# FUNCIÓN 1: SUBIR ARCHIVO PDF A S3 Y CREAR DOC EN BD
# -------------------------------------------------------------------------------
async def upload_file(state: DocumentProcessingState) -> DocumentProcessingState:
    """Sube el archivo PDF a S3 y crea/actualiza el documento en MongoDB."""
    filename = state['filename']
    raw = state['file_content']
    # si viene como SecretBytes, extrae .get_secret_value(), si no, úsalo tal cual
    file_content = raw.get_secret_value() if isinstance(raw, SecretBytes) else raw
    requester = state['requester']
    user_id = str(requester.id)

    docfile_id = state.get('docfile_id')

    # Si NO se provee docfile_id, creamos el DocFile en la BD
    if not docfile_id:
        uploaded_by = f"{requester.first_name} {requester.last_name}"
        tenant_id = state.get('tenant_id', 'default')
        
        docfile = DocFile(
            name=filename,
            uploaded_by=uploaded_by,
            status="En cola",
            progress=0,
            tenant_id=tenant_id
        )

        docfile_db = await collection.insert_one(docfile.model_dump(by_alias=True))
        docfile_id = str(docfile_db.inserted_id)

    # Actualiza estado a "Cargando"
    await update_status(collection, docfile_id, "Cargando", user_id, send_progress_ws=True)

    # Obtener configuración del tenant para rutas S3
    tenant_id = state.get('tenant_id', 'default')
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)
    
    # Key del archivo PDF en S3 usando prefijo del tenant
    s3_key = f"{tenant_config.get_s3_prefix(docfile_id)}/pdf_file/{filename}"

    # Subida asincrónica del PDF a S3
    await asyncio.to_thread(
        s3_client.put_object,
        Bucket=S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_content
    )

    # Liberar file_content inmediatamente después de subirlo
    del file_content

    # URL pública en S3
    s3_pdf_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"

    # Actualiza objeto DocFile con la URL y estado
    await collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {"upload_path": s3_pdf_url, "status": "Cargado"}}
    )

    # Actualiza estado a "Cargado"
    await update_status(collection, docfile_id, "Cargado", user_id, send_progress_ws=True)

    # Actualizar estado con docfile_id y datos S3
    updated_state = state.copy()
    updated_state.update({
        "docfile_id": docfile_id,
        "s3_pdf_key": s3_key,
    })
    
    return updated_state



# -------------------------------------------------------------------------------
# FUNCIÓN 2: CONVERTIR A IMÁGENES
# -------------------------------------------------------------------------------
# >>> Variables para ajustar el comportamiento <<<
CONVERSION_BATCH_SIZE = 3  # Número de páginas a procesar en cada llamada a convert_from_path
PROGRESS_UPDATE_STEP_PERCENTAGE = 10 # Actualizar el progreso cada este porcentaje (ej: 25, 50, 75, 100)

async def convert_pdf_to_images(state: DocumentProcessingState) -> DocumentProcessingState:
    """Convierte el PDF a imágenes PNG y las sube a S3."""
    docfile_id = state['docfile_id']
    s3_pdf_key = state['s3_pdf_key']  # Key del PDF en S3
    requester = state['requester']
    user_id = str(requester.id)

    await update_status(collection, docfile_id, "Convirtiendo", user_id, progress=0, send_progress_ws=True) # Iniciar con 0%

    temp_dir = None
    image_urls = [] # Lista para almacenar las URLs de S3 de las imágenes

    processed_pages_count = 0 # Contador de páginas procesadas exitosamente

    # Variables para controlar la actualización de progreso
    next_progress_threshold = PROGRESS_UPDATE_STEP_PERCENTAGE
    last_reported_progress_percent = 0


    try:
        # Crear un directorio temporal
        temp_dir = tempfile.mkdtemp()
        pdf_filename = os.path.basename(s3_pdf_key)
        temp_pdf_path = os.path.join(temp_dir, pdf_filename)

        # Descargar el archivo PDF desde S3
        await asyncio.to_thread(
            s3_client.download_file,
            S3_BUCKET_NAME,
            s3_pdf_key,
            temp_pdf_path
        )

        # Obtener el número total de páginas
        info = await asyncio.to_thread(pdfinfo_from_path, temp_pdf_path)
        total_pages = info['Pages']

        if total_pages == 0:
             logging.warning(f"Documento {docfile_id} parece no tener páginas.")
             # Actualizar con page_count = 0 para documentos sin páginas
             await collection.update_one(
                 {"_id": ObjectId(docfile_id)},
                 {"$set": {"page_count": 0, "status": "Convertido", "progress": 100}}
             )
             await update_status(collection, docfile_id, "Convertido", user_id, progress=100, update_db=False, send_progress_ws=True)
             # No hay imágenes ni output_params para enviar al siguiente paso
             return None # O un dict vacío si el siguiente paso lo espera


        # Iterar sobre los lotes de páginas
        # i representa el índice de inicio del lote (0-based)
        for i in range(0, total_pages, CONVERSION_BATCH_SIZE):
            start_page_batch = i + 1 # Número de la primera página del lote (1-based)
            end_page_batch = min(i + CONVERSION_BATCH_SIZE, total_pages) # Número de la última página del lote (1-based)

            logging.info(f"Procesando lote de páginas {start_page_batch}-{end_page_batch} para docfile {docfile_id}")

            # Convertir el lote de páginas actual a imágenes
            # Esto devuelve una lista con 'end_page_batch - start_page_batch + 1' imágenes
            try:
                 batch_images = await asyncio.to_thread(
                     convert_from_path,
                     temp_pdf_path,
                     first_page=start_page_batch,
                     last_page=end_page_batch,
                     #dpi=300 # Considera ajustar DPI si la calidad o tamaño de archivo son un problema
                 )
            except Exception as convert_e:
                 logging.error(f"Error al convertir lote de páginas {start_page_batch}-{end_page_batch} para docfile {docfile_id}: {convert_e}", exc_info=True)
                 # Decide si abortar todo el proceso o intentar continuar con el siguiente lote
                 # Por ahora, continuaremos pero loggearemos el error y no procesaremos estas imágenes fallidas.
                 continue # Pasar al siguiente lote

            # Procesar cada imagen dentro del lote
            for j, image in enumerate(batch_images):
                current_page_number = start_page_batch + j # Número de la página actual (1-based)

                # Obtener configuración del tenant para rutas S3
                tenant_id = state.get('tenant_id', 'default')
                from app.services.tenant_config import get_tenant_config
                tenant_config = get_tenant_config(tenant_id)
                
                # Construir la key para la imagen en S3 usando prefijo del tenant
                image_key = f"{tenant_config.get_s3_prefix(docfile_id)}/images/page_{str(current_page_number).zfill(3)}.png"

                # Convertir la imagen a bytes en memoria
                img_bytes = BytesIO()
                try:
                    # Usamos thread para la operación de guardado si es síncrona y potencialmente bloqueante
                    await asyncio.to_thread(image.save, img_bytes, format='PNG')
                    img_bytes.seek(0)
                except Exception as save_e:
                     logging.error(f"Error al guardar página {current_page_number} a bytes para docfile {docfile_id}: {save_e}", exc_info=True)
                     continue # Saltar a la siguiente imagen/página si falla el guardado

                # Subir la imagen a S3
                try:
                    # Usamos thread para la operación de S3 put_object si no es async nativa
                    await asyncio.to_thread(
                        s3_client.put_object,
                        Bucket=S3_BUCKET_NAME,
                        Key=image_key,
                        Body=img_bytes.getvalue()
                    )
                    # Si la subida es exitosa, añadir la URL
                    s3_image_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{image_key}"
                    image_urls.append(s3_image_url)
                    processed_pages_count += 1 # Incrementar solo si la página se procesó y subió

                except Exception as s3_e:
                     logging.error(f"Error al subir página {current_page_number} ({image_key}) a S3 para docfile {docfile_id}: {s3_e}", exc_info=True)
                     # Decide si abortar todo o solo saltar esta página fallida
                     # Para este ejemplo, saltamos esta página y continuamos
                     continue

                # Liberar memoria explícitamente - PIL requiere .close() para liberar recursos internos
                image.close()
                image = None
                img_bytes.close()
                img_bytes = None

            # Liberar el lote de imágenes después de procesarlas todas
            for img in batch_images:
                if img:
                    img.close()
            batch_images.clear()
            batch_images = None
            
            # Forzar garbage collection después de cada batch de imágenes
            import gc
            from PIL import Image
            
            # Limpiar cache interno de PIL
            Image.MAX_IMAGE_PIXELS = None  # Resetear límites
            gc.collect()


            # --- Actualización de Progreso ---
            # Calcula el progreso basado en el número de páginas procesadas (exitosas o intentadas, ajusta si prefieres)
            current_progress_percent = min(int(((end_page_batch) / total_pages) * 100), 99) # Nunca 100% hasta el final

            # Actualiza el status si hemos superado el umbral o si es la primera actualización significativa
            if current_progress_percent >= next_progress_threshold and current_progress_percent > last_reported_progress_percent:
                 # Asegurarse de que el progreso reportado sea el umbral o el calculado si es mayor
                 report_progress = max(current_progress_percent, next_progress_threshold)
                 await update_status(
                     collection,
                     docfile_id,
                     "Convirtiendo", # El estado principal sigue siendo "Convirtiendo"
                     user_id,
                     progress=report_progress,
                     update_db=False, # No saturar la BD, solo actualizar WS
                     send_progress_ws=True
                 )
                 last_reported_progress_percent = report_progress
                 # Calcular el siguiente umbral. Usamos math.ceil para redondear hacia arriba al múltiplo del paso.
                 next_progress_threshold = math.ceil((current_progress_percent + 1) / PROGRESS_UPDATE_STEP_PERCENTAGE) * PROGRESS_UPDATE_STEP_PERCENTAGE
                 next_progress_threshold = min(next_progress_threshold, 100) # Asegurarse de no pasar de 100

        # --- Fin del bucle de lotes ---

        # Crear la lista de páginas para la BD a partir de las URLs recolectadas
        # Usamos las URLs recolectadas para asegurar que solo incluimos páginas subidas exitosamente
        pages = []
        # image_urls ya está en el orden correcto por número de página
        for idx, url in enumerate(image_urls):
             # El número de página real corresponde a la posición en image_urls + 1
             page_number = idx + 1
             pages.append({
                 "name": f"page_{str(page_number).zfill(3)}.png",
                 "image_path": url,
                 "number": page_number
             })


        # Guardamos la información de las páginas en la BD y actualizamos el estado final a 100% y "Convertido"
        await collection.update_one(
            {"_id": ObjectId(docfile_id)},
            {"$set": {"pages": pages, "page_count": total_pages, "status": "Convertido", "progress": 100}}
        )
        # Envía la actualización final por WebSocket asegurando el 100% y el estado final
        await update_status(collection, docfile_id, "Convertido", user_id, progress=100, page_count=total_pages ,update_db= False, send_progress_ws=True) # update_db=False aquí porque ya actualizamos arriba

        # NO liberar variables aquí - las necesitamos para el retorno
        # Las liberaremos después de usarlas para verificar el retorno
        
        # Forzar garbage collection después de procesar todas las imágenes
        gc.collect()

    except Exception as e:
        error_message = f"Error general durante la conversión de PDF a imágenes para docfile {docfile_id}: {str(e)}"
        logging.error(error_message, exc_info=True)
        # Si ocurre un error general (ej: descarga fallida, pdfinfo fallido, etc.)
        await update_status(collection, docfile_id, "Error", user_id, error_message=error_message, update_db=True, send_progress_ws=True)
        # No necesitamos retornar nada si hay un error, el pipeline se detendrá para este doc
        return None # Retornar None para detener el pipeline de Langchain

    finally:
        # Limpiar el directorio temporal SIEMPRE
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logging.debug(f"Directorio temporal limpiado para docfile {docfile_id}: {temp_dir}")
            except Exception as clean_e:
                 logging.error(f"Error limpiando directorio temporal {temp_dir} para docfile {docfile_id}: {clean_e}")

        # 🧹💥 MALLOC_TRIM despues de conversión PDF2IMG - atacar memoria zombie
        try_malloc_trim()

    # Solo retornar estado actualizado si el proceso fue exitoso
    # La forma más segura es verificar si image_urls no está vacío (significa que al menos 1 página se subió)
    # o si total_pages era 0 (caso que manejamos arriba)
    if image_urls or (total_pages == 0 and 'pages' in locals()): # pages exists for total_pages=0 case
         # Obtener datos actualizados del documento para el estado
         doc = await collection.find_one({"_id": ObjectId(docfile_id)})
         pages = [Page(**page) for page in doc.get("pages", [])] if doc else []
         total_pages = doc.get("page_count", 0) if doc else 0
         
         # Actualizar estado con páginas convertidas
         updated_state = state.copy()
         updated_state.update({
             "pages": pages,
             "total_pages": total_pages,
         })
         
         # Ahora SÍ liberar las variables grandes después de usarlas
         if 'image_urls' in locals():
             del image_urls
         if 'pages' in locals() and 'pages' != pages:  # No eliminar el pages que acabamos de crear
             del pages
         
         return updated_state
    else:
         # Si no se subió ninguna imagen (ej. todos los lotes fallaron) y no era un PDF de 0 páginas
         logging.warning(f"No se pudo procesar ninguna página para docfile {docfile_id}.")
         # Es probable que el estado ya esté en "Error" por un error loggeado antes,
         # pero aseguramos el retorno con error_message para indicar el problema.
         
         # Liberar variables incluso en caso de error
         if 'image_urls' in locals():
             del image_urls
         if 'pages' in locals():
             del pages
         
         return {**state, "error_message": "No se pudo procesar ninguna página del documento"}



# Pipeline legacy eliminado - ahora trabajamos directamente con funciones async


# ------------------------------------------------------------------------------------
# NODO LANGGRAPH: UPLOAD AND CONVERT NODE
# ------------------------------------------------------------------------------------
async def upload_convert_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo LangGraph para subida y conversión de PDF a imágenes.
    
    Ejecuta el proceso completo de:
    1. Subida del archivo PDF a S3
    2. Conversión del PDF a imágenes PNG
    3. Subida de las imágenes a S3
    4. Actualización del documento en MongoDB
    
    Args:
        state: Estado actual del procesamiento
        
    Returns:
        DocumentProcessingState: Estado actualizado con páginas convertidas
    """
    import logging
    import time
    from app.models.docs_processing_time import ProcessingTime
    
    # Iniciar tracking de tiempo
    start_time = time.perf_counter()
    
    try:
        # PASO 1: Subir archivo PDF a S3
        state = await upload_file(state)
        
        # PASO 2: Convertir PDF a imágenes
        state = await convert_pdf_to_images(state)
        
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
                    
                    # Actualizar el tiempo de upload_convert
                    processing_time.upload_convert = duration
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
                    
                    logging.info(f"Tiempo upload_convert para {docfile_id}: {duration:.2f}s - Notificado vía WebSocket")
            except Exception as e:
                logging.error(f"Error actualizando processing_time para upload_convert: {e}")
        
        # Limpiar datos de upload ya no necesarios para liberar memoria
        updated_state = state.copy()
        updated_state.update({
            "filename": None,
            "file_content": None,
        })
        
        return updated_state
        
    except Exception as e:
        logging.error(f"Error en upload_convert_node: {str(e)}")
        return {**state, "error_message": f"Error en upload y conversión: {str(e)}"}

