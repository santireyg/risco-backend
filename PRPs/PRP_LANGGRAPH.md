# Product Requirements Prompt (PRP) - Migración a LangGraph

## Contexto del Sistema Actual

### Arquitectura Actual

La API de Risco es un sistema de análisis automatizado de estados financieros construido con FastAPI que procesa documentos PDF de balances contables. El sistema actual utiliza LangChain con `RunnableSequence` y `RunnableParallel` para orquestar el procesamiento de documentos a través de 4 etapas principales.

### Estructura del Codebase

```
app/
├── services/
│   ├── s0_pipelines.py          # Orquestador principal con pipelines LangChain
│   ├── s1_upload_convert.py     # Subida y conversión PDF → imágenes
│   ├── s2_recognize.py          # Reconocimiento OCR y clasificación de páginas
│   ├── s3_extract.py            # Extracción de datos contables (ESP/ER)
│   ├── s3_extract_balance.py    # Extracción específica de balance (ESP)
│   ├── s3_extract_income.py     # Extracción específica de estado de resultados (ER)
│   ├── S3_extract_company_info.py # Extracción de información de empresa
│   ├── s4_validate.py           # Validación de ecuaciones contables
│   └── task_queue.py            # Sistema de cola asíncrona para procesamiento
├── api/endpoints/
│   └── processing.py            # Endpoints REST para disparar procesamiento
├── core/
│   └── auth.py                  # Autenticación JWT con get_current_user()
└── models/
    ├── users.py                 # Modelos User y UserPublic
    └── docs.py                  # Modelos DocFile, Page, etc.
```

### Flujo Actual de Procesamiento

#### Tipos de Operaciones Disponibles (s0_pipelines.py):

1. **`complete_process`**: upload_convert → recognize → extract → validate
2. **`recognize_and_extract`**: recognize → extract → validate
3. **`extract`**: extract → validate
4. **`validate`**: validate

#### Etapas de Procesamiento:

- **S1 (upload_convert)**: Sube PDF a S3, convierte a imágenes, crea DocFile en MongoDB
- **S2 (recognize)**: Aplica OCR y clasificación (pero mediante LLMs y LangChain), principalmente para identificar páginas de ESP (Estado de Situación Patrmonial) y ER (Estado de Resultados)
- **S3 (extract)**: Ejecuta en paralelo extracción de balance, estado de resultados e info de empresa
- **S4 (validate)**: Valida ecuaciones contables fundamentales (A = P + PN, etc.)

#### Manejo de Parámetros Actual:

Cada stage recibe un diccionario `params` con:

```python
params = {
    "docfile_id": str,
    "current_user": {"first_name": str, "last_name": str, "id": str},
    "filename": str,  # solo en S1
    "file_content": bytes,  # solo en S1
    # otros campos específicos por stage...
}
```

#### Endpoints Actuales (processing.py):

- `POST /complete_process_batch/`: Procesamiento completo de múltiples archivos **usando cola asíncrona**
- `POST /recognize_and_extract/{docfile_id}`: Reconocimiento y extracción **usando background tasks**
- `POST /extract/{docfile_id}`: Solo extracción y validación **usando background tasks**
- `POST /validate_data/{docfile_id}`: Solo validación **usando background tasks**

**Sistema de Colas Actual**:

- `/complete_process_batch/` utiliza `task_queue.py` con `enqueue_doc_processing()` para manejar múltiples archivos
- Los documentos encolados cambian su status a **"En cola"** inmediatamente después de ser encolados
- Un worker asíncrono (`doc_worker()`) procesa las tareas de la cola con tracking de memoria avanzado
- Los demás endpoints ejecutan directamente las funciones de `s0_pipelines.py` como background tasks

Todos los endpoints usan `get_current_user()` para autenticación JWT vía cookies.

### Limitaciones del Sistema Actual

