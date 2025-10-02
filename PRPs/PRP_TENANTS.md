# Product Requirements Prompt (PRP) - Sistema Multi-Tenant

## Contexto del Sistema Actual

### Arquitectura General de la API

La API de Risco es un sistema de análisis automatizado de estados financieros construido con **FastAPI** y **LangGraph** que procesa documentos PDF de balances contables mediante IA. El sistema procesa documentos a través de un grafo de procesamiento (LangGraph) con 4 etapas principales, utilizando modelos de lenguaje (LLMs) para extracción de datos estructurados.

### Estructura del Codebase Actual

```
risco-backend/
├── app/
│   ├── main.py                          # Aplicación FastAPI principal
│   ├── api/
│   │   └── endpoints/
│   │       ├── processing.py            # Endpoints de procesamiento de documentos
│   │       ├── auth.py                  # Autenticación y login
│   │       ├── crud.py                  # CRUD de documentos
│   │       └── user_management.py       # Gestión de usuarios
│   │
│   ├── core/
│   │   ├── auth.py                      # JWT, get_current_user()
│   │   ├── config.py                    # Configuración (env vars)
│   │   ├── database.py                  # Motor async MongoDB
│   │   ├── s3_client.py                 # Cliente boto3 S3
│   │   ├── email.py                     # Sistema de emails (Brevo)
│   │   └── limiter.py                   # Rate limiting
│   │
│   ├── models/
│   │   ├── users.py                     # User, UserPublic
│   │   ├── docs.py                      # DocFile, Page
│   │   ├── docs_balance.py              # BalanceData, BalanceMainResults
│   │   ├── docs_income.py               # IncomeStatementData, IncomeStatementMainResults
│   │   ├── docs_company_info.py         # CompanyInfo
│   │   ├── docs_validation.py           # Validation
│   │   ├── docs_recognition.py          # RecognizedInfo, RecognizedInfoForLLM
│   │   └── docs_financial_items.py      # DocumentGeneralInformation, SheetItem
│   │
│   ├── services/
│   │   ├── graph_definition.py          # Definición del grafo LangGraph
│   │   ├── graph_state.py               # DocumentProcessingState (TypedDict)
│   │   ├── graph_router.py              # Lógica de enrutamiento condicional
│   │   ├── task_queue.py                # Sistema de colas asíncrono unificado
│   │   └── graph_nodes/
│   │       ├── n0_start_end.py          # Nodos de inicio/fin/error
│   │       ├── n1_upload_convert.py     # Upload PDF a S3 y conversión a imágenes
│   │       ├── n2_recognize.py          # Reconocimiento OCR con LLM (GPT-4o)
│   │       ├── n3_extract.py            # Orquestador de extracciones paralelas
│   │       ├── n3_extract_balance.py    # Extracción ESP con LLM (Gemini/Claude)
│   │       ├── n3_extract_income.py     # Extracción ER con LLM (Gemini)
│   │       ├── n3_extract_company_info.py # Extracción info empresa
│   │       └── n4_validate.py           # Validación de ecuaciones contables
│   │
│   ├── utils/
│   │   ├── prompts.py                   # Prompts para LLMs (CRÍTICO PARA TENANTS)
│   │   ├── status_notifier.py           # Notificaciones WebSocket de progreso
│   │   ├── advanced_memory_tracker.py   # Tracking de memoria
│   │   ├── base64_utils.py              # Codificación de imágenes
│   │   └── llm_clients.py               # Clientes LLM configurados
│   │
│   └── websockets/
│       └── manager.py                   # WebSocket manager para updates en tiempo real
│
└── requirements.txt
```

### Flujo de Procesamiento Actual (LangGraph)

El sistema utiliza **LangGraph** con un grafo de estados (`DocumentProcessingState`) que orquesta el procesamiento de documentos:

#### Estado Centralizado (DocumentProcessingState)

```python
class DocumentProcessingState(TypedDict):
    # Identificación
    docfile_id: str
    requester: UserPublic
    operation: Literal["validate", "extract", "recognize_extract", "complete_process"]

    # Datos de entrada (solo para complete_process)
    filename: Optional[str]
    file_content: Optional[bytes]

    # Estado de procesamiento
    pages: Optional[List[Page]]
    total_pages: Optional[int]
    stop: Optional[bool]

    # Datos extraídos
    balance_data: Optional[BalanceData]
    income_data: Optional[IncomeStatementData]
    company_info: Optional[CompanyInfo]

    # Control
    progress: Optional[float]
    error_message: Optional[str]
    _next_node: Optional[str]  # Para enrutamiento interno
```

#### Tipos de Operaciones Disponibles

1. **`complete_process`**: upload_convert → recognize → extract → validate
2. **`recognize_extract`**: recognize → extract → validate
3. **`extract`**: extract → validate
4. **`validate`**: validate únicamente

#### Nodos del Grafo LangGraph

**Nodo 0: Start/End/Error** (`n0_start_end.py`)

- `start_node`: Inicialización del estado
- `end_node`: Finalización exitosa
- `error_node`: Manejo de errores

**Nodo 1: Upload & Convert** (`n1_upload_convert.py`)

- Sube PDF a S3 en: `s3://{bucket}/{S3_ENVIRONMENT}/documents/{docfile_id}/pdf_file/{filename}`
- Convierte PDF a imágenes PNG (usando `pdf2image`)
- Sube imágenes a S3 en: `s3://{bucket}/{S3_ENVIRONMENT}/documents/{docfile_id}/images/page_XXX.png`
- Crea/actualiza `DocFile` en MongoDB con páginas (`Page[]`)
- Notifica progreso vía WebSocket

**Nodo 2: Recognize** (`n2_recognize.py`)

- Obtiene páginas del documento desde MongoDB
- Procesa cada página con **GPT-4o** usando el prompt `prompt_recognize_pages`
- Identifica para cada página:
  - `is_balance_sheet`: ¿Es Estado de Situación Patrimonial (ESP)?
  - `is_income_statement_sheet`: ¿Es Estado de Resultados (ER)?
  - `is_appendix`: ¿Es anexo o nota explicativa?
  - `original_orientation_degrees`: Grados de rotación necesarios
  - `has_company_cuit`, `has_company_name`, etc.
- Rota imágenes si es necesario y reemplaza en S3
- Actualiza campo `recognized_info` de cada `Page` en MongoDB
- Procesamiento paralelo con límite de concurrencia (15 páginas simultáneas)
- Rate limiting: 2.5 requests/segundo

**Nodo 3: Extract** (`n3_extract.py`)

- Verifica que existan páginas relevantes (ESP o ER)
- Ejecuta en **paralelo**:
  - `extract_balance()`: Extrae datos del ESP
  - `extract_income()`: Extrae datos del ER
  - `extract_company_info()`: Extrae CUIT, nombre, dirección, actividad
- Consolida resultados en el estado
- Actualiza MongoDB con datos extraídos

**Nodo 3a: Extract Balance** (`n3_extract_balance.py`)

