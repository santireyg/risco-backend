# app/services/s2_recognize.py

from bson import ObjectId
import gc
from PIL import Image
from urllib.parse import urlparse
from io import BytesIO

# Importes para LangGraph
from app.services.graph_state import DocumentProcessingState 

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.rate_limiters import InMemoryRateLimiter

from app.core.database import docs_collection
from app.models.docs import DocFile, Page
from app.models.docs_recognition import RecognizedInfoForLLM
from app.utils.prompts import prompt_recognize_pages
from app.utils.base64_utils import get_base64_encoded_image
from app.utils.status_notifier import update_status
from app.utils.memory_cleanup import try_malloc_trim  ##🧹 MALLOC_TRIM para recognize

# Importamos el cliente de S3 y configuración
from app.core.s3_client import s3_client
from app.core.config import S3_BUCKET_NAME

# Colección de documentos sobre la que vamos a trabajar
collection = docs_collection

# MODELO DE IA A UTILIZAR
AI_MODEL = "gpt-4o"

# ------------------------------------------------------------------------------- 
# FUNCIÓN 1: OBTENER EL DOCUMENTO DE LA BASE DE DATOS 
# -------------------------------------------------------------------------------

async def get_pages_from_doc(state: DocumentProcessingState) -> DocumentProcessingState:
    """Obtiene las páginas del documento desde MongoDB y actualiza el estado."""
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)

    # Obtengo el documento de la base de datos
    docfile_data = await collection.find_one({"_id": ObjectId(docfile_id)})
    if not docfile_data:
        await update_status(collection, docfile_id, "Error", user_id, error_message="Documento no encontrado")
        raise ValueError(f"Documento con ID {docfile_id} no encontrado")
    
    # Convertir documento a formato DocFile
    docfile = DocFile(**docfile_data)
    pages = docfile.pages
    total_pages = len(pages)

    # Update Status: Reconociendo (inicial, 0%)
    await update_status(collection, docfile_id, "Reconociendo", user_id, progress=0, update_db=False, send_progress_ws=True)

    # Actualizar estado con páginas obtenidas
    updated_state = state.copy()
    updated_state.update({
        "pages": pages,
        "total_pages": total_pages,
    })
    
    return updated_state



# ------------------------------------------------------------------------------- 
# FUNCIÓN 2: RECONOCER CON IA LA INFORMACIÓN DE CADA PÁGINA
# (es Estado de resultados? es situacion patrimonial? grados de rotación, etc.)
# -------------------------------------------------------------------------------

# Limitador de RPM a la IA
rate_limiter = InMemoryRateLimiter(requests_per_second=2.5) # 250 Reqs cada 100 segundos (150 RPM)
# Limitador de concurrencia
concurrency_limit = 15  # Máximo de 15 páginas procesadas en paralelo

model = ChatOpenAI(model=AI_MODEL, max_retries=2, temperature=0, rate_limiter=rate_limiter).with_structured_output(RecognizedInfoForLLM)
#model = ChatGoogleGenerativeAI(model=AI_MODEL, thinking_budget=0, max_retries=2, temperature=0, rate_limiter=rate_limiter).with_structured_output(RecognizedInfoForLLM)

indications = prompt_recognize_pages

async def recognize_page(page: Page) -> Page:
    page_path = page.image_path  # URL de S3
    image_data = get_base64_encoded_image(page_path)
    messages = [
        ("system", "{indications}"),
        ("human", [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}])
    ]
    # Creo un template de prompt a partir de la lista de mensajes
    template = ChatPromptTemplate(messages)
    # Adjunto al template las indicaciones personalizadas y la imagen
    prompt = template.invoke({"image_data": image_data, "indications": indications})
    
    # Liberar image_data inmediatamente después de crear el prompt
    del image_data
    
    # Invoco el modelo con el prompt final para reconocer la imagen
    recognized_info = await model.ainvoke(prompt)
    page.recognized_info = recognized_info

    # Liberar variables del prompt
    del messages
    del template
    del prompt

    return page

