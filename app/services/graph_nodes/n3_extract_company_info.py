# app/services/S3_extract_info.py

from bson import ObjectId

from app.core.database import docs_collection
from app.models.docs import DocFile

# Importes para LangGraph
from app.services.graph_state import DocumentProcessingState

# Imports de LangChain legacy eliminados
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from app.utils.base64_utils import get_base64_encoded_image
from app.models.docs_company_info import CompanyInfo
from app.utils.prompts import prompt_extract_company_info

# Collection de documentos sobre la que vamos a trabajar
collection = docs_collection

# Defino el modelo a utilizar, con el tipo de dato esperado
model_text = "gemini-flash-latest"
model = ChatGoogleGenerativeAI(model=model_text, max_tokens=15000, max_retries=1).with_structured_output(CompanyInfo)


# -------------------------------------------------------------------------------
# FUNCIÓN 1: OBTENER LAS PÁGINAS DE INFORMACIÓN GENERAL EN BASE A REGLAS
# -------------------------------------------------------------------------------
async def get_company_info_pages(state: DocumentProcessingState) -> DocumentProcessingState:
    """Obtiene y clasifica las páginas que contienen información de la empresa."""
    # 1. Chequeo de stop
    if state.get("stop"):
        return state
    # 2. Obtención del docfile y sus páginas
    docfile_id = state["docfile_id"]
    docfile_data = await collection.find_one({"_id": ObjectId(docfile_id)})
    docfile = DocFile(**docfile_data)
    pages = docfile.pages

    # Setea todas las páginas a company_info=False en memoria antes de clasificar
    for page in pages:
        page.company_info = False
    # 3. Clasificación de cada página según las categorías TOP
    def classify(page):
        ri = page.recognized_info
        deg0 = ri.original_orientation_degrees == 0
        # Clasificación según las categorías TOP (A: si es deg0, B: si no)

        # TOP1: La pagina contiene CUIT, Nombre, Actividad, Informe de auditoría y Domicilio
        if ri.has_company_cuit and ri.has_company_name and ri.has_company_activity and ri.audit_report and ri.has_company_address:
            return "TOP1A" if deg0 else "TOP1B"
        # TOP2: La pagina contiene CUIT, Nombre, Actividad e Informe de auditoría
        if ri.has_company_cuit and ri.has_company_name and ri.has_company_activity and ri.audit_report:
            return "TOP2A" if deg0 else "TOP2B"
        # TOP3: La pagina contiene CUIT, Nombre y Actividad
        if ri.has_company_cuit and ri.has_company_name and ri.has_company_activity:
            return "TOP3A" if deg0 else "TOP3B"
        # TOP4: La pagina contiene CUIT, Nombre e Informe de auditoría
        if ri.has_company_cuit and ri.has_company_name and ri.audit_report:
            return "TOP4A" if deg0 else "TOP4B"
        # TOP5: La pagina contiene CUIT y Nombre
        if ri.has_company_cuit and ri.has_company_name:
            return "TOP5A" if deg0 else "TOP5B"
        
        # Clasificaciones menos prioritarias SIN CUIT
        # TOP6: La pagina contiene Nombre, Actividad, Informe de auditoría y Domicilio (SIN CUIT)
        if ri.has_company_name and ri.has_company_activity and ri.audit_report and ri.has_company_address:
            return "TOP6A" if deg0 else "TOP6B"
        # TOP7: La pagina contiene Nombre, Actividad e Informe de auditoría (SIN CUIT)
        if ri.has_company_name and ri.has_company_activity and ri.audit_report:
            return "TOP7A" if deg0 else "TOP7B"
        # TOP8: La pagina contiene Nombre y Actividad (SIN CUIT)
        if ri.has_company_name and ri.has_company_activity:
            return "TOP8A" if deg0 else "TOP8B"
        # TOP9: La pagina contiene Nombre e Informe de auditoría (SIN CUIT)
        if ri.has_company_name and ri.audit_report:
            return "TOP9A" if deg0 else "TOP9B"
        # TOP10: La pagina contiene solo Nombre (SIN CUIT)
        if ri.has_company_name:
            return "TOP10A" if deg0 else "TOP10B"
        
        return None

    # 4. Indexación de páginas por categoría
    categorized = {k: [] for k in ["TOP1A","TOP1B","TOP2A","TOP2B","TOP3A","TOP3B","TOP4A","TOP4B","TOP5A","TOP5B",
                                    "TOP6A","TOP6B","TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]}
    for page in pages:
        category = classify(page)
        if category:
            categorized[category].append(page)

    # 5. Helpers para obtener la primera o última página de una lista
    def first(list):
        return list[0] if list else None
    def last(list):
        return list[-1] if list else None

    selected_company_info_pages = []

    # REGLA 1: Si hay TOP1
    top1 = first(categorized["TOP1A"]) or first(categorized["TOP1B"])
    if top1:
        priorities = ["TOP3A","TOP3B","TOP4A","TOP4B","TOP5A","TOP5B","TOP6A","TOP6B","TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
        additional = None
        for category in priorities:
            for page in categorized[category]:
                if page.id != top1.id:
                    additional = page
                    break
            if additional:
                break
        selected_company_info_pages = [top1] if not additional else [top1, additional]
    else:
        # REGLA 2: Si hay TOP2 (y no hay TOP1)
        top2 = first(categorized["TOP2A"]) or first(categorized["TOP2B"])
        if top2:
            domicilio = [page for page in pages if page.recognized_info.has_company_address and page.id != top2.id]
            domicilio_deg0 = [page for page in domicilio if page.recognized_info.original_orientation_degrees == 0]
            additional = first(domicilio_deg0) or first(domicilio)
            if not additional:
                priorities = ["TOP3A","TOP3B","TOP4A","TOP4B","TOP5A","TOP5B","TOP6A","TOP6B","TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
                for category in priorities:
                    for page in categorized[category]:
                        if page.id != top2.id:
                            additional = page
                            break
                    if additional:
                        break
            selected_company_info_pages = [top2] if not additional else [top2, additional]
        else:
            # REGLA 3: Si hay TOP3 (y no hay TOP1 ni TOP2)
            top3 = first(categorized["TOP3A"]) or first(categorized["TOP3B"])
            if top3:
                auditor = [page for page in pages if page.recognized_info.audit_report and page.id != top3.id]
                auditor_deg0 = [page for page in auditor if page.recognized_info.original_orientation_degrees == 0]
                additional = first(auditor_deg0) or first(auditor)
                if not additional:
                    top3_others = [page for page in categorized["TOP3A"]+categorized["TOP3B"] if page.id != top3.id]
                    additional = first([page for page in top3_others if page.recognized_info.original_orientation_degrees == 0]) or first(top3_others)
                if not additional:
                    top5 = [page for page in categorized["TOP5A"]+categorized["TOP5B"]]
                    additional = first([page for page in top5 if page.id != top3.id and page.recognized_info.original_orientation_degrees == 0]) or first([page for page in top5 if page.id != top3.id])
                if not additional:
                    cuit_pages = [page for page in pages if page.recognized_info.has_company_cuit and page.id != top3.id]
                    additional = first([page for page in cuit_pages if page.recognized_info.original_orientation_degrees == 0]) or first(cuit_pages)
                if not additional:
                    # Buscar en categorías sin CUIT
                    priorities_no_cuit = ["TOP6A","TOP6B","TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
                    for category in priorities_no_cuit:
                        for page in categorized[category]:
                            if page.id != top3.id:
                                additional = page
                                break
                        if additional:
                            break
                selected_company_info_pages = [top3] if not additional else [top3, additional]
            else:
                # REGLA 4: Si hay TOP4 (y no hay TOP1, TOP2 ni TOP3)
                top4 = first(categorized["TOP4A"]) or first(categorized["TOP4B"])
                if top4:
                    top5 = [page for page in categorized["TOP5A"]+categorized["TOP5B"] if page.id != top4.id]
                    additional = first([page for page in top5 if page.recognized_info.original_orientation_degrees == 0]) or first(top5)
                    if not additional:
                        cuit_pages = [page for page in pages if page.recognized_info.has_company_cuit and page.id != top4.id]
                        additional = first([page for page in cuit_pages if page.recognized_info.original_orientation_degrees == 0]) or first(cuit_pages)
                    if not additional:
                        # Buscar en categorías sin CUIT
                        priorities_no_cuit = ["TOP6A","TOP6B","TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
                        for category in priorities_no_cuit:
                            for page in categorized[category]:
                                if page.id != top4.id:
                                    additional = page
                                    break
                            if additional:
                                break
                    selected_company_info_pages = [top4] if not additional else [top4, additional]
                else:
                    # REGLA 5: Si hay TOP5 (y no hay TOP1, TOP2, TOP3 ni TOP4)
                    top5 = first(categorized["TOP5A"]) or first(categorized["TOP5B"])
                    if top5:
                        top5_others = [page for page in categorized["TOP5A"]+categorized["TOP5B"] if page.id != top5.id]
                        additional = last([page for page in top5_others if page.recognized_info.original_orientation_degrees == 0]) or last(top5_others)
                        if not additional:
                            cuit_pages = [page for page in pages if page.recognized_info.has_company_cuit and page.id != top5.id]
                            additional = first([page for page in cuit_pages if page.recognized_info.original_orientation_degrees == 0]) or first(cuit_pages)
                        if not additional:
                            # Buscar en categorías sin CUIT
                            priorities_no_cuit = ["TOP6A","TOP6B","TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
                            for category in priorities_no_cuit:
                                for page in categorized[category]:
                                    if page.id != top5.id:
                                        additional = page
                                        break
                                if additional:
                                    break
                        selected_company_info_pages = [top5] if not additional else [top5, additional]
                    else:
                        # REGLA 6: Si hay TOP6 (y no hay TOP1-TOP5)
                        top6 = first(categorized["TOP6A"]) or first(categorized["TOP6B"])
                        if top6:
                            priorities = ["TOP7A","TOP7B","TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
                            additional = None
                            for category in priorities:
                                for page in categorized[category]:
                                    if page.id != top6.id:
                                        additional = page
                                        break
                                if additional:
                                    break
                            selected_company_info_pages = [top6] if not additional else [top6, additional]
                        else:
                            # REGLA 7: Si hay TOP7 (y no hay TOP1-TOP6)
                            top7 = first(categorized["TOP7A"]) or first(categorized["TOP7B"])
                            if top7:
                                priorities = ["TOP8A","TOP8B","TOP9A","TOP9B","TOP10A","TOP10B"]
                                additional = None
                                for category in priorities:
                                    for page in categorized[category]:
                                        if page.id != top7.id:
                                            additional = page
                                            break
                                    if additional:
                                        break
                                selected_company_info_pages = [top7] if not additional else [top7, additional]
                            else:
                                # REGLA 8: Si hay TOP8 (y no hay TOP1-TOP7)
                                top8 = first(categorized["TOP8A"]) or first(categorized["TOP8B"])
                                if top8:
                                    priorities = ["TOP9A","TOP9B","TOP10A","TOP10B"]
                                    additional = None
                                    for category in priorities:
                                        for page in categorized[category]:
                                            if page.id != top8.id:
                                                additional = page
                                                break
                                        if additional:
                                            break
                                    selected_company_info_pages = [top8] if not additional else [top8, additional]
                                else:
                                    # REGLA 9: Si hay TOP9 (y no hay TOP1-TOP8)
                                    top9 = first(categorized["TOP9A"]) or first(categorized["TOP9B"])
                                    if top9:
                                        top10 = [page for page in categorized["TOP10A"]+categorized["TOP10B"] if page.id != top9.id]
                                        additional = first([page for page in top10 if page.recognized_info.original_orientation_degrees == 0]) or first(top10)
                                        selected_company_info_pages = [top9] if not additional else [top9, additional]
                                    else:
                                        # REGLA 10: Si hay TOP10 (y no hay TOP1-TOP9)
                                        top10 = first(categorized["TOP10A"]) or first(categorized["TOP10B"])
                                        if top10:
                                            top10_others = [page for page in categorized["TOP10A"]+categorized["TOP10B"] if page.id != top10.id]
                                            additional = last([page for page in top10_others if page.recognized_info.original_orientation_degrees == 0]) or last(top10_others)
                                            selected_company_info_pages = [top10] if not additional else [top10, additional]
                                        else:
                                            # REGLA 11: Si sólo hay páginas con CUIT
                                            cuit_pages = [page for page in pages if page.recognized_info.has_company_cuit]
                                            if cuit_pages:
                                                deg0 = [page for page in cuit_pages if page.recognized_info.original_orientation_degrees == 0]
                                                if len(deg0) >= 2:
                                                    selected_company_info_pages = [deg0[0], deg0[-1]]
                                                elif len(deg0) == 1 and len(cuit_pages) > 1:
                                                    selected_company_info_pages = [deg0[0], cuit_pages[-1]]
                                                elif len(cuit_pages) >= 2:
                                                    selected_company_info_pages = [cuit_pages[0], cuit_pages[-1]]
                                                else:
                                                    selected_company_info_pages = [cuit_pages[0]]
                                            else:
                                                # REGLA 12: Si no se encuentra nada relevante
                                                selected_company_info_pages = []

    # Obtener los ids de las páginas seleccionadas
    page_ids_selected = set(page.id for page in selected_company_info_pages)
    # Actualizar en memoria el campo company_info de las páginas seleccionadas
    for page in pages:
        if page.id in page_ids_selected:
            page.company_info = True
        else:
            page.company_info = False
    # Actualizar en la BD el campo company_info de todas las páginas de una sola vez
    await collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {"pages": [page.model_dump() for page in pages]}}
    )
    
    # Actualizar estado con páginas de información de empresa
    updated_state = state.copy()
    updated_state.update({
        "company_info": selected_company_info_pages
    })
    return updated_state



# -------------------------------------------------------------------------------
# RUNNABLE 2: EXTRAER INFORMACIÓN DE EMPRESA USANDO LLM
# -------------------------------------------------------------------------------

indications= prompt_extract_company_info

async def extract_company_info_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    """Extrae información de la empresa usando IA desde las páginas identificadas."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    # Obtengo las páginas de información general de la empresa
    company_info_pages = state["company_info"]

    # Creo el esqueleto de los mensajes a enviar a la IA
    messages = [("system", "{indications}"),]
    # Append de cada página reconocida como página con información de la empresa a la lista de mensajes
    for page in company_info_pages:
        image_number = company_info_pages.index(page) + 1
        image_path = page.image_path  # Imagen almacenada en S3 (URL pública)
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
    # Con el prompt final llamo al modelo para extraer los datos
    extracted_company_info = await model.ainvoke(prompt)

    # Liberar memoria explícitamente
    del messages
    del template
    del prompt

    # Actualizar estado con información de empresa extraída (eliminar company_info para liberar memoria)
    updated_state = state.copy()
    updated_state.update({
        'extracted_company_info': extracted_company_info
    })
    # Eliminar company_info del estado para liberar memoria
    if 'company_info' in updated_state:
        del updated_state['company_info']

    return updated_state



# -------------------------------------------------------------------------------
# RUNNABLE 3: ACTUALIZAR LOS DATOS DE LA EMPRESA DUEÑA DEL DOCUMENTO EN LA BD
# -------------------------------------------------------------------------------

async def update_company_info(state: DocumentProcessingState) -> DocumentProcessingState:
    """Actualiza el documento en MongoDB con la información extraída de la empresa."""
    # Si el pipeline fue detenido previamente, retorna inmediatamente sin hacer nada
    if state.get("stop"):
        return state
    
    docfile_id = state["docfile_id"]
    company_info = state['extracted_company_info'].model_dump()

    # Actualizo el documento en la colección con los datos extraídos
    await collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {
            "company_info": company_info
        }}
    )

    # Preparar company_info sin campos innecesarios para el estado
    company_info_filtered = company_info.copy()
    # Droppear campos que no se necesitan más en el estado
    if 'company_activity' in company_info_filtered:
        del company_info_filtered['company_activity']
    if 'company_address' in company_info_filtered:
        del company_info_filtered['company_address']

    # Actualizar estado (eliminar extracted_company_info para liberar memoria)
    updated_state = state.copy()
    updated_state.update({
        'extracted_company_info': company_info_filtered
    })
    
    return updated_state


# -------------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN DE INFORMACIÓN DE EMPRESA
# -------------------------------------------------------------------------------

async def extract_company_info(state: DocumentProcessingState) -> DocumentProcessingState:
    """Ejecuta el proceso completo de extracción de información de empresa."""
    try:
        # PASO 1: Obtener páginas de información de empresa
        state = await get_company_info_pages(state)
        
        # PASO 2: Extraer información de empresa usando IA
        state = await extract_company_info_llm(state)
        
        # PASO 3: Actualizar documento en BD
        state = await update_company_info(state)
        
        return state
        
    except Exception as e:
        import logging
        logging.error(f"Error en extract_company_info: {str(e)}")
        return {**state, "error_message": f"Error en extracción de información de empresa: {str(e)}"}