- Filtra páginas con `is_balance_sheet = True`
- Usa **Gemini 2.5 Flash** (o Claude 3.7 Sonnet) con `prompt_extract_balance_data`
- Extrae datos estructurados según modelo `BalanceData`:
  - `informacion_general`: empresa, periodo_actual, periodo_anterior
  - `resultados_principales` (`BalanceMainResults`):
    - `disponibilidades_caja_banco_o_equivalentes_actual/anterior`
    - `bienes_de_cambio_o_equivalentes_actual/anterior`
    - `activo_corriente_actual/anterior`
    - `activo_no_corriente_actual/anterior`
    - `activo_total_actual/anterior`
    - `pasivo_corriente_actual/anterior`
    - `pasivo_no_corriente_actual/anterior`
    - `pasivo_total_actual/anterior`
    - `patrimonio_neto_actual/anterior`
  - `detalles_activo`: Lista de `SheetItem[]` con todos los conceptos
  - `detalles_pasivo`: Lista de `SheetItem[]`
  - `detalles_patrimonio_neto`: Lista de `SheetItem[]`
- Usa `.with_structured_output(BalanceData)` para garantizar formato
- Actualiza `balance_data` y `balance_date` en MongoDB

**Nodo 3b: Extract Income** (`n3_extract_income.py`)

- Filtra páginas con `is_income_statement_sheet = True`
- Usa **Gemini 2.5 Flash** con `prompt_extract_income_statement_data`
- Extrae datos estructurados según modelo `IncomeStatementData`:
  - `informacion_general`: empresa, periodo_actual, periodo_anterior
  - `resultados_principales` (`IncomeStatementMainResults`):
    - `ingresos_operativos_empresa_actual/anterior`
    - `resultados_antes_de_impuestos_actual/anterior`
    - `resultados_del_ejercicio_actual/anterior`
  - `detalles_estado_resultados`: Lista de `SheetItem[]` con todos los conceptos
- Actualiza `income_statement_data` en MongoDB

**Nodo 3c: Extract Company Info** (`n3_extract_company_info.py`)

- Filtra páginas con `has_company_*` en True
- Usa LLM con `prompt_extract_company_info`
- Extrae: `company_cuit`, `company_name`, `company_address`, `company_activity`
- Actualiza `company_info` en MongoDB

**Nodo 4: Validate** (`n4_validate.py`)

- Valida ecuaciones contables fundamentales:
  1. A = P + PN (períodos actual y anterior)
  2. A = A corriente + A no corriente
  3. P = P corriente + P no corriente
  4. PN actual = PN anterior + Resultado del ejercicio
  5. Disponibilidades ≤ Activo corriente
  6. Bienes de cambio ≤ Activo corriente
  7. Resultado antes de impuestos ≥ Resultado del ejercicio
  8. Ingresos operativos ≥ Resultado antes de impuestos
  9. ΔA = ΔP + ΔPN
- Tolerancia de error: 0.0005 (0.05%)
- Genera objeto `Validation` con status y mensajes de error
- Actualiza campo `validation` en MongoDB
- Status final: "Analizado" o "Sin datos"

#### Sistema de Enrutamiento (graph_router.py)

El router determina el siguiente nodo basado en:

- La operación solicitada (`operation`)
- Validaciones de estado (docfile existe, tiene páginas, tiene reconocimiento, etc.)

**Funciones de enrutamiento:**

- `route_operation()`: Router principal
- `_route_complete_process()`: Valida filename/file_content → upload_convert_node
- `_route_recognize_extract()`: Valida páginas convertidas → recognize_node
- `_route_extract()`: Valida páginas reconocidas → extract_node
- `_route_validate()`: Valida datos extraídos → validate_node

#### Sistema de Colas Unificado (task_queue.py)

- Cola asíncrona única: `graph_queue = asyncio.Queue()`
- Función de encolado: `enqueue_graph_processing(operation, docfile_id, requester, filename?, file_content?)`
- Worker asíncrono: `graph_worker()` procesa tareas con tracking de memoria
- Invoca: `await process_document(initial_state)` del grafo LangGraph
- Logging detallado de progreso y tiempos

### Endpoints de Procesamiento (processing.py)

#### POST `/complete_process_batch/`

- Límite: 3 requests/minuto, máximo 5 archivos por batch
- Para cada archivo:
  1. Crea `DocFile` con status "En cola"
  2. Encola con `enqueue_graph_processing(operation="complete_process", ...)`
- Retorna: `{"message": "...", "docfile_ids": [...]}`

#### POST `/recognize_and_extract/{docfile_id}`

- Límite: 5 requests/minuto
- Cambia status a "En cola"
- Encola con `operation="recognize_extract"`

#### POST `/extract/{docfile_id}`

- Límite: 5 requests/minuto
- Cambia status a "En cola"
- Encola con `operation="extract"`

#### POST `/validate_data/{docfile_id}`

- Límite: 10 requests/minuto
- Cambia status a "En cola"
- Encola con `operation="validate"`

Todos usan:

- `get_current_user()` para autenticación JWT
- Conversión `User → UserPublic` para el estado del grafo
- Rate limiting con `@limiter.limit()`
- WebSocket para notificaciones de progreso en tiempo real

### Modelos de Datos Clave

#### DocFile (MongoDB collection: "documents")

```python
{
  "_id": ObjectId,
  "name": str,
  "status": str,  # "En cola", "Cargando", "Cargado", "Reconociendo", "Analizando", "Validando", "Analizado", "Error"
  "upload_path": str,  # URL S3 del PDF
  "progress": float,  # 0.0 - 1.0
  "pages": [Page],
  "page_count": int,
  "upload_date": datetime,
  "uploaded_by": str,
  "balance_date": datetime,
  "balance_date_previous": datetime,
  "income_statement_data": IncomeStatementData,
  "balance_data": BalanceData,
  "validation": Validation,
  "company_info": CompanyInfo,
  "processing_time": ProcessingTime,
  "export_data": ExportData
}
```

#### User (MongoDB collection: "users")

```python
{
  "_id": ObjectId,
  "username": str,
  "email": EmailStr,
  "first_name": str,
  "last_name": str,
  "password_hash": str,
  "role": str,  # "user" | "admin"
  "status": str,  # "pending" | "active" | "inactive"
  "created_at": datetime,
  "approved_at": datetime,
  "company_domain": str,  # Extraído del email (ej: "caucion.com.ar")
  "email_verified": bool
}
```

### Configuración Actual (config.py)

**Variables de entorno relevantes:**

