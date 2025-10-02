# Sistema Multi-Tenant - Documentación de Implementación

## Resumen

Este documento describe la implementación del sistema multi-tenant para Risco Backend, que permite a diferentes organizaciones (tenants) tener configuraciones personalizadas de prompts, campos de resultados y almacenamiento S3.

## Cambios Implementados

### 1. Estructura de Tenants

Se creó la siguiente estructura de carpetas:

```
app/
  tenants/
    __init__.py
    base/
      __init__.py
      prompts.py          # Prompts genéricos reutilizables
    default/
      __init__.py
      prompts.py          # Prompts del tenant "default"
```

Cada tenant tiene su propia carpeta con archivos de prompts personalizados:

- `PROMPT_EXTRACT_BALANCE`: Para extracción de Estado de Situación Patrimonial
- `PROMPT_EXTRACT_INCOME`: Para extracción de Estado de Resultados

### 2. Servicios Multi-Tenant

#### `app/services/tenant_config.py`

- Clase `TenantConfig`: Carga configuración desde MongoDB y archivos Python
- Factory `get_tenant_config(tenant_id)`: Con cache en memoria
- Genera modelos Pydantic dinámicos basados en campos configurados
- Genera rutas S3 específicas por tenant

#### `app/services/tenant_mapping.py`

- Mapeo de dominios de email a tenant_id
- Función `get_tenant_id_from_email(email)`

### 3. Modelos de Datos Modificados

#### `app/models/users.py`

- Agregado campo `tenant_id: str = "default"` en `User`
- Agregado campo `tenant_id: str = "default"` en `UserPublic`

#### `app/models/docs.py`

- Agregado campo `tenant_id: str = "default"` en `DocFile`

#### `app/services/graph_state.py`

- Agregado campo `tenant_id: str` en `DocumentProcessingState`

### 4. Nodos del Grafo Modificados

#### `n0_start_end.py`

- `start_node()`: Inyecta `tenant_id` desde `requester.tenant_id`

#### `n1_upload_convert.py`

- Guarda `tenant_id` en nuevos documentos
- Usa rutas S3 específicas del tenant mediante `TenantConfig.get_s3_prefix()`

#### `n3_extract_balance.py`

- Carga prompts específicos del tenant
- Genera modelos Pydantic dinámicos basados en campos configurados
- Usa `TenantConfig.create_balance_model()` y `PROMPT_EXTRACT_BALANCE`

#### `n3_extract_income.py`

- Carga prompts específicos del tenant
- Genera modelos Pydantic dinámicos basados en campos configurados
- Usa `TenantConfig.create_income_model()` y `PROMPT_EXTRACT_INCOME`

### 5. Endpoints Modificados

#### `app/api/endpoints/crud.py`

Todos los endpoints CRUD ahora filtran por `tenant_id`:

- `GET /documents`: Lista solo documentos del tenant del usuario
- `GET /document/{docfile_id}`: Verifica que el documento pertenezca al tenant
- `GET /document/{docfile_id}/download`: Verifica pertenencia al tenant
- `PUT /update_docfile/{docfile_id}`: Solo actualiza documentos del tenant
- `DELETE /document/{docfile_id}`: Solo borra documentos del tenant

#### `app/api/endpoints/user_registration.py`

- `POST /register`: Asigna `tenant_id` basado en el dominio del email

### 6. Base de Datos MongoDB

#### Nueva Colección: `tenants`