# Función para procesar el reconocimiento de varias páginas en batch con progreso manual
async def batch_recognize(state: DocumentProcessingState) -> DocumentProcessingState:
    """Procesa el reconocimiento OCR de todas las páginas en paralelo con reporte de progreso."""
    pages = state["pages"]
    docfile_id = state["docfile_id"]
    requester = state["requester"]
    user_id = str(requester.id)
    total_pages = state["total_pages"]

    # Crear semáforo para limitar concurrencia
    import asyncio
    semaphore = asyncio.Semaphore(concurrency_limit)
    
    # Contador de páginas completadas
    completed_count = 0
    
    async def recognize_with_progress(page: Page, index: int) -> Page:
        """Reconoce una página y reporta progreso."""
        nonlocal completed_count
        
        async with semaphore:
            # Reconocer la página
            recognized_page = await recognize_page(page)
            
            # Incrementar contador y calcular progreso
            completed_count += 1
            progress = min(int((completed_count / total_pages) * 100), 99)
            
            # Enviar update de progreso cada cierto porcentaje o cada N páginas
            # Para evitar saturar el websocket, enviamos cada 5% de progreso o cada 5 páginas
            if completed_count % max(1, total_pages // 20) == 0 or completed_count == total_pages:
                await update_status(
                    collection,
                    docfile_id,
                    "Reconociendo",
                    user_id,
                    progress=progress,
                    update_db=False,
                    send_progress_ws=True
                )
            
            return recognized_page
    
    # Procesar todas las páginas en paralelo con límite de concurrencia
    recognized_pages = await asyncio.gather(
        *[recognize_with_progress(page, i) for i, page in enumerate(pages)]
    )

    # Actualizar estado con páginas reconocidas
    updated_state = state.copy()
    updated_state.update({
        "pages": recognized_pages
    })
    
    # Liberar la referencia temporal
    del recognized_pages

    return updated_state



# ------------------------------------------------------------------------------- 
# FUNCIÓN 3: ROTAR LAS PÁGINAS APAISADAS
# -------------------------------------------------------------------------------
async def rotate_images(state: DocumentProcessingState) -> DocumentProcessingState:
    """Rota las imágenes que necesitan corrección de orientación según el reconocimiento OCR."""
    pages = state['pages']
    
    for page in pages:
        if page.recognized_info.original_orientation_degrees != 0:
            image_url = page.image_path  # La imagen está en S3, es una URL
            # Extraer la key del objeto S3 a partir de la URL
            parsed = urlparse(image_url)
            key = parsed.path.lstrip("/")
            # Descargar la imagen desde S3
            response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
            image_bytes = response['Body'].read()
            # Abrir la imagen con PIL
            img = Image.open(BytesIO(image_bytes))
            # Rotar la imagen
            rotated_img = img.rotate(-page.recognized_info.original_orientation_degrees, expand=True)
            # Guardar la imagen rotada en un buffer
            output_buffer = BytesIO()
            rotated_img.save(output_buffer, format='PNG')
            output_buffer.seek(0)
            # Reemplazar la imagen original en S3 con la imagen rotada
            s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=output_buffer.getvalue())
            
            # Liberar variables de imagen correctamente para PIL
            img.close()
            rotated_img.close()
            output_buffer.close()
            
            img = None
            rotated_img = None
            output_buffer = None
            del image_bytes
    
    # Retornar el estado sin modificaciones (las páginas ya se actualizaron por referencia)
    return state



# ------------------------------------------------------------------------------- 
# FUNCIÓN 4: ACTUALIZAR LA BASE DE DATOS
# -------------------------------------------------------------------------------
async def update_doc_pages(state: DocumentProcessingState) -> DocumentProcessingState:
    """Actualiza el documento en MongoDB con las páginas reconocidas y estado final."""
    docfile_id = state["docfile_id"]
    pages = state["pages"]
    requester = state["requester"]
    user_id = str(requester.id)

    # Update Status: Reconocido
    await update_status(collection, docfile_id, "Reconocido", user_id, progress=100, update_db=False)    
    await collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {
            "status": "Reconocido",
            "pages": [page.model_dump(by_alias=True) for page in pages],
            "progress": 100
        }}
    )
    
    # Actualizar estado con progreso completado
    updated_state = state.copy()
    updated_state.update({
        "progress": 1.0  # 100% completado
    })
    
    # Forzar garbage collection al final del reconocimiento
    gc.collect()
    
    # 🧹⚡ MALLOC_TRIM despues de reconocimiento OCR - liberar memoria zombie
    try_malloc_trim()
    
    return updated_state



# Pipeline legacy eliminado - ahora trabajamos directamente con funciones async


# ------------------------------------------------------------------------------------
# NODO LANGGRAPH: RECOGNIZE NODE
# ------------------------------------------------------------------------------------
async def recognize_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """
    Nodo LangGraph para reconocimiento OCR y clasificación de páginas.
    
    Ejecuta el proceso completo de:
    1. Obtención de páginas del documento
    2. Reconocimiento OCR con IA (identificación de ESP/ER)
    3. Rotación de imágenes según orientación detectada
    4. Actualización del documento en MongoDB
    
    Args:
        state: Estado actual del procesamiento
        
    Returns:
        DocumentProcessingState: Estado actualizado con páginas reconocidas
    """
    import logging
    import time
    from app.models.docs_processing_time import ProcessingTime
    from bson import ObjectId
    from app.core.database import docs_collection
    
    # Iniciar tracking de tiempo
    start_time = time.perf_counter()
    
    try:
        # PASO 1: Obtener páginas del documento
        state = await get_pages_from_doc(state)
        
        # PASO 2: Reconocimiento OCR en batch
        state = await batch_recognize(state)
        
        # PASO 3: Rotación de imágenes
        state = await rotate_images(state)
        
        # PASO 4: Actualización de base de datos
        state = await update_doc_pages(state)
        
        # Calcular duración
        duration = time.perf_counter() - start_time
        
        # Actualizar processing_time en la BD y notificar vía WebSocket
        docfile_id = state.get("docfile_id")
        requester = state.get("requester")
        if docfile_id and requester:
            user_id = str(requester.id)
            try:
                # Obtener el documento actual
                document = await docs_collection.find_one({"_id": ObjectId(docfile_id)})
                if document:
                    # Obtener o crear processing_time
                    processing_time_data = document.get("processing_time", {})
                    processing_time = ProcessingTime(**processing_time_data) if processing_time_data else ProcessingTime()
                    
                    # Actualizar el tiempo de recognize
                    processing_time.recognize = duration
                    processing_time.update_total()
                    
                    # Guardar en BD y notificar vía WebSocket
                    from app.utils.status_notifier import update_status
                    current_status = document.get("status", "Procesando")
                    await update_status(
                        collection=docs_collection,
                        docfile_id=docfile_id,
                        new_status=current_status,
                        user_id=user_id,
                        processing_time=processing_time.model_dump(),
                        update_db=True
                    )
                    
                    logging.info(f"Tiempo recognize para {docfile_id}: {duration:.2f}s - Notificado vía WebSocket")
            except Exception as e:
                logging.error(f"Error actualizando processing_time para recognize: {e}")
        
        return state
        
    except Exception as e:
        logging.error(f"Error en recognize_node: {str(e)}")
        return {**state, "error_message": f"Error en reconocimiento: {str(e)}"}