- `MONGO_URI`, `MONGO_DB`: Conexión MongoDB
- `S3_BUCKET_NAME`: Bucket S3 (ej: "integrity-caucion-bucket")
- `S3_ENVIRONMENT`: Prefijo de rutas S3 (ej: "test" o "prod")
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`: API keys LLMs
- `ALLOWED_EMAIL_DOMAIN`: Dominio permitido para registro (ej: "@caucion.com.ar")

### Sistema de Prompts Actual (utils/prompts.py)

**Prompts actualmente definidos:**

1. `prompt_recognize_pages`: Para reconocimiento de páginas (Nodo 2)
2. `prompt_extract_balance_data`: Para extracción de ESP (Nodo 3a)
3. `prompt_extract_income_statement_data`: Para extracción de ER (Nodo 3b)
4. `prompt_extract_company_info`: Para extracción de info empresa (Nodo 3c)

**Características de los prompts:**

- Son strings largos (50-100 líneas) con instrucciones detalladas
- Incluyen ejemplos de JSON esperado
- Definen campos específicos de `resultados_principales`
- Contienen reglas de negocio (ej: "valores en miles", "actividad económica", etc.)
- Son específicos del dominio contable argentino

---

## Objetivo: Sistema Multi-Tenant

Implementar un sistema **multi-tenant simple y mantenible (KISS)** que permita a diferentes organizaciones (tenants) tener configuraciones personalizadas de:

1. **Prompts de extracción** (Balance e Income)
2. **Campos de resultados principales** (modelos Pydantic dinámicos)
3. **Almacenamiento S3** (carpetas separadas por tenant)
4. **Aislamiento de datos en MongoDB** (todos los documentos marcados con `tenant_id`)

**Alcance inicial:** 8-20 tenants máximo

**NO se personalizará:**

- Modelos IA a utilizar (común para todos)
- Validaciones contables (comunes para todos)
- Tolerancias de error (comunes para todos)
- Límites operacionales (comunes para todos)
- Formatos de exportación (comunes para todos)
- Reglas de reconocimiento OCR (comunes para todos)

---

## Requerimientos Funcionales

### 1. Modelo de Datos Multi-Tenant

#### 1.1. Colección `tenants` en MongoDB

**Crear nueva colección:** `db["tenants"]`

**Estructura del documento:**

```python
{
  "_id": ObjectId,
  "tenant_id": str,  # Identificador único, slug-friendly (ej: "default", "caucion_sa", "empresa_xyz")
  "tenant_name": str,  # Nombre legible (ej: "Default", "Caución SA", "Empresa XYZ")
  "status": str,  # "active" | "inactive"

  # Configuración de campos de resultados principales
  "balance_main_results_fields": [str],  # Lista de nombres de campos para BalanceMainResults
  "income_main_results_fields": [str],   # Lista de nombres de campos para IncomeStatementMainResults

  # Metadatos
  "created_at": datetime,
  "updated_at": datetime,
  "created_by": str  # username del admin que lo creó
}
```

**Ejemplo de documento "default":**

```python
{
  "tenant_id": "default",
  "tenant_name": "Default",
  "status": "active",
  "balance_main_results_fields": [
    "disponibilidades_caja_banco_o_equivalentes",
    "bienes_de_cambio_o_equivalentes",
    "activo_corriente",
    "activo_no_corriente",
    "activo_total",
    "pasivo_corriente",
    "pasivo_no_corriente",
    "pasivo_total",
    "patrimonio_neto"
  ],
  "income_main_results_fields": [
    "ingresos_operativos_empresa",
    "resultados_antes_de_impuestos",
    "resultados_del_ejercicio"
  ],
  "created_at": "2025-09-30T00:00:00Z",
  "updated_at": "2025-09-30T00:00:00Z",
  "created_by": "system"
}
```

**Índices requeridos:**

```python
# Índice único en tenant_id
db.tenants.create_index("tenant_id", unique=True)
```

#### 1.2. Modificación de Colección `users`

**Agregar campo:**

```python
{
  # ... campos existentes ...
  "tenant_id": str  # Referencia al tenant (ej: "default", "caucion_sa")
}
```

**Índice requerido:**

```python
# Índice para búsquedas por tenant
db.users.create_index("tenant_id")
```

**Estrategia de asignación de tenant:**

- Al crear un usuario, derivar `tenant_id` desde `company_domain`
- Mapeo configurable en MongoDB (colección opcional `domain_tenant_mapping`) o en código
- Fallback: `tenant_id = "default"` si no hay mapeo

**Ejemplo de mapeo (opcional, puede ser en código):**

```python
# Lógica en app/services/tenant_mapping.py
DOMAIN_TO_TENANT = {
    "caucion.com.ar": "caucion_sa",
    "empresa1.com": "empresa1",
    # ... más mapeos ...
}

def get_tenant_id_from_email(email: str) -> str:
    domain = email.split("@")[1] if "@" in email else ""
    return DOMAIN_TO_TENANT.get(domain, "default")
```

#### 1.3. Modificación de Colección `documents`

**Agregar campo:**

```python
{
  # ... campos existentes ...
  "tenant_id": str  # Tenant propietario del documento
}
```

**Índices requeridos:**

```python
# Índice compuesto para búsquedas por tenant
db.documents.create_index([("tenant_id", 1), ("upload_date", -1)])
```

**Origen del tenant_id:**

- Se obtiene del `requester.tenant_id` al crear el documento
- Se persiste en todos los documentos para aislamiento de datos

### 2. Sistema de Prompts Tenant-Specific

#### 2.1. Estructura de Carpetas

**Crear nueva estructura:**

```
app/
  tenants/
    __init__.py
    base/
      __init__.py
      prompts.py          # Prompts genéricos (reutilizables)

    default/
      __init__.py
      prompts.py          # Prompts del tenant "default" (configuración actual)

    # Futuros tenants se agregarán aquí:
    # caucion_sa/
    #   __init__.py
    #   prompts.py
```

#### 2.2. Contenido de Prompts

**`app/tenants/base/prompts.py`:**

```python
# Prompts genéricos base que pueden ser reutilizados
# Por ahora vacío, pero se puede usar para compartir fragmentos comunes
```

**`app/tenants/default/prompts.py`:**

```python
"""
Prompts del tenant DEFAULT.
Estos son los prompts actuales del sistema.
"""

PROMPT_EXTRACT_BALANCE = """
[Contenido actual de prompt_extract_balance_data de utils/prompts.py]
"""

PROMPT_EXTRACT_INCOME = """
[Contenido actual de prompt_extract_income_statement_data de utils/prompts.py]
"""
```

**Migración:**

- Mover contenido de `utils/prompts.py` (prompts de extracción) a `tenants/default/prompts.py`
- Mantener `prompt_recognize_pages` y `prompt_extract_company_info` en `utils/prompts.py` (comunes a todos los tenants)
- Actualizar imports en los nodos de extracción

#### 2.3. Convención de Nombres

**Todos los archivos `prompts.py` de tenants deben exportar:**

- `PROMPT_EXTRACT_BALANCE`: Prompt para extracción de ESP
- `PROMPT_EXTRACT_INCOME`: Prompt para extracción de ER

**Nombres consistentes para facilitar carga dinámica.**

### 3. Sistema de Configuración de Tenant (TenantConfig)

#### 3.1. Módulo TenantConfig

**Crear archivo:** `app/services/tenant_config.py`

**Nota:** Se ubica en `services/` porque es lógica de negocio/dominio (cómo los tenants configuran su procesamiento).

**Contenido:**

```python
"""
Sistema de configuración multi-tenant.
Carga y cachea configuraciones de tenants desde MongoDB y archivos Python.
"""

import importlib
from typing import Optional, List, Type
from pydantic import BaseModel, create_model
from app.core.database import db
import logging

logger = logging.getLogger(__name__)

# Cache de configuraciones cargadas
_tenant_configs: dict[str, "TenantConfig"] = {}


