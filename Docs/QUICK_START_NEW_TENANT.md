# Guía Rápida de Implementación Multi-Tenant

## Agregar un Nuevo Tenant (Ejemplo)

### Paso "activo_total": "Activo Total",

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

````ura de archivos

```bash
# Crear carpeta del tenant
mkdir -p app/tenants/empresa_xyz
touch app/tenants/empresa_xyz/__init__.py
````

### Paso 2: Crear archivo de prompts

Crear `app/tenants/empresa_xyz/prompts.py`:

```python
"""Prompts personalizados para Empresa XYZ."""

PROMPT_EXTRACT_BALANCE = """
[Tus instrucciones personalizadas para balance...]
"""

PROMPT_EXTRACT_INCOME = """
[Tus instrucciones personalizadas para income...]
"""
```

### Paso 3: Mapear dominio de email

Editar `app/services/tenant_mapping.py`:

```python
DOMAIN_TO_TENANT = {
    "caucion.com.ar": "default",
    "empresaxyz.com": "empresa_xyz",  # NUEVO
}
```

### Paso 4: Insertar en MongoDB

```javascript
// Opción A: Usar mongosh
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
    bienes_de_cambio: "Bienes de Cambio", // Opcional
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

**Nota importante**:

- `balance_main_results_fields` e `income_statement_main_results_fields` son **objetos** (no arrays)
- Formato: `{concepto: "Etiqueta Legible"}`
- El concepto es la clave (snake_case) y la etiqueta es el valor
- Ver `FINANCIAL_DATA_REFACTORING.md` para más detalles sobre estructura v2.0

O crear un script Python temporal:

```python
# scripts/add_tenant_empresa_xyz.py
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB

async def add_tenant():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

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

asyncio.run(add_tenant())
```

```bash
python scripts/add_tenant_empresa_xyz.py
rm scripts/add_tenant_empresa_xyz.py
```

### Paso 5: Verificar

```python
from app.services.tenant_config import get_tenant_config

config = get_tenant_config("empresa_xyz")
print(config.tenant_name)  # "Empresa XYZ"
```

## Cambios Clave en el Sistema

### 1. Modelos con `tenant_id`

- `User` y `UserPublic`: Tienen campo `tenant_id`
- `DocFile`: Tiene campo `tenant_id`
- `DocumentProcessingState`: Tiene campo `tenant_id`

### 2. Endpoints CRUD con Filtrado

- `GET /documents`: Solo muestra documentos del tenant del usuario
- `GET /document/{id}`: Verifica pertenencia al tenant
- `PUT /update_docfile/{id}`: Solo actualiza documentos del tenant
- `DELETE /document/{id}`: Solo borra documentos del tenant

### 3. Registro de Usuarios

- `POST /register`: Asigna `tenant_id` automáticamente basado en el dominio del email

### 4. Procesamiento con Tenant

- Los nodos del grafo LangGraph usan configuración del tenant
- Prompts cargados dinámicamente desde `app/tenants/{tenant_id}/prompts.py`
- Modelos Pydantic generados dinámicamente basados en campos configurados
- Rutas S3 específicas por tenant: `{env}/{tenant_id}/documents/{docfile_id}/`

## Estructura de Archivos S3

```
s3://bucket/
  prod/
    default/
      documents/
        abc123/
          pdf_file/
            documento.pdf
          images/
            page_001.png
            page_002.png
    empresa_xyz/
      documents/
        xyz789/
          pdf_file/
            documento.pdf
          images/
            page_001.png
```

## Troubleshooting Común

### ❌ Error: "Tenant 'default' no existe en la base de datos"

```bash
python scripts/init_tenants.py
```

### ❌ Error: "No se encontraron prompts para tenant 'xxx'"

1. Verificar que existe `app/tenants/xxx/prompts.py`
2. Verificar que exporta `PROMPT_EXTRACT_BALANCE` y `PROMPT_EXTRACT_INCOME`

### ❌ Usuarios no se asignan al tenant correcto

1. Verificar `app/services/tenant_mapping.py`
2. El dominio debe coincidir exactamente (después del @)

### ❌ Cache desactualizado

```python
from app.services.tenant_config import clear_tenant_cache
clear_tenant_cache()  # Limpiar todo
# O
clear_tenant_cache("empresa_xyz")  # Limpiar uno específico
```

## Documentación Completa

Para información detallada, consultar:

- **MULTI_TENANT_README.md**: Documentación completa de implementación
- **FINANCIAL_DATA_REFACTORING.md**: Nueva estructura de datos financieros (v2.0)
- **PRP_TENANTS.md**: Product Requirements Prompt original

## Cambios Importantes en v2.0

### Nueva Estructura de Datos

Los resultados principales ahora son directamente una **lista** en lugar de campos planos:

```python
# Nueva estructura (v2.0) - Lista directa
{
    "resultados_principales": [
        {
            "concepto_code": "activo_total",
            "concepto": "Activo Total",  # Opcional
            "monto_actual": 1000.0,
            "monto_anterior": 900.0
        },
        # ... más items
    ]
}

# Estructura antigua (v1.0) - Todavía soportada
{
    "resultados_principales": {
        "activo_total_actual": 1000.0,
        "activo_total_anterior": 900.0,
        # ... más campos
    }
}
```

### Campos Requeridos y Opcionales

**Balance (Mínimos requeridos)**:

- `activo_total`, `activo_corriente`, `activo_no_corriente`
- `pasivo_total`, `pasivo_corriente`, `pasivo_no_corriente`
- `patrimonio_neto`, `disponibilidades`

**Balance (Opcionales)**:

- `bienes_de_cambio` (validaciones que lo usan se saltean si no está)

**Income (Mínimos requeridos)**:

- `ingresos_por_venta` (antes: `ingresos_operativos_empresa`)
- `resultados_antes_de_impuestos`
- `resultados_del_ejercicio`

### Compatibilidad Hacia Atrás

✅ El sistema soporta **ambas estructuras** simultáneamente gracias a `FinancialDataAccessor`  
✅ Los datos existentes en estructura v1.0 siguen funcionando sin necesidad de migración  
✅ Los nuevos tenants deben usar estructura v2.0 en sus prompts

## Resumen de Compatibilidad

✅ **Compatibilidad hacia atrás 100%**:

- Usuarios existentes → tenant "default"
- Documentos existentes → tenant "default"
- Configuración de "default" = configuración actual del sistema
- No hay cambios visibles para usuarios actuales