```javascript
{
  "_id": ObjectId,
  "tenant_id": "default",
  "tenant_name": "Default",
  "status": "active",
  "balance_main_results_fields": {
    "activo_total": "Activo Total",
    "activo_corriente": "Activo Corriente",
    "activo_no_corriente": "Activo No Corriente",
    "pasivo_total": "Pasivo Total",
    "pasivo_corriente": "Pasivo Corriente",
    "pasivo_no_corriente": "Pasivo No Corriente",
    "patrimonio_neto": "Patrimonio Neto",
    "disponibilidades": "Disponibilidades",
    "bienes_de_cambio": "Bienes de Cambio"  // Opcional
  },
  "income_statement_main_results_fields": {
    "ingresos_por_venta": "Ingresos por Venta",
    "resultados_antes_de_impuestos": "Resultados Antes de Impuestos",
    "resultados_del_ejercicio": "Resultados del Ejercicio"
  },
  "created_at": ISODate,
  "updated_at": ISODate,
  "created_by": "system"
}
```

**Nota sobre la estructura**:

- `balance_main_results_fields` e `income_statement_main_results_fields` son **objetos** (no arrays)
- Formato: `{"concepto": "Etiqueta Legible"}`
- La clave es el identificador del concepto (snake_case)
- El valor es la etiqueta legible que se mostrará al usuario

**Nota sobre la estructura de datos**: A partir de la versión 2.0, los resultados principales son directamente una lista (ver `FINANCIAL_DATA_REFACTORING.md`):

```javascript
// Nueva estructura (v2.0+) - Lista directa
"resultados_principales": [
  {
    "concepto_code": "activo_total",
    "concepto": "Activo Total",  // Opcional
    "monto_actual": 1000.0,
    "monto_anterior": 900.0
  },
  // ... más items
]

// Estructura antigua (v1.0) - Todavía soportada
"resultados_principales": {
  "activo_total_actual": 1000.0,
  "activo_total_anterior": 900.0,
  // ... más campos
}
```

El sistema mantiene compatibilidad hacia atrás con ambas estructuras mediante `FinancialDataAccessor`.

#### Índices Creados

- `tenants.tenant_id`: Único
- `users.tenant_id`: Para búsquedas eficientes
- `documents.tenant_id + upload_date`: Compuesto para listados

## Scripts de Inicialización y Migración

### `scripts/init_tenants.py`

**Propósito**: Inicializa el tenant 'default' y crea índices en MongoDB.

**Cuándo ejecutar**:

- Una vez, antes de iniciar el sistema con multi-tenant por primera vez.

**Uso**:

```bash
python scripts/init_tenants.py
```

**Qué hace**:

1. Crea el documento del tenant 'default' en MongoDB
2. Crea índices únicos y compuestos necesarios
3. Muestra instrucciones para próximos pasos

### `scripts/migrate_users_tenant.py`

**Propósito**: Migra usuarios existentes al tenant 'default'.

**Cuándo ejecutar**:

- Una sola vez, si ya tienes usuarios en la base de datos sin `tenant_id`.

**Uso**:

```bash
python scripts/migrate_users_tenant.py
# Después de verificar que la migración fue exitosa:
rm scripts/migrate_users_tenant.py
```

**⚠️ IMPORTANTE**: Este script debe eliminarse después de ejecutarlo para evitar ejecuciones accidentales.

### `scripts/migrate_documents_tenant.py`

**Propósito**: Migra documentos existentes al tenant 'default'.

**Cuándo ejecutar**:

- Una sola vez, si ya tienes documentos en la base de datos sin `tenant_id`.

**Uso**:

```bash
python scripts/migrate_documents_tenant.py
# Después de verificar que la migración fue exitosa:
rm scripts/migrate_documents_tenant.py
```

**⚠️ IMPORTANTE**: Este script debe eliminarse después de ejecutarlo para evitar ejecuciones accidentales.

## Proceso de Implementación (Pasos)

### Para Sistema Nuevo (Sin Datos Existentes)

1. **Inicializar el tenant default**:

   ```bash
   python scripts/init_tenants.py
   ```

2. **Iniciar el servidor**:
   ```bash
   # El sistema ya está listo para usarse
   uvicorn app.main:app --reload
   ```

### Para Sistema con Datos Existentes

1. **Inicializar el tenant default**:

   ```bash
   python scripts/init_tenants.py
   ```