class TenantConfig:
    """
    Configuración consolidada de un tenant.

    Carga configuración desde:
    - MongoDB (colección 'tenants'): Campos dinámicos
    - Archivos Python (app/tenants/{tenant_id}/): Prompts
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._db_config: Optional[dict] = None
        self._prompts_module = None

        # Cargar configuración
        self._load_config()

    def _load_config(self):
        """Carga configuración desde MongoDB y archivos."""
        # 1. Cargar desde MongoDB
        self._db_config = db.tenants.find_one({"tenant_id": self.tenant_id})

        if not self._db_config:
            logger.warning(f"Tenant '{self.tenant_id}' no encontrado en BD, usando 'default'")
            self._db_config = db.tenants.find_one({"tenant_id": "default"})
            if not self._db_config:
                raise ValueError("Tenant 'default' no existe en la base de datos")

        # 2. Cargar prompts desde archivos Python
        try:
            self._prompts_module = importlib.import_module(f"app.tenants.{self.tenant_id}.prompts")
            logger.info(f"Prompts cargados para tenant '{self.tenant_id}'")
        except ImportError:
            logger.warning(f"No se encontraron prompts para tenant '{self.tenant_id}', usando 'default'")
            self._prompts_module = importlib.import_module("app.tenants.default.prompts")

    @property
    def tenant_name(self) -> str:
        """Nombre legible del tenant."""
        return self._db_config.get("tenant_name", "Unknown")

    @property
    def status(self) -> str:
        """Status del tenant."""
        return self._db_config.get("status", "inactive")

    @property
    def balance_fields(self) -> List[str]:
        """Campos de resultados principales del Balance."""
        return self._db_config.get("balance_main_results_fields", [])

    @property
    def income_fields(self) -> List[str]:
        """Campos de resultados principales del Income."""
        return self._db_config.get("income_main_results_fields", [])

    @property
    def prompt_extract_balance(self) -> str:
        """Prompt para extracción de Balance."""
        return getattr(self._prompts_module, "PROMPT_EXTRACT_BALANCE", "")

    @property
    def prompt_extract_income(self) -> str:
        """Prompt para extracción de Income."""
        return getattr(self._prompts_module, "PROMPT_EXTRACT_INCOME", "")

    def create_balance_model(self) -> Type[BaseModel]:
        """
        Crea dinámicamente el modelo Pydantic BalanceMainResults
        basado en los campos configurados del tenant.
        """
        fields = {}
        for field_name in self.balance_fields:
            fields[f"{field_name}_actual"] = (float, ...)
            fields[f"{field_name}_anterior"] = (float, ...)

        return create_model("BalanceMainResults", **fields)

    def create_income_model(self) -> Type[BaseModel]:
        """
        Crea dinámicamente el modelo Pydantic IncomeStatementMainResults
        basado en los campos configurados del tenant.
        """
        fields = {}
        for field_name in self.income_fields:
            fields[f"{field_name}_actual"] = (float, ...)
            fields[f"{field_name}_anterior"] = (float, ...)

        return create_model("IncomeStatementMainResults", **fields)

    def get_s3_prefix(self, docfile_id: str) -> str:
        """
        Retorna el prefijo S3 para documentos de este tenant.

        Formato: {S3_ENVIRONMENT}/{tenant_id}/documents/{docfile_id}/
        """
        from app.core.config import S3_ENVIRONMENT
        return f"{S3_ENVIRONMENT}/{self.tenant_id}/documents/{docfile_id}"


def get_tenant_config(tenant_id: str) -> TenantConfig:
    """
    Factory con cache para configuraciones de tenant.

    Args:
        tenant_id: Identificador del tenant

    Returns:
        TenantConfig: Configuración del tenant
    """
    if tenant_id not in _tenant_configs:
        _tenant_configs[tenant_id] = TenantConfig(tenant_id)

    return _tenant_configs[tenant_id]


def clear_tenant_cache(tenant_id: Optional[str] = None):
    """
    Limpia el cache de configuraciones de tenant.

    Args:
        tenant_id: Si se especifica, limpia solo ese tenant. Si es None, limpia todo.
    """
    global _tenant_configs

    if tenant_id:
        _tenant_configs.pop(tenant_id, None)
        logger.info(f"Cache limpiado para tenant '{tenant_id}'")
    else:
        _tenant_configs.clear()
        logger.info("Cache de tenants completamente limpiado")
```

**Características:**

- Carga desde MongoDB (campos dinámicos)
- Carga desde archivos Python (prompts)
- Cache en memoria para performance
- Fallback a "default" si tenant no existe
- Factory pattern con `get_tenant_config()`
- Generación dinámica de modelos Pydantic
- Generación de rutas S3 por tenant

### 4. Modificación del Estado del Grafo

#### 4.1. DocumentProcessingState

**Modificar:** `app/services/graph_state.py`

**Agregar campos:**

```python
class DocumentProcessingState(TypedDict):
    # ... campos existentes ...

    # NUEVO: Identificador de tenant
    tenant_id: str
```

**Explicación:**

- `tenant_id`: Se inyecta al inicio del procesamiento desde `requester.tenant_id`

### 5. Modificación de Nodos de Extracción

#### 5.1. Nodo Start (n0_start_end.py)

**Modificar `start_node()`:**

```python
async def start_node(state: DocumentProcessingState) -> DocumentProcessingState:
    """Inicializa el estado del grafo con información del tenant."""
    requester = state["requester"]

    # Obtener tenant_id del usuario
    # Asumimos que User ya tiene tenant_id después de las modificaciones
    tenant_id = getattr(requester, "tenant_id", "default")

    # Actualizar estado con tenant_id
    updated_state = state.copy()
    updated_state["tenant_id"] = tenant_id

    logger.info(f"[START] Procesamiento iniciado para tenant '{tenant_id}'")

    return updated_state
```

#### 5.2. Nodo Upload Convert (n1_upload_convert.py)

**Modificar rutas S3 para incluir tenant_id:**

**En `upload_file()`:**

```python
async def upload_file(state: DocumentProcessingState) -> DocumentProcessingState:
    # ... código existente ...

    tenant_id = state.get("tenant_id", "default")
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)

    # CAMBIO: Usar prefijo S3 del tenant
    s3_key = f"{tenant_config.get_s3_prefix(docfile_id)}/pdf_file/{filename}"

    # ... resto del código ...
```

**En `convert_pdf_to_images()`:**

```python
async def convert_pdf_to_images(state: DocumentProcessingState) -> DocumentProcessingState:
    # ... código existente ...

    tenant_id = state.get("tenant_id", "default")
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)

    # CAMBIO: Usar prefijo S3 del tenant para imágenes
    image_key = f"{tenant_config.get_s3_prefix(docfile_id)}/images/page_{str(current_page_number).zfill(3)}.png"

    # ... resto del código ...
```

**Además, guardar tenant_id en DocFile:**

```python
async def upload_file(state: DocumentProcessingState) -> DocumentProcessingState:
    # ... código existente ...

    tenant_id = state.get("tenant_id", "default")

    if not docfile_id:
        docfile = DocFile(
            name=filename,
            uploaded_by=uploaded_by,
            status="En cola",
            progress=0,
            tenant_id=tenant_id  # NUEVO
        )
        # ... resto del código ...
```

#### 5.3. Nodo Extract Balance (n3_extract_balance.py)

**Modificar `extract_balance_llm()`:**

```python
async def extract_balance_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    """Extrae datos del balance usando IA desde las páginas identificadas como ESP."""
    if state.get("stop"):
        return state

    balance_pages = state['balance_pages']
    tenant_id = state.get("tenant_id", "default")

    # Cargar configuración del tenant
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)

    # Usar prompt específico del tenant
    indications = tenant_config.prompt_extract_balance

    # Crear modelo dinámico basado en campos del tenant
    from app.models.docs_financial_items import DocumentGeneralInformation, SheetItem
    from pydantic import create_model
    from typing import List

    BalanceMainResults = tenant_config.create_balance_model()

    BalanceData = create_model(
        "BalanceData",
        informacion_general=(DocumentGeneralInformation, ...),
        resultados_principales=(BalanceMainResults, ...),
        detalles_activo=(List[SheetItem], ...),
        detalles_pasivo=(List[SheetItem], ...),
        detalles_patrimonio_neto=(List[SheetItem], ...)
    )

    # Crear modelo LLM con structured output dinámico
    from langchain_google_genai import ChatGoogleGenerativeAI
    model_text = "gemini-2.5-flash"
    model = ChatGoogleGenerativeAI(
        model=model_text,
        max_tokens=13000,
        max_retries=1
    ).with_structured_output(BalanceData)

    # ... resto del código de extracción (igual que antes) ...

    # Creo el esqueleto de los mensajes a enviar a la IA
    messages = [("system", "{indications}"),]
    for page in balance_pages:
        # ... código de construcción de mensajes ...

    messages.append(("ai", "Aquí está el JSON solicitado:"))
    template = ChatPromptTemplate(messages)
    prompt = template.invoke({"indications": indications})
    extracted_balance = await model.ainvoke(prompt)

    # ... resto del código (limpieza de memoria, etc.) ...
```

**Nota:** El modelo dinámico se crea en tiempo de ejecución basado en los campos configurados del tenant.

#### 5.4. Nodo Extract Income (n3_extract_income.py)

**Modificar `extract_income_llm()` de manera análoga:**

```python
async def extract_income_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    """Extrae datos del estado de resultados usando IA desde las páginas identificadas como ER."""
    if state.get("stop"):
        return state

    income_pages = state['income_pages']
    tenant_id = state.get("tenant_id", "default")

    # Cargar configuración del tenant
    from app.services.tenant_config import get_tenant_config
    tenant_config = get_tenant_config(tenant_id)

    # Usar prompt específico del tenant
    indications = tenant_config.prompt_extract_income

    # Crear modelo dinámico basado en campos del tenant
    from app.models.docs_financial_items import DocumentGeneralInformation, SheetItem
    from pydantic import create_model
    from typing import List

    IncomeStatementMainResults = tenant_config.create_income_model()

    IncomeStatementData = create_model(
        "IncomeStatementData",
        informacion_general=(DocumentGeneralInformation, ...),
        resultados_principales=(IncomeStatementMainResults, ...),
        detalles_estado_resultados=(List[SheetItem], ...)
    )

    # Crear modelo LLM con structured output dinámico
    from langchain_google_genai import ChatGoogleGenerativeAI
    model_text = "gemini-2.5-flash"
    model = ChatGoogleGenerativeAI(
        model=model_text,
        max_tokens=13000,
        max_retries=1
    ).with_structured_output(IncomeStatementData)

    # ... resto del código de extracción (igual que antes) ...
```

### 6. Modificación de Modelos de Usuario

#### 6.1. Modelo User (models/users.py)

**Agregar campo:**

```python
class User(BaseModel):
    # ... campos existentes ...
    tenant_id: str = "default"  # NUEVO: Identificador del tenant
```

**Agregar campo en UserPublic:**

```python
class UserPublic(BaseModel):
    # ... campos existentes ...
    tenant_id: str = "default"  # NUEVO: Identificador del tenant
```

#### 6.2. Lógica de Asignación de Tenant

**Crear módulo:** `app/services/tenant_mapping.py`

```python
"""
Mapeo de dominios de email a tenant_id.
"""

# Mapeo estático de dominios a tenants
DOMAIN_TO_TENANT = {
    "caucion.com.ar": "default",  # Por ahora todos van a default
    # Futuros mapeos:
    # "empresa1.com": "empresa1",
    # "empresa2.com": "empresa2",
}

def get_tenant_id_from_email(email: str) -> str:
    """
    Determina el tenant_id basado en el dominio del email.

    Args:
        email: Email del usuario

    Returns:
        str: tenant_id correspondiente (default si no hay mapeo)
    """
    if "@" not in email:
        return "default"

    domain = email.split("@")[1].lower()
    return DOMAIN_TO_TENANT.get(domain, "default")
```

**Modificar endpoint de registro (`api/endpoints/user_registration.py` o similar):**

```python
from app.services.tenant_mapping import get_tenant_id_from_email

# En la creación del usuario
tenant_id = get_tenant_id_from_email(user_data.email)

new_user = User(
    username=user_data.username,
    email=user_data.email,
    # ... otros campos ...
    tenant_id=tenant_id  # NUEVO
)
```

### 7. Modificación de Modelo DocFile

#### 7.1. Modelo DocFile (models/docs.py)

**Agregar campo:**

```python
class DocFile(BaseModel):
    # ... campos existentes ...
    tenant_id: str = "default"  # NUEVO: Tenant propietario del documento
```

### 8. Aislamiento de Datos en MongoDB

#### 8.1. Filtros por Tenant en CRUD

**Modificar endpoints de CRUD (`api/endpoints/crud.py`):**

**En GET de documentos:**

```python
@router.get("/documents/", response_model=List[DocFilePublic])
async def get_documents(current_user: User = Depends(get_current_user)):
    tenant_id = current_user.tenant_id

    # Filtrar solo documentos del tenant del usuario
    documents = await docs_collection.find(
        {"tenant_id": tenant_id}
    ).sort("upload_date", -1).to_list(length=None)

    # ... resto del código ...
```

**En GET de documento individual:**

```python
@router.get("/documents/{docfile_id}", response_model=DocFilePublic)
async def get_document(
    docfile_id: str,
    current_user: User = Depends(get_current_user)
):
    tenant_id = current_user.tenant_id

    # Verificar que el documento pertenece al tenant del usuario
    document = await docs_collection.find_one({
        "_id": ObjectId(docfile_id),
        "tenant_id": tenant_id
    })

    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # ... resto del código ...
```

**En DELETE:**

```python
@router.delete("/documents/{docfile_id}")
async def delete_document(
    docfile_id: str,
    current_user: User = Depends(get_current_user)
):
    tenant_id = current_user.tenant_id

    # Solo permitir borrar documentos del propio tenant
    result = await docs_collection.delete_one({
        "_id": ObjectId(docfile_id),
        "tenant_id": tenant_id
    })

    # ... resto del código ...
```

### 9. Inicialización del Sistema

#### 9.1. Script de Inicialización

**Crear script:** `scripts/init_tenants.py`

```python
"""
Script de inicialización de tenants.
Crea el tenant 'default' con la configuración actual del sistema.
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def init_default_tenant():
    """Crea el tenant 'default' en la base de datos."""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    # Verificar si ya existe
    existing = await db.tenants.find_one({"tenant_id": "default"})
    if existing:
        print("Tenant 'default' ya existe")
        return

    # Crear tenant default
    default_tenant = {
        "tenant_id": "default",
        "tenant_name": "Default",
        "status": "active",
        "balance_main_results_fields": [
            "disponibilidades_caja_banco_o_equivalentes",
            "bienes_de_cambio_o_equivalentes",
            "activo_corriente",
            "activo_no_corriente",
            "activo_total",
            "pasivo_corriente",
            "pasivo_no_corriente",
            "pasivo_total",
            "patrimonio_neto"
        ],
        "income_main_results_fields": [
            "ingresos_operativos_empresa",
            "resultados_antes_de_impuestos",
            "resultados_del_ejercicio"
        ],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "created_by": "system"
    }

    await db.tenants.insert_one(default_tenant)
    print("Tenant 'default' creado exitosamente")

    # Crear índices
    await db.tenants.create_index("tenant_id", unique=True)
    await db.users.create_index("tenant_id")
    await db.documents.create_index([("tenant_id", 1), ("upload_date", -1)])
    print("Índices creados exitosamente")

    client.close()