- Orquestación rígida con RunnableSequence
- Dificultad para agregar lógica condicional compleja
- Manejo de estado distribuido en múltiples parámetros
- Falta de visibilidad del flujo de ejecución
- Replicación de lógica de enrutamiento

## Objetivo de la Migración

Migrar el sistema de orquestación actual basado en LangChain RunnableSequence/RunnableParallel a **LangGraph** para obtener:

- Estado centralizado y consistente
- Enrutamiento condicional inteligente
- Mejor observabilidad y debugging
- Flexibilidad para agregar nuevos nodos y flujos
- Manejo de errores más robusto
- **Sistema de colas unificado** para todos los endpoints de procesamiento

## Requerimientos Funcionales

### 0. Unificación del Sistema de Colas

**OBJETIVO**: Todos los endpoints que invocan procesamiento de documentos deben utilizar el sistema de colas asíncrono.

#### Comportamiento Actual:

- Solo `/complete_process_batch/` usa `task_queue.py` con `enqueue_doc_processing()`
- Los demás endpoints (`/recognize_and_extract/`, `/extract/`, `/validate_data/`) usan background tasks directos

#### Comportamiento Requerido:

- **Todos los endpoints** deben encolar las tareas en `task_queue.py`
- **Status "En cola"**: Al encolar cualquier tarea, el documento debe cambiar inmediatamente su status a "En cola"
- El worker (`doc_worker()`) debe ser capaz de procesar diferentes tipos de operaciones del graph
- Mantener el tracking de memoria avanzado existente en el worker

### 1. Graph State Design

Crear un estado centralizado que reemplace el actual sistema de `params`:

```python
from typing import TypedDict, Optional, List, Literal
from app.models.users import UserPublic
from app.models.docs import Page
from app.models.docs_balance import BalanceData
from app.models.docs_income import IncomeStatementData
from app.models.docs_company_info import CompanyInfo

class DocumentProcessingState(TypedDict):
    # Datos de entrada obligatorios
    docfile_id: str
    requester: UserPublic  # Reemplaza current_user dict

    # Parámetros de operación
    operation: Literal["validate", "extract", "recognize_extract", "complete_process"]

    # Datos específicos para complete_process
    filename: Optional[str]
    file_content: Optional[bytes]

    # Estado del procesamiento
    pages: Optional[List[Page]]
    total_pages: Optional[int]
    stop: Optional[bool]

    # Datos extraídos (tipos específicos de los modelos)
    balance_data: Optional[BalanceData]
    income_data: Optional[IncomeStatementData]
    company_info: Optional[CompanyInfo]

    # Metadatos
    progress: Optional[float]
    error_message: Optional[str]
```

### 2. Nodos del Graph

Transformar las funciones actuales en nodos de LangGraph:

#### Nodos de Procesamiento:

- **`upload_convert_node`**: Basado en `pipe_upload_convert`
- **`recognize_node`**: Basado en `pipe_recognize`
- **`extract_node`**: Basado en `pipe_extract` (incluye balance, income, company_info)
- **`validate_node`**: Basado en `pipe_validate`

#### Nodos de Control:

- **`start_node`**: Validación inicial y preparación del estado
- **`router_node`**: Enrutamiento basado en `operation`
- **`error_node`**: Manejo centralizado de errores
- **`end_node`**: Finalización y cleanup

### 3. Router Logic (Nuevo archivo `/services/graph_router.py`)

Crear un enrutador que determine la secuencia de ejecución:

```python
def route_operation(state: DocumentProcessingState) -> str:
    """Enruta la ejecución basada en la operación solicitada."""
    operation = state["operation"]

    if operation == "complete_process":
        return "upload_convert_node"
    elif operation == "recognize_extract":
        return "recognize_node"
    elif operation == "extract":
        return "extract_node"
    elif operation == "validate":
        return "validate_node"
    else:
        return "error_node"
```

#### Validaciones del Router:

- **`complete_process`**: Requiere `filename` y `file_content`
- **`recognize_extract`**: Requiere `docfile_id` existente con páginas convertidas
- **`extract`**: Requiere `docfile_id` con páginas reconocidas
- **`validate`**: Requiere `docfile_id` con datos extraídos

### 4. Adaptación de Servicios Existentes

#### Cambios en S1-S4:

- Reemplazar acceso a `params["field"]` por `state["field"]`
- Mantener la lógica de procesamiento existente
- Conservar `malloc_trim()` y `gc.collect()` para manejo de memoria
- Adaptar funciones para trabajar con el estado de LangGraph

#### Servicios de Extracción:

- `s3_extract_balance.py`: Adaptar para leer/escribir del state
- `s3_extract_income.py`: Adaptar para leer/escribir del state
- `S3_extract_company_info.py`: Adaptar para leer/escribir del state

### 5. Integración con Endpoints Existentes

#### Modificaciones en `processing.py`:

- Mantener todos los endpoints actuales
- **Unificar el uso del sistema de colas**: Todos los endpoints deben usar `enqueue_graph_processing()` en lugar de background tasks directos
- Usar `get_current_user()` existente y convertir a `UserPublic`
- Conservar autenticación JWT y rate limiting
- **Status "En cola"**: Cada endpoint debe cambiar el status del documento a "En cola" antes de encolarlo

#### Modificaciones en `task_queue.py`:

- Crear nueva función `enqueue_graph_processing(operation, docfile_id, requester, **kwargs)` para manejar diferentes operaciones del graph
- Modificar `doc_worker()` para invocar el graph con la operación correspondiente en lugar de `complete_process()` directamente
- Mantener el tracking de memoria avanzado existente

#### Ejemplo de integración:

```python
@router.post("/recognize_and_extract/{docfile_id}")
async def recognize_and_extract_task(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    # Convertir User a UserPublic
    requester = UserPublic(**current_user.model_dump())

    # Cambiar status a "En cola" inmediatamente
    await docs_collection.update_one(
        {"_id": ObjectId(docfile_id)},
        {"$set": {"status": "En cola"}}
    )

    # Encolar tarea en el sistema de colas unificado
    await enqueue_graph_processing(
        operation="recognize_extract",
        docfile_id=docfile_id,
        requester=requester
    )

    return {"message": "El documento está siendo procesado en segundo plano."}
```

## Requerimientos Técnicos

### 1. Arquitectura del Graph

```python
# services/document_processing_graph.py
from langgraph import StateGraph
from langgraph.prebuilt import ToolNode

def create_document_processing_graph():
    graph = StateGraph(DocumentProcessingState)

    # Agregar nodos
    graph.add_node("start", start_node)
    graph.add_node("router", router_node)
    graph.add_node("upload_convert", upload_convert_node)
    graph.add_node("recognize", recognize_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("error", error_node)
    graph.add_node("end", end_node)

    # Definir flujo
    graph.add_edge("start", "router")
    graph.add_conditional_edges("router", route_operation)
    # ... más edges

    graph.set_entry_point("start")
    graph.set_finish_point("end")

    return graph.compile()
```

### 2. Manejo de Errores

- Centralizar manejo de errores en `error_node`
- Mantener compatibilidad con `update_status()` existente
- Preservar logging y notificaciones WebSocket

### 3. Observabilidad

- Integrar con LangSmith para tracking
- Mantener `advanced_memory_monitor` decoradores
- Preservar callbacks de timing y progreso

### 4. Compatibilidad

- **No breaking changes** en endpoints existentes
- Mantener estructura de respuestas actual
- Preservar modelos Pydantic existentes
- Conservar integración con MongoDB y S3

### 5. Estándares de Documentación y Comentarios

**OBJETIVO**: El código debe estar bien documentado siguiendo los estándares del codebase actual.

#### Formato de Comentarios Requerido:

Seguir el formato establecido en archivos como `s3_extract.py`:

