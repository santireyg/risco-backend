# path: app/services/s3_extract_income.py

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
# FUNCIÓN 1: OBTENER ESTADO DE RESULTADOS (ER) DEL DOCUMENTO, DE LA BD
# -------------------------------------------------------------------------------

async def get_income_pages_from_doc(state: DocumentProcessingState) -> DocumentProcessingState:
    """Obtiene las páginas identificadas como Estado de Resultados (ER)."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    docfile_id = state["docfile_id"]
    # Obtengo el documento de la base de datos
    docfile_data = await collection.find_one({"_id": ObjectId(docfile_id)})
    # Convertir documento a formato DocFile
    docfile = DocFile(**docfile_data)
    # Me quedo con las páginas reconocidas como Income, es decir ER (Estado de Resultados)
    income_pages = [page for page in docfile.pages if page.recognized_info.is_income_statement_sheet]
    
    # Actualizar estado con páginas de estado de resultados
    updated_state = state.copy()
    updated_state.update({
        'income_pages': income_pages
    })
    return updated_state


# -------------------------------------------------------------------------------
# FUNCIÓN 2: EXTRAER DATOS DEL ESTADO DE RESULTADOS (ER) USANDO LLM
# -------------------------------------------------------------------------------

async def extract_income_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    """Extrae datos del estado de resultados usando IA desde las páginas identificadas como ER."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    income_pages = state['income_pages']
    tenant_id = state.get('tenant_id', 'default')
    
    # Cargar configuración del tenant
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)
    
    # Usar prompt específico del tenant
    indications = tenant_config.prompt_extract_income
    
    # Crear modelos dinámicos basados en campos del tenant
    from app.models.docs_income import create_income_data_model, IncomeStatementDataForLLM, IncomeStatementItem
    
    IncomeStatementMainResults = tenant_config.create_income_model()
    IncomeStatementData = create_income_data_model(IncomeStatementMainResults)
    
    # Crear modelo LLM con structured output simplificado (sin campo 'concepto')
    model_text = "gemini-flash-latest"
    model = ChatGoogleGenerativeAI(
        model=model_text,
        max_tokens=None,
        max_retries=2,
        temperature=0
    ).with_structured_output(IncomeStatementDataForLLM, method="json_mode")
    
    # Creo el esqueleto de los mensajes a enviar a la IA
    messages = [("system", "{indications}"),]
    # Append de cada página reconocida como Estado de Resultados (ER) a la lista de mensajes de la IA
    for page in income_pages:
        image_number = income_pages.index(page) + 1
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
    extracted_income_llm = await model.ainvoke(prompt)
    
    # POST-PROCESAMIENTO: Agregar campo 'concepto' desde tenant_config
    # Convertir resultados principales agregando 'concepto' de la configuración
    resultados_principales_completos = []
    for item_llm in extracted_income_llm.resultados_principales:
        # Obtener el concepto (etiqueta) desde la configuración del tenant
        concepto_label = tenant_config.income_fields.get(item_llm.concepto_code, item_llm.concepto_code)
        
        # Crear IncomeStatementItem completo con el campo 'concepto'
        item_completo = IncomeStatementItem(
            concepto_code=item_llm.concepto_code,
            concepto=concepto_label,
            monto_actual=item_llm.monto_actual,
            monto_anterior=item_llm.monto_anterior
        )
        resultados_principales_completos.append(item_completo)
    
    # Crear IncomeStatementData completo con concepto agregado
    extracted_income = IncomeStatementData(
        informacion_general=extracted_income_llm.informacion_general,
        resultados_principales=resultados_principales_completos,
        detalles_estado_resultados=extracted_income_llm.detalles_estado_resultados
    )

    # Liberar memoria explícitamente
    del extracted_income_llm
    del messages
    del template
    del prompt

    # Actualizar estado con estado de resultados extraído (eliminar income_pages para liberar memoria)
    updated_state = state.copy()
    updated_state.update({
        'extracted_income': extracted_income
    })
    # Eliminar income_pages del estado para liberar memoria
    if 'income_pages' in updated_state:
        del updated_state['income_pages']

    return updated_state


# -------------------------------------------------------------------------------
# FUNCIÓN 3: ACTUALIZAR LOS DATOS DEL ER EN LA BD
# -------------------------------------------------------------------------------

async def update_doc_income(state: DocumentProcessingState) -> DocumentProcessingState:
    """Actualiza el documento en MongoDB con los datos extraídos del estado de resultados."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    docfile_id = state["docfile_id"]
    income_data = state["extracted_income"]
    
    await collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {
            "income_statement_data": income_data.model_dump()
        }}
    )
    
    # Actualizar estado (eliminar extracted_income para liberar memoria)
    updated_state = state.copy()
    # Eliminar extracted_income del estado para liberar memoria
    if 'extracted_income' in updated_state:
        del updated_state['extracted_income']
    
    return updated_state


# -------------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN DE ESTADO DE RESULTADOS
# -------------------------------------------------------------------------------

async def extract_income(state: DocumentProcessingState) -> DocumentProcessingState:
    """Ejecuta el proceso completo de extracción de estado de resultados (ER)."""
    try:
        # PASO 1: Obtener páginas de estado de resultados
        state = await get_income_pages_from_doc(state)
        
        # PASO 2: Extraer datos del estado de resultados usando IA
        state = await extract_income_llm(state)
        
        # PASO 3: Actualizar documento en BD
        state = await update_doc_income(state)
        
        return state
        
    except Exception as e:
        import logging
        logging.error(f"Error en extract_income: {str(e)}")
        return {**state, "error_message": f"Error en extracción de estado de resultados: {str(e)}"}