if __name__ == "__main__":
    asyncio.run(init_default_tenant())
```

**Ejecutar:**

```bash
# Activar el entorno virtual del proyecto
source .venv/bin/activate

# Ejecutar el script
python scripts/init_tenants.py
```

#### 9.2. Migración de Usuarios Existentes

**Crear script:** `scripts/migrate_users_tenant.py`

**IMPORTANTE:** Este script debe ejecutarse UNA SOLA VEZ durante la implementación inicial del sistema multi-tenant. Después de su ejecución exitosa, el archivo debe ser eliminado o archivado para evitar ejecuciones accidentales.

```python
"""
Migra usuarios existentes al tenant 'default'.

ADVERTENCIA: Este script debe ejecutarse UNA SOLA VEZ.
Después de la migración, eliminar este archivo.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def migrate_users():
    """Asigna tenant_id='default' a todos los usuarios existentes."""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    # Actualizar usuarios sin tenant_id
    result = await db.users.update_many(
        {"tenant_id": {"$exists": False}},
        {"$set": {"tenant_id": "default"}}
    )

    print(f"Usuarios actualizados: {result.modified_count}")

    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_users())
```

**Ejecutar desde la terminal (una sola vez):**

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar la migración
python scripts/migrate_users_tenant.py

# Después de verificar que la migración fue exitosa, eliminar el script
rm scripts/migrate_users_tenant.py
```

#### 9.3. Migración de Documentos Existentes

**Crear script:** `scripts/migrate_documents_tenant.py`

**IMPORTANTE:** Este script debe ejecutarse UNA SOLA VEZ durante la implementación inicial del sistema multi-tenant. Después de su ejecución exitosa, el archivo debe ser eliminado o archivado para evitar ejecuciones accidentales.

```python
"""
Migra documentos existentes al tenant 'default'.