2. **Migrar usuarios existentes**:

   ```bash
   python scripts/migrate_users_tenant.py
   # Verificar que la migración fue exitosa
   rm scripts/migrate_users_tenant.py
   ```

3. **Migrar documentos existentes**:

   ```bash
   python scripts/migrate_documents_tenant.py
   # Verificar que la migración fue exitosa
   rm scripts/migrate_documents_tenant.py
   ```

4. **Iniciar el servidor**:
   ```bash
   uvicorn app.main:app --reload
   ```

## Cómo Agregar un Nuevo Tenant

### 1. Crear carpeta de prompts

```bash
mkdir -p app/tenants/empresa_xyz
touch app/tenants/empresa_xyz/__init__.py
```

### 2. Crear archivo de prompts

Crear `app/tenants/empresa_xyz/prompts.py`:

```python
"""
Prompts personalizados para Empresa XYZ.
"""

PROMPT_EXTRACT_BALANCE = """
[Instrucciones específicas para extracción de balance...]
"""

PROMPT_EXTRACT_INCOME = """
[Instrucciones específicas para extracción de income...]
"""
```

**IMPORTANTE**: Los nombres de las constantes deben ser exactamente:

- `PROMPT_EXTRACT_BALANCE`
- `PROMPT_EXTRACT_INCOME`

### 3. Agregar mapeo de dominio

Editar `app/services/tenant_mapping.py`:

```python
DOMAIN_TO_TENANT = {
    "caucion.com.ar": "default",
    "empresa.com": "empresa_xyz",  # NUEVO
}
```

### 4. Insertar configuración en MongoDB

Opción A - Script Python:

```python
# scripts/add_tenant_empresa_xyz.py
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def add_tenant():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    existing = await db.tenants.find_one({"tenant_id": "empresa_xyz"})
    if existing:
        print("Tenant ya existe")
        return

    new_tenant = {
        "tenant_id": "empresa_xyz",
        "tenant_name": "Empresa XYZ",
        "status": "active",
        "balance_main_results_fields": {
            "activo_total": "Activo Total",
            "activo_corriente": "Activo Corriente",
            "activo_no_corriente": "Activo No Corriente",
            "pasivo_total": "Pasivo Total",
            "pasivo_corriente": "Pasivo Corriente",
            "pasivo_no_corriente": "Pasivo No Corriente",
            "patrimonio_neto": "Patrimonio Neto",
            "disponibilidades": "Disponibilidades",
            "bienes_de_cambio": "Bienes de Cambio"  # Opcional
        },
        "income_statement_main_results_fields": {
            "ingresos_por_venta": "Ingresos por Venta",
            "resultados_antes_de_impuestos": "Resultados Antes de Impuestos",
            "resultados_del_ejercicio": "Resultados del Ejercicio"
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "created_by": "admin"
    }

    await db.tenants.insert_one(new_tenant)
    print("✓ Tenant creado")
    client.close()

if __name__ == "__main__":
    asyncio.run(add_tenant())
```

```bash
python scripts/add_tenant_empresa_xyz.py
rm scripts/add_tenant_empresa_xyz.py
```

Opción B - MongoDB Shell:

```bash
mongosh "mongodb://localhost:27017/risco_db"
```

```javascript
db.tenants.insertOne({
  tenant_id: "empresa_xyz",
  tenant_name: "Empresa XYZ",
  status: "active",
  balance_main_results_fields: {
    activo_total: "Activo Total",
    activo_corriente: "Activo Corriente",
    activo_no_corriente: "Activo No Corriente",
    pasivo_total: "Pasivo Total",
    pasivo_corriente: "Pasivo Corriente",
    pasivo_no_corriente: "Pasivo No Corriente",
    patrimonio_neto: "Patrimonio Neto",
    disponibilidades: "Disponibilidades",
    bienes_de_cambio: "Bienes de Cambio",
  },
  income_statement_main_results_fields: {
    ingresos_por_venta: "Ingresos por Venta",
    resultados_antes_de_impuestos: "Resultados Antes de Impuestos",
    resultados_del_ejercicio: "Resultados del Ejercicio",
  },
  created_at: new Date(),
  updated_at: new Date(),
  created_by: "admin",
});
```

