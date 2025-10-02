# path: app/services/s3_extract_balance.py

from bson import ObjectId

from app.core.database import docs_collection
from app.models.docs import DocFile

# Importes para LangGraph
from app.services.graph_state import DocumentProcessingState
from app.utils.base64_utils import get_base64_encoded_image

# Imports de LangChain legacy eliminados
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# Collection de documentos sobre la que vamos a trabajar
collection = docs_collection


# -------------------------------------------------------------------------------
# FUNCIÓN 1: OBTENER BALANCE (ESP) DEL DOCUMENTO DE LA BD
# -------------------------------------------------------------------------------

async def get_balance_pages_from_doc(state: DocumentProcessingState) -> DocumentProcessingState:
    """Obtiene las páginas identificadas como Estado de Situación Patrimonial (ESP)."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    docfile_id = state["docfile_id"]
    # Obtengo el documento de la base de datos
    docfile_data = await collection.find_one({"_id": ObjectId(docfile_id)})
    # Convertir documento a formato DocFile
    docfile = DocFile(**docfile_data)
    # Me quedo con las páginas reconocidas como balance, es decir ESP (Estado de Situación Patrimonial)
    balance_pages = [page for page in docfile.pages if page.recognized_info.is_balance_sheet]
    
    # Actualizar estado con páginas de balance
    updated_state = state.copy()
    updated_state.update({
        'balance_pages': balance_pages
    })
    return updated_state

# -------------------------------------------------------------------------------
# FUNCIÓN 2: EXTRAER DATOS DEL BALANCE USANDO LLM
# -------------------------------------------------------------------------------

async def extract_balance_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    """Extrae datos del balance usando IA desde las páginas identificadas como ESP."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    balance_pages = state['balance_pages']
    tenant_id = state.get('tenant_id', 'default')
    
    # Cargar configuración del tenant
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)
    
    # Usar prompt específico del tenant
    indications = tenant_config.prompt_extract_balance
    
    # Crear modelos dinámicos basados en campos del tenant
    from app.models.docs_balance import create_balance_data_model, BalanceDataForLLM, BalanceItem
    
    BalanceMainResults = tenant_config.create_balance_model()
    BalanceData = create_balance_data_model(BalanceMainResults)
    
    # Crear modelo LLM con structured output simplificado (sin campo 'concepto')
    model_text = "gemini-flash-latest"
    model = ChatGoogleGenerativeAI(
        model=model_text,
        max_tokens=None,
        max_retries=2,
        temperature=0
    ).with_structured_output(BalanceDataForLLM, method="json_mode")
    
    # Creo el esqueleto de los mensajes a enviar a la IA
    messages = [("system", "{indications}"),]
    # Append de cada página reconocida como Balance (ESP) a la lista de mensajes de la IA
    for page in balance_pages:
        image_number = balance_pages.index(page) + 1
        image_path = page.image_path  # Ahora la imagen está almacenada en S3 (URL pública)
        image_data = get_base64_encoded_image(image_path)  # Se descarga desde S3 si corresponde
        # Crear el mensaje y anexarlo a la lista de mensajes
        message = (
            "human",
            [
                {"type": "text", "text": f"IMAGEN {image_number}:\n"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
            ],
        )
        messages.append(message)
        # Liberar image_data inmediatamente después de usarla
        del image_data
    
    # Anexar inicio respuesta IA
    messages.append(("ai", "Aquí está el JSON solicitado:"))
    # Creo un template de prompt con la lista de mensajes, con todas las imagenes adjuntas
    template = ChatPromptTemplate(messages)
    # Creo el prompt final con las indicaciones específicas
    prompt = template.invoke({"indications": indications})
    # Con el prompt final llamo al modelo para extraer los datos (sin campo 'concepto')
    extracted_balance_llm = await model.ainvoke(prompt)
    
    # POST-PROCESAMIENTO: Agregar campo 'concepto' desde tenant_config
    # Convertir resultados principales agregando 'concepto' de la configuración
    resultados_principales_completos = []
    for item_llm in extracted_balance_llm.resultados_principales:
        # Obtener el concepto (etiqueta) desde la configuración del tenant
        concepto_label = tenant_config.balance_fields.get(item_llm.concepto_code, item_llm.concepto_code)
        
        # Crear BalanceItem completo con el campo 'concepto'
        item_completo = BalanceItem(
            concepto_code=item_llm.concepto_code,
            concepto=concepto_label,
            monto_actual=item_llm.monto_actual,
            monto_anterior=item_llm.monto_anterior
        )
        resultados_principales_completos.append(item_completo)
    
    # Crear BalanceData completo con concepto agregado
    extracted_balance = BalanceData(
        informacion_general=extracted_balance_llm.informacion_general,
        resultados_principales=resultados_principales_completos,
        detalles_activo=extracted_balance_llm.detalles_activo,
        detalles_pasivo=extracted_balance_llm.detalles_pasivo,
        detalles_patrimonio_neto=extracted_balance_llm.detalles_patrimonio_neto
    )
    
    # Liberar memoria explícitamente
    del extracted_balance_llm
    del messages
    del template
    del prompt
    
    # Actualizar estado con balance extraído (eliminar balance_pages para liberar memoria)
    updated_state = state.copy()
    updated_state.update({
        'extracted_balance': extracted_balance
    })
    # Eliminar balance_pages del estado para liberar memoria
    if 'balance_pages' in updated_state:
        del updated_state['balance_pages']

    return updated_state

# -------------------------------------------------------------------------------
# FUNCIÓN 3: ACTUALIZAR LOS DATOS DEL ESP EN LA BD
# -------------------------------------------------------------------------------

async def update_doc_balance(state: DocumentProcessingState) -> DocumentProcessingState:
    """Actualiza el documento en MongoDB con los datos extraídos del balance."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    docfile_id = state["docfile_id"]
    balance_data = state["extracted_balance"]
    balance_date = balance_data.informacion_general.periodo_actual
    balance_date_previous = balance_data.informacion_general.periodo_anterior  # Nuevo: fecha del período anterior
    
    await collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {
            "balance_date": balance_date,
            "balance_date_previous": balance_date_previous,  # Nuevo campo
            "balance_data": balance_data.model_dump()
        }}
    )
    
    # Actualizar estado con fechas de balance (eliminar extracted_balance para liberar memoria)
    updated_state = state.copy()
    updated_state.update({
        'balance_date': balance_date,
        'balance_date_previous': balance_date_previous
    })
    # Eliminar extracted_balance del estado para liberar memoria
    if 'extracted_balance' in updated_state:
        del updated_state['extracted_balance']
    
    return updated_state


# -------------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN DE BALANCE
# -------------------------------------------------------------------------------

async def extract_balance(state: DocumentProcessingState) -> DocumentProcessingState:
    """Ejecuta el proceso completo de extracción de balance (ESP)."""
    try:
        # PASO 1: Obtener páginas de balance
        state = await get_balance_pages_from_doc(state)
        
        # PASO 2: Extraer datos del balance usando IA
        state = await extract_balance_llm(state)
        
        # PASO 3: Actualizar documento en BD
        state = await update_doc_balance(state)
        
        return state
        
    except Exception as e:
        import logging
        logging.error(f"Error en extract_balancee: {str(e)}")
        return {**state, "error_message": f"Error en extracción de balance: {str(e)}"}