ADVERTENCIA: Este script debe ejecutarse UNA SOLA VEZ.
Después de la migración, eliminar este archivo.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def migrate_documents():
    """Asigna tenant_id='default' a todos los documentos existentes."""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    # Actualizar documentos sin tenant_id
    result = await db.documents.update_many(
        {"tenant_id": {"$exists": False}},
        {"$set": {"tenant_id": "default"}}
    )

    print(f"Documentos actualizados: {result.modified_count}")

    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_documents())
```

**Ejecutar desde la terminal (una sola vez):**

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar la migración
python scripts/migrate_documents_tenant.py

# Después de verificar que la migración fue exitosa, eliminar el script
rm scripts/migrate_documents_tenant.py
```

### 10. Documentación: Cómo Agregar un Nuevo Tenant

Esta sección describe el proceso completo para agregar un nuevo tenant al sistema.

#### 10.1. Requisitos Previos

- Acceso a MongoDB para insertar configuración
- Acceso al repositorio del código
- Entorno virtual `.venv` activado
- Conocer el dominio de email de la organización (ej: `empresa.com`)

#### 10.2. Paso 1: Crear Carpeta de Prompts del Tenant

**Ubicación:** `app/tenants/{tenant_id}/`

**Ejemplo:** Para una empresa llamada "Empresa XYZ" con `tenant_id = "empresa_xyz"`

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Crear la carpeta del tenant
mkdir -p app/tenants/empresa_xyz

# Crear archivo __init__.py
touch app/tenants/empresa_xyz/__init__.py
```

#### 10.3. Paso 2: Crear Archivo de Prompts

**Archivo:** `app/tenants/empresa_xyz/prompts.py`

**IMPORTANTE:** El archivo DEBE exportar exactamente estas dos constantes:

- `PROMPT_EXTRACT_BALANCE`: Prompt para extracción de Estado de Situación Patrimonial (ESP/Balance)
- `PROMPT_EXTRACT_INCOME`: Prompt para extracción de Estado de Resultados (ER/Income Statement)

**Ejemplo:**

```python
"""
Prompts personalizados para Empresa XYZ.
"""

PROMPT_EXTRACT_BALANCE = """
Eres un experto en análisis de estados financieros.

[Instrucciones específicas para Empresa XYZ...]

IMPORTANTE:
- Los valores deben estar expresados en miles de pesos
- Incluir resultados_principales con los siguientes campos:
  * disponibilidades_caja_banco_o_equivalentes
  * activo_corriente
  * activo_no_corriente
  * activo_total
  * pasivo_corriente
  * pasivo_no_corriente
  * pasivo_total
  * patrimonio_neto

[Más instrucciones específicas...]
"""