### 5. Verificar el tenant

```python
from app.services.tenant_config import get_tenant_config

config = get_tenant_config("empresa_xyz")
print(config.tenant_name)  # "Empresa XYZ"
print(config.balance_fields)  # Lista de campos
print(len(config.prompt_extract_balance) > 0)  # True
```

### 6. Migrar usuarios existentes (opcional)

Si ya existen usuarios con el dominio del nuevo tenant:

```python
# scripts/migrate_users_to_empresa_xyz.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def migrate():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    result = await db.users.update_many(
        {"email": {"$regex": "@empresa.com$"}},
        {"$set": {"tenant_id": "empresa_xyz"}}
    )

    print(f"Usuarios actualizados: {result.modified_count}")
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
```

## Almacenamiento en S3

### Estructura de Carpetas por Tenant

```
s3://{bucket}/{environment}/{tenant_id}/documents/{docfile_id}/
  ├── pdf_file/
  │   └── {filename}.pdf
  └── images/
      ├── page_001.png
      ├── page_002.png
      └── ...
```

**Ejemplo**:

- Tenant "default": `s3://bucket/prod/default/documents/abc123/...`
- Tenant "empresa_xyz": `s3://bucket/prod/empresa_xyz/documents/xyz789/...`

## Aislamiento de Datos

### Nivel de Usuario

- Cada usuario tiene un `tenant_id` asignado al momento del registro
- El `tenant_id` se deriva del dominio del email según `DOMAIN_TO_TENANT`
- Fallback automático a "default" si no hay mapeo

### Nivel de Documento

- Todos los documentos creados heredan el `tenant_id` del usuario
- Los filtros en MongoDB siempre incluyen `tenant_id`
- Usuarios solo ven y acceden a documentos de su propio tenant

### Nivel de API

- Todos los endpoints CRUD filtran por `tenant_id`
- Imposible acceder a documentos de otro tenant (404 si se intenta)

## Personalización por Tenant

### 1. Prompts

- Completamente personalizables por tenant
- Ubicados en `app/tenants/{tenant_id}/prompts.py`
- Deben exportar `PROMPT_EXTRACT_BALANCE` y `PROMPT_EXTRACT_INCOME`

### 2. Campos de Resultados Principales

- Definidos en MongoDB: `balance_main_results_fields` e `income_statement_main_results_fields`
- Los modelos Pydantic se generan dinámicamente en tiempo de ejecución
- **Nueva estructura (v2.0+)**: Cada concepto genera un item con `concepto_code`, `concepto` (opcional), `monto_actual` y `monto_anterior`. Los items se devuelven como lista directa en `resultados_principales`
- **Campos mínimos requeridos**:
  - Balance: `activo_total`, `activo_corriente`, `activo_no_corriente`, `pasivo_total`, `pasivo_corriente`, `pasivo_no_corriente`, `patrimonio_neto`, `disponibilidades`
  - Income: `ingresos_por_venta`, `resultados_antes_de_impuestos`, `resultados_del_ejercicio`
- **Campos opcionales**: `bienes_de_cambio` (las validaciones que lo usan se saltean si no está presente)

Ver `Docs/FINANCIAL_DATA_REFACTORING.md` para más detalles sobre la estructura de datos.

### 3. Almacenamiento S3

- Carpetas separadas por tenant
- Prefijo: `{S3_ENVIRONMENT}/{tenant_id}/documents/{docfile_id}/`

## Compatibilidad Hacia Atrás

- ✅ Todos los usuarios existentes se migran al tenant "default"
- ✅ Todos los documentos existentes se migran al tenant "default"
- ✅ La configuración de "default" es idéntica al sistema anterior
- ✅ No hay cambios visibles para usuarios actuales