```python
# ------------------------------------------------------------------------------------
# RUNNABLE 1: DESCRIPCIÓN CLARA DE LA FUNCIÓN DEL RUNNABLE
# ------------------------------------------------------------------------------------
async def function_name(params: dict):
    # Descripción detallada de lo que hace la función
    # Explicación de parámetros importantes
    # Lógica condicional explicada

    docfile_id = params["docfile_id"]
    current_user = params['current_user']

    # Comentarios inline para lógica compleja
    # Explicación de return values
    return params
```

#### Estándares de Documentación:

- **Secciones claramente delimitadas** con líneas de guiones (`# --------`)
- **Títulos descriptivos** que expliquen el propósito de cada runnable/nodo
- **Comentarios inline** para lógica condicional y operaciones complejas
- **Documentación de parámetros** y valores de retorno
- **Explicaciones de flujo de datos** entre nodos
- **Referencias a archivos relacionados** cuando sea relevante

## Entregables

### Archivos Nuevos:

1. `/services/graph_router.py` - Lógica de enrutamiento
2. `/services/document_processing_graph.py` - Definición del graph
3. `/services/graph_state.py` - Definición del estado TypedDict con tipos específicos de modelos

### Archivos Modificados:

1. `s1_upload_convert.py` - Adaptación a state
2. `s2_recognize.py` - Adaptación a state
3. `s3_extract.py` - Adaptación a state
4. `s3_extract_balance.py` - Adaptación a state
5. `s3_extract_income.py` - Adaptación a state
6. `S3_extract_company_info.py` - Adaptación a state
7. `s4_validate.py` - Adaptación a state
8. `processing.py` - Integración con graph y sistema de colas unificado
9. `task_queue.py` - Soporte para diferentes operaciones del graph

### Archivo Deprecado:

- `s0_pipelines.py` - Mantener temporalmente para rollback

## Principios de Diseño

### KISS (Keep It Simple, Stupid)

- Migrar funcionalidad existente sin agregar complejidad innecesaria
- Reutilizar máximo código existente
- Mantener interfaces familiares

### Backward Compatibility

- Cero impacto en usuarios finales
- Mantener contratos de API existentes
- Preservar comportamiento observable

### Performance

- Mantener optimizaciones de memoria existentes
- No agregar overhead significativo
- Conservar paralelización donde existe

## Consideraciones de Implementación

### Modificaciones Específicas a `task_queue.py`

#### Funciones Nuevas Requeridas:

```python
async def enqueue_graph_processing(operation: str, docfile_id: str, requester: UserPublic, **kwargs):
    """
    Encola una tarea de procesamiento del graph con la operación especificada.

    Args:
        operation: Tipo de operación ("validate", "extract", "recognize_extract", "complete_process")
        docfile_id: ID del documento a procesar
        requester: Usuario que solicita el procesamiento
        **kwargs: Parámetros adicionales (filename, file_content para complete_process)
    """
```

#### Modificaciones al Worker:

- `doc_worker()` debe ser capaz de procesar diferentes operaciones del graph
- Mantener el tracking de memoria avanzado existente (`advanced_memory_monitor`)
- Conservar el logging detallado y limpieza de memoria
- Invocar el graph de LangGraph en lugar de `complete_process()` directamente

### Fases de Migración:

1. **Fase 1**: Crear graph básico con operación `validate` y unificar sistema de colas
2. **Fase 2**: Agregar operaciones `extract` y `recognize_extract`
3. **Fase 3**: Implementar `complete_process`
4. **Fase 4**: Testing exhaustivo y rollout gradual

### Testing:

- Mantener comportamiento idéntico al sistema actual
- Validar con documentos reales existentes
- Verificar tiempos de procesamiento similares

### Rollback Plan:

- Mantener `s0_pipelines.py` funcional
- Feature flag para alternar entre sistemas
- Monitoreo de métricas de performance