PROMPT_EXTRACT_INCOME = """
Eres un experto en análisis de estados de resultados.

[Instrucciones específicas para Empresa XYZ...]

IMPORTANTE:
- Incluir resultados_principales con los siguientes campos:
  * ingresos_operativos_empresa
  * resultados_antes_de_impuestos
  * resultados_del_ejercicio

[Más instrucciones específicas...]
"""
```

**Nota:** Los campos mencionados en los prompts deben coincidir con los campos configurados en MongoDB (Paso 4).

#### 10.4. Paso 3: Agregar Mapeo de Dominio (Opcional)

Si la organización tiene un dominio de email específico, agregar el mapeo en:

**Archivo:** `app/services/tenant_mapping.py`

```python
DOMAIN_TO_TENANT = {
    "caucion.com.ar": "default",
    "empresa.com": "empresa_xyz",  # AGREGAR ESTA LÍNEA
    # ... más mapeos ...
}
```

**Nota:** Si no se agrega el mapeo, los usuarios de ese dominio se asignarán automáticamente al tenant "default".

#### 10.5. Paso 4: Insertar Configuración en MongoDB

**Crear script temporal:** `scripts/add_tenant_empresa_xyz.py`

```python
"""
Script para agregar tenant 'empresa_xyz'.
EJECUTAR UNA SOLA VEZ y luego eliminar.
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def add_tenant():
    """Crea el tenant 'empresa_xyz' en la base de datos."""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    # Verificar si ya existe
    existing = await db.tenants.find_one({"tenant_id": "empresa_xyz"})
    if existing:
        print("Tenant 'empresa_xyz' ya existe")
        client.close()
        return

    # Crear tenant
    new_tenant = {
        "tenant_id": "empresa_xyz",
        "tenant_name": "Empresa XYZ",
        "status": "active",

        # CAMPOS DE BALANCE: Deben coincidir con el prompt
        "balance_main_results_fields": [
            "disponibilidades_caja_banco_o_equivalentes",
            "activo_corriente",
            "activo_no_corriente",
            "activo_total",
            "pasivo_corriente",
            "pasivo_no_corriente",
            "pasivo_total",
            "patrimonio_neto"
        ],

        # CAMPOS DE INCOME: Deben coincidir con el prompt
        "income_main_results_fields": [
            "ingresos_operativos_empresa",
            "resultados_antes_de_impuestos",
            "resultados_del_ejercicio"
        ],

        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "created_by": "admin"  # O el username del admin
    }

    await db.tenants.insert_one(new_tenant)
    print("Tenant 'empresa_xyz' creado exitosamente")

    client.close()

if __name__ == "__main__":
    asyncio.run(add_tenant())
```

**Ejecutar desde la terminal:**

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar el script
python scripts/add_tenant_empresa_xyz.py

# Después de verificar que se creó correctamente, eliminar el script
rm scripts/add_tenant_empresa_xyz.py
```

**Alternativa: Inserción directa desde terminal con mongosh:**

```bash
# Conectar a MongoDB
mongosh "mongodb://localhost:27017/risco_db"

# Insertar el documento
db.tenants.insertOne({
  "tenant_id": "empresa_xyz",
  "tenant_name": "Empresa XYZ",
  "status": "active",
  "balance_main_results_fields": [
    "disponibilidades_caja_banco_o_equivalentes",
    "activo_corriente",
    "activo_no_corriente",
    "activo_total",
    "pasivo_corriente",
    "pasivo_no_corriente",
    "pasivo_total",
    "patrimonio_neto"
  ],
  "income_main_results_fields": [
    "ingresos_operativos_empresa",
    "resultados_antes_de_impuestos",
    "resultados_del_ejercicio"
  ],
  "created_at": new Date(),
  "updated_at": new Date(),
  "created_by": "admin"
})
```

#### 10.6. Paso 5: Verificar el Tenant

**Opción A: Verificar en MongoDB**

```bash
mongosh "mongodb://localhost:27017/risco_db"

# Buscar el tenant
db.tenants.findOne({"tenant_id": "empresa_xyz"})
```

**Opción B: Verificar desde Python**

```python
# En terminal interactivo de Python
source .venv/bin/activate
python

>>> from app.services.tenant_config import get_tenant_config
>>> config = get_tenant_config("empresa_xyz")
>>> print(config.tenant_name)
Empresa XYZ
>>> print(config.balance_fields)
['disponibilidades_caja_banco_o_equivalentes', 'activo_corriente', ...]
>>> print(len(config.prompt_extract_balance) > 0)
True
```

#### 10.7. Paso 6: Migrar Usuarios Existentes (Si Aplica)

Si ya existen usuarios con el dominio de la nueva empresa:

```python
# Script temporal: scripts/migrate_users_to_empresa_xyz.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def migrate():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    # Actualizar usuarios con dominio específico
    result = await db.users.update_many(
        {"email": {"$regex": "@empresa.com$"}},
        {"$set": {"tenant_id": "empresa_xyz"}}
    )

    print(f"Usuarios actualizados: {result.modified_count}")
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
```

```bash
source .venv/bin/activate
python scripts/migrate_users_to_empresa_xyz.py
rm scripts/migrate_users_to_empresa_xyz.py
```

#### 10.8. Checklist de Verificación

Antes de considerar el tenant listo para producción:

- [ ] Carpeta `app/tenants/{tenant_id}/` creada
- [ ] Archivo `app/tenants/{tenant_id}/prompts.py` con `PROMPT_EXTRACT_BALANCE` y `PROMPT_EXTRACT_INCOME`
- [ ] Documento en colección `tenants` de MongoDB
- [ ] Campos `balance_main_results_fields` e `income_main_results_fields` definidos
- [ ] Mapeo de dominio agregado en `tenant_mapping.py` (si aplica)
- [ ] Verificación exitosa con `get_tenant_config(tenant_id)`
- [ ] Usuarios migrados (si aplica)
- [ ] Scripts temporales eliminados

#### 10.9. Estructura Final de Carpetas

```
app/
  tenants/
    __init__.py
    base/
      __init__.py
      prompts.py

    default/
      __init__.py
      prompts.py

    empresa_xyz/           # NUEVO TENANT
      __init__.py
      prompts.py

    # Futuros tenants...
```

#### 10.10. Notas Importantes

**Convenciones de Nombres:**

- `tenant_id`: Usar snake_case, sin espacios ni caracteres especiales (ej: `empresa_xyz`, `banco_nacion`)
- `tenant_name`: Puede tener espacios y mayúsculas (ej: "Empresa XYZ", "Banco Nación")

**Campos Personalizables:**

- Los campos en `balance_main_results_fields` e `income_main_results_fields` se pueden personalizar según las necesidades del tenant
- Los campos deben estar en snake_case
- El sistema generará automáticamente versiones `_actual` y `_anterior` de cada campo

**Prompts:**

- Los prompts pueden ser completamente diferentes entre tenants
- Deben generar JSON compatible con la estructura de modelos Pydantic
- Incluir ejemplos y validaciones específicas del dominio del tenant

**Fallback:**

- Si un tenant no se encuentra, el sistema usa automáticamente el tenant "default"
- Si un dominio no tiene mapeo, los usuarios se asignan al tenant "default"

---

## Entorno de Desarrollo

**Entorno Virtual:** El proyecto utiliza `.venv` como entorno virtual Python.

**Activación del entorno:**

```bash
source .venv/bin/activate
```

**Nota:** Todos los scripts de Python deben ejecutarse con el entorno virtual activado.

---

## Requerimientos No Funcionales

### 1. Performance

- **Cache de TenantConfig:** Mantener configuraciones en memoria para evitar lecturas repetidas de MongoDB
- **Índices MongoDB:** Asegurar índices en `tenant_id` para búsquedas eficientes
- **Carga Lazy:** Cargar configuración de tenant solo cuando se necesite, no en cada request

### 2. Seguridad

- **Aislamiento de Datos:** NUNCA permitir que un usuario vea documentos de otro tenant
- **Validación de tenant_id:** Verificar que el tenant exista y esté activo antes de procesar
- **Logs de Auditoría:** Registrar qué tenant ejecuta qué operaciones

### 3. Mantenibilidad

- **KISS (Keep It Simple, Stupid):** No agregar complejidad innecesaria
- **Convenciones Claras:** Nombres consistentes en prompts (`PROMPT_EXTRACT_BALANCE`, `PROMPT_EXTRACT_INCOME`)
- **Documentación:** Comentar claramente las modificaciones en el código

### 4. Escalabilidad

- **Preparado para 8-20 tenants:** El diseño debe soportar este rango sin cambios arquitecturales
- **Fácil Adición de Tenants:** Agregar un tenant nuevo debe ser simple:
  1. Crear carpeta `app/tenants/{tenant_id}/`
  2. Crear archivo `prompts.py` con los prompts
  3. Insertar documento en colección `tenants` con campos
  4. Agregar mapeo en `DOMAIN_TO_TENANT` si corresponde

---

## Plan de Implementación (Fases)

### Fase 1: Infraestructura Base

1. Crear colección `tenants` en MongoDB
2. Crear tenant "default" con configuración actual
3. Crear estructura de carpetas `app/tenants/`
4. Implementar `TenantConfig` en `app/services/tenant_config.py`
5. Crear scripts de inicialización

### Fase 2: Modificación de Modelos

1. Agregar campo `tenant_id` a `User` y `UserPublic`
2. Agregar campo `tenant_id` a `DocFile`
3. Crear módulo `app/services/tenant_mapping.py`
4. Modificar endpoints de registro para asignar tenant

### Fase 3: Modificación del Grafo

1. Agregar `tenant_id` a `DocumentProcessingState`
2. Modificar `start_node` para inyectar `tenant_id`
3. Modificar `upload_convert_node` para usar rutas S3 por tenant
4. Modificar `extract_balance_node` para usar prompts y modelos dinámicos
5. Modificar `extract_income_node` para usar prompts y modelos dinámicos

### Fase 4: Migración de Prompts

1. Mover prompts actuales a `app/tenants/default/prompts.py`
2. Actualizar imports en nodos de extracción
3. Mantener prompts comunes en `app/utils/prompts.py`

### Fase 5: Aislamiento de Datos

1. Modificar endpoints de CRUD para filtrar por `tenant_id`
2. Agregar índices a MongoDB
3. Migrar usuarios existentes a tenant "default" (UNA SOLA VEZ, luego eliminar script)
4. Migrar documentos existentes a tenant "default" (UNA SOLA VEZ, luego eliminar script)

---

## Criterios de Aceptación

### 1. Tenant "default" Funcional

- [ ] Existe colección `tenants` con documento "default"
- [ ] Usuarios nuevos se asignan a tenant "default" automáticamente
- [ ] Documentos nuevos se asocian al tenant del usuario
- [ ] Prompts de "default" están en `app/tenants/default/prompts.py`

### 2. TenantConfig Operativo

- [ ] `get_tenant_config("default")` retorna configuración válida
- [ ] Prompts se cargan correctamente desde archivos
- [ ] Campos de balance e income se obtienen de MongoDB
- [ ] Modelos Pydantic dinámicos se generan correctamente
- [ ] Rutas S3 incluyen `tenant_id` en el prefijo

### 3. Aislamiento de Datos

- [ ] Usuarios solo ven documentos de su propio tenant
- [ ] Búsquedas en CRUD filtran por `tenant_id`
- [ ] Índices en MongoDB están creados

### 4. Procesamiento Multi-Tenant

- [ ] Documentos se procesan con prompts del tenant correcto
- [ ] Datos extraídos usan campos configurados del tenant
- [ ] Archivos en S3 se almacenan en carpeta del tenant
- [ ] Logs indican qué tenant está procesando

### 5. Migración Exitosa

- [ ] Usuarios existentes tienen `tenant_id = "default"`
- [ ] Documentos existentes tienen `tenant_id = "default"`
- [ ] Sistema sigue funcionando sin cambios visibles para usuarios

### 6. Preparación para Futuros Tenants

- [ ] Documentación clara de cómo agregar un tenant
- [ ] Estructura de carpetas lista para nuevos tenants
- [ ] Mapeo de dominios configurable en `tenant_mapping.py`

---

## Notas Importantes

### Principio KISS (Keep It Simple, Stupid)

**NO agregar:**

- Configuraciones complejas innecesarias
- Múltiples capas de abstracción
- Features que no se usarán inmediatamente
- Validaciones excesivas que ralenticen el sistema

**SÍ agregar:**

- Solo lo necesario para multi-tenancy básico
- Código claro y mantenible
- Convenciones simples y consistentes

### Compatibilidad Hacia Atrás

**Crítico:** El sistema debe seguir funcionando para usuarios actuales sin cambios visibles.

**Estrategia:**

- Todos los usuarios existentes → tenant "default"
- Todos los documentos existentes → tenant "default"
- Configuración de "default" = configuración actual del sistema
- Prompts de "default" = prompts actuales

### Evolución Futura

**Este diseño prepara para:**

- Agregar nuevos tenants fácilmente
- Personalizar prompts por industria/sector
- Definir campos custom en resultados principales
- Mantener aislamiento de datos por organización

**NO está diseñado para (por ahora):**

- Personalización de validaciones contables
- Modelos IA diferentes por tenant
- Rate limiting por tenant
- Facturación/costos por tenant
- UI de administración de tenants

Estas features se agregarán en iteraciones futuras si se requieren.

---

## Referencias

### Archivos Clave a Modificar

1. `app/services/tenant_config.py` - **CREAR**
2. `app/services/tenant_mapping.py` - **CREAR**
3. `app/tenants/default/prompts.py` - **CREAR**
4. `app/services/graph_state.py` - **MODIFICAR** (agregar tenant_id)
5. `app/services/graph_nodes/n0_start_end.py` - **MODIFICAR** (inyectar tenant_id)
6. `app/services/graph_nodes/n1_upload_convert.py` - **MODIFICAR** (rutas S3 por tenant)
7. `app/services/graph_nodes/n3_extract_balance.py` - **MODIFICAR** (usar TenantConfig)
8. `app/services/graph_nodes/n3_extract_income.py` - **MODIFICAR** (usar TenantConfig)
9. `app/models/users.py` - **MODIFICAR** (agregar tenant_id)
10. `app/models/docs.py` - **MODIFICAR** (agregar tenant_id)
11. `app/api/endpoints/crud.py` - **MODIFICAR** (filtrar por tenant)
12. `app/api/endpoints/user_registration.py` - **MODIFICAR** (asignar tenant)

### Scripts a Crear

1. `scripts/init_tenants.py` - Inicialización de tenant default
2. `scripts/migrate_users_tenant.py` - Migración de usuarios (ejecutar una sola vez, luego eliminar)
3. `scripts/migrate_documents_tenant.py` - Migración de documentos (ejecutar una sola vez, luego eliminar)

**Nota sobre scripts de migración:** Los scripts `migrate_users_tenant.py` y `migrate_documents_tenant.py` deben ejecutarse UNA SOLA VEZ durante la implementación inicial. Después de verificar que la migración fue exitosa, estos archivos deben ser eliminados para evitar ejecuciones accidentales. Alternativamente, pueden ejecutarse directamente desde la terminal usando `mongosh` sin necesidad de crear archivos Python.

---

## Glosario

- **Tenant:** Organización o cliente que usa el sistema de manera aislada
- **tenant_id:** Identificador único del tenant (slug-friendly, ej: "default", "caucion_sa")
- **TenantConfig:** Clase que encapsula la configuración de un tenant
- **ESP:** Estado de Situación Patrimonial (Balance)
- **ER:** Estado de Resultados (Income Statement)
- **resultados_principales:** Campos principales extraídos de ESP/ER (configurables por tenant)
- **Modelo dinámico:** Modelo Pydantic generado en runtime basado en configuración
- **S3 prefix:** Ruta en S3 específica del tenant para almacenar documentos

---

## Contacto y Soporte

Para dudas sobre la implementación:

- Revisar este PRP en detalle
- Consultar código existente en archivos mencionados
- Seguir convenciones del codebase actual
- Aplicar principio KISS en todo momento