## Consideraciones de Performance

- **Cache**: Las configuraciones de tenant se cachean en memoria
- **Índices**: Creados en `tenant_id` para búsquedas eficientes
- **Modelos dinámicos**: Se crean una vez por request, bajo overhead

## Limitaciones Actuales

**NO personalizable por tenant**:

- Modelos IA utilizados (común para todos)
- Validaciones contables (comunes para todos)
- Tolerancias de error (comunes para todos)
- Rate limiting (común para todos)
- Formatos de exportación (comunes para todos)
- Reglas de reconocimiento OCR (comunes para todos)

## Troubleshooting

### Error: "Tenant 'default' no existe en la base de datos"

**Solución**: Ejecutar `python scripts/init_tenants.py`

### Error: "No se encontraron prompts para tenant 'xxx'"

**Solución**:

1. Verificar que existe `app/tenants/{tenant_id}/prompts.py`
2. Verificar que exporta `PROMPT_EXTRACT_BALANCE` y `PROMPT_EXTRACT_INCOME`

### Usuarios no se asignan al tenant correcto

**Solución**:

1. Verificar mapeo en `app/services/tenant_mapping.py`
2. El dominio debe coincidir exactamente (después del @)

### Cache de TenantConfig desactualizado

**Solución**:

```python
from app.services.tenant_config import clear_tenant_cache

# Limpiar cache de un tenant específico
clear_tenant_cache("empresa_xyz")

# O limpiar todo el cache
clear_tenant_cache()
```

## Resumen de Archivos Modificados

### Archivos Creados

- `app/tenants/__init__.py`
- `app/tenants/base/__init__.py`
- `app/tenants/base/prompts.py`
- `app/tenants/default/__init__.py`
- `app/tenants/default/prompts.py`
- `app/services/tenant_config.py`
- `app/services/tenant_mapping.py`
- `app/utils/financial_data_accessor.py` (v2.0+)
- `app/models/docs_balance.py` (v2.0+)
- `app/models/docs_income.py` (v2.0+)
- `scripts/init_tenants.py`
- `scripts/migrate_users_tenant.py`
- `scripts/migrate_documents_tenant.py`
- `Docs/FINANCIAL_DATA_REFACTORING.md` (v2.0+)

### Archivos Modificados

- `app/models/users.py`: Agregado campo `tenant_id`
- `app/models/docs.py`: Agregado campo `tenant_id`
- `app/services/graph_state.py`: Agregado campo `tenant_id`
- `app/services/graph_nodes/n0_start_end.py`: Inyección de `tenant_id`
- `app/services/graph_nodes/n1_upload_convert.py`: Rutas S3 por tenant
- `app/services/graph_nodes/n3_extract_balance.py`: Prompts y modelos dinámicos (v2.0: estructura con items)
- `app/services/graph_nodes/n3_extract_income.py`: Prompts y modelos dinámicos (v2.0: estructura con items)
- `app/services/graph_nodes/n4_validate.py`: Validaciones con `FinancialDataAccessor` (v2.0)
- `app/api/endpoints/crud.py`: Filtrado por `tenant_id`
- `app/api/endpoints/user_registration.py`: Asignación de `tenant_id`
- `app/tenants/default/prompts.py`: Actualizado para estructura v2.0

## Contacto y Soporte

Para dudas sobre la implementación, consultar:

1. Este documento (MULTI_TENANT_README.md)
2. Refactorización de datos financieros (FINANCIAL_DATA_REFACTORING.md)
3. El PRP original (PRP_TENANTS.md)
4. Guía rápida (QUICK_START_NEW_TENANT.md)
5. Código fuente en los archivos mencionados

## Versiones

- **v1.0**: Implementación inicial multi-tenant con estructura de campos planos
- **v2.0**: Refactorización a estructura basada en items con compatibilidad hacia atrás (2025-10-01)
