# Refactorización del Modelo de Datos Financieros

## 📋 Resumen

Se ha refactorizado la estructura de datos para `BalanceMainResults` e `IncomeStatementMainResults` para usar listas directas en lugar de campos planos, eliminando el wrapper innecesario y haciendo la estructura más consistente con los demás campos (`detalles_*`).

## 🎯 Objetivo

Simplificar y hacer más mantenible la estructura de datos financieros, permitiendo:

- Mayor flexibilidad en los campos configurables por tenant
- Mejor documentación de cada concepto con etiquetas legibles
- Validaciones opcionales (ej: bienes de cambio)
- Compatibilidad hacia atrás con datos existentes
- Consistencia con el resto del modelo (todos los arrays son listas directas)

## 📊 Cambios en la Estructura

### Antes (Estructura Plana)

```python
{
    "resultados_principales": {
        "activo_total_actual": 1000.0,
        "activo_total_anterior": 900.0,
        "pasivo_total_actual": 600.0,
        "pasivo_total_anterior": 500.0,
        ...
    }
}
```

### Después (Estructura con Lista Directa)

```python
{
    "resultados_principales": [
        {
            "concepto_code": "activo_total",
            "concepto": "Activo Total",  # Opcional
            "monto_actual": 1000.0,
            "monto_anterior": 900.0
        },
        {
            "concepto_code": "pasivo_total",
            "concepto": "Pasivo Total",
            "monto_actual": 600.0,
            "monto_anterior": 500.0
        },
        ...
    ]
}
```

## 🔧 Archivos Modificados

### 1. Modelos (`app/models/`)

- **`docs_balance.py`**: Nuevo modelo `BalanceItem` con campos `concepto_code`, `concepto`, `monto_actual`, `monto_anterior`
- **`docs_income.py`**: Nuevo modelo `IncomeStatementItem` con la misma estructura

### 2. Configuración (`app/services/`)

- **`tenant_config.py`**:
  - Agregadas constantes `BALANCE_REQUIRED_FIELDS` e `INCOME_REQUIRED_FIELDS` como **diccionarios** (formato: `{concepto: etiqueta}`)
  - Campos configurables en MongoDB ahora son **objetos** en lugar de arrays
    - Propiedades `balance_fields` e `income_fields` retornan `dict` en lugar de `List[str]`

### 3. MongoDB (`tenants` collection)

- **Cambio de estructura**: Los campos `balance_main_results_fields` e `income_statement_main_results_fields` ahora son **objetos** (no arrays)
- **Formato**: `{"concepto": "Etiqueta Legible"}`
- **Ejemplo**: `{"activo_total": "Activo Total", "pasivo_total": "Pasivo Total"}`

- **`n4_validate.py`**: Actualizado para usar `FinancialDataAccessor` que soporta ambas estructuras

### 4. Validaciones (`app/services/graph_nodes/`)

- **`n4_validate.py`**: Actualizado para usar `FinancialDataAccessor` que soporta ambas estructuras

````

### 3. MongoDB (`tenants` collection)

- **Cambio de estructura**: Los campos `balance_main_results_fields` e `income_statement_main_results_fields` ahora son **objetos** (no arrays)
- **Formato**: `{"concepto": "Etiqueta Legible"}`
- **Ejemplo**: `{"activo_total": "Activo Total", "pasivo_total": "Pasivo Total"}`

- **`n4_validate.py`**: Actualizado para usar `FinancialDataAccessor` que soporta ambas estructuras

### 4. Validaciones (`app/services/graph_nodes/`)

- **`n4_validate.py`**: Actualizado para usar `FinancialDataAccessor` que soporta ambas estructuras

### 5. Utilidades (`app/utils/`)

- **`financial_data_accessor.py`**: Nuevo helper para acceso unificado a datos financieros (NUEVO)

### 6. Prompts (`app/tenants/default/`)

- **`prompts.py`**: Actualizados `PROMPT_EXTRACT_BALANCE` y `PROMPT_EXTRACT_INCOME` para generar nueva estructura

## 📝 Campos Requeridos

### Balance (Mínimo)

```python
# Formato v2.0: Diccionario {concepto: etiqueta}
BALANCE_REQUIRED_FIELDS = {
    "activo_total": "Activo Total",
    "activo_corriente": "Activo Corriente",
    "activo_no_corriente": "Activo No Corriente",
    "pasivo_total": "Pasivo Total",
    "pasivo_corriente": "Pasivo Corriente",
    "pasivo_no_corriente": "Pasivo No Corriente",
    "patrimonio_neto": "Patrimonio Neto",
    "disponibilidades": "Disponibilidades"
}
````

### Income Statement (Mínimo)

```python
# Formato v2.0: Diccionario {concepto: etiqueta}
INCOME_REQUIRED_FIELDS = {
    "ingresos_por_venta": "Ingresos por Venta",  # Antes: "ingresos_operativos_empresa"
    "resultados_antes_de_impuestos": "Resultados Antes de Impuestos",
    "resultados_del_ejercicio": "Resultados del Ejercicio"
}
```

### Campos Opcionales

- **`bienes_de_cambio`**: Las validaciones que involucran este campo se saltan si no está presente

### Configuración en MongoDB

En la colección `tenants`, los campos se definen como **objetos**:

```javascript
{
  "balance_main_results_fields": {
    "activo_total": "Activo Total",
    "pasivo_total": "Pasivo Total",
    // ... más campos
  },
  "income_statement_main_results_fields": {
    "ingresos_por_venta": "Ingresos por Venta",
    // ... más campos
  }
}
```

    "resultados_antes_de_impuestos",
    "resultados_del_ejercicio"

]

````

### Campos Opcionales

- **`bienes_de_cambio`**: Las validaciones que involucran este campo se saltan si no está presente

## 🔄 Compatibilidad Hacia Atrás

El helper `FinancialDataAccessor` permite leer tanto la estructura antigua como la nueva:

```python
from app.utils.financial_data_accessor import create_accessor

# Funciona con ambas estructuras
accessor = create_accessor(balance_data['resultados_principales'])

# Acceso unificado
activo_total_actual = accessor.get('activo_total', 'actual')
activo_total_anterior = accessor.get('activo_total', 'anterior')

# Verificar existencia de campo opcional
if accessor.has('bienes_de_cambio'):
    bienes_cambio = accessor.get('bienes_de_cambio', 'actual')
````

## 🧪 Validaciones Actualizadas

Las validaciones en `n4_validate.py` ahora:

1. ✅ Usan `FinancialDataAccessor` para acceso a datos
2. ✅ Verifican existencia de valores antes de validar (evita errores con None)
3. ✅ Saltean validaciones si falta campo opcional (ej: `bienes_de_cambio`)
4. ✅ Mantienen compatibilidad con datos antiguos en BD

## 🚀 Beneficios

1. **Simplicidad (KISS)**: Estructura más simple y consistente
2. **Flexibilidad**: Fácil agregar/quitar conceptos por tenant
3. **Documentación**: Cada concepto puede tener etiqueta legible
4. **Mantenibilidad**: Código más limpio y fácil de entender
5. **Compatibilidad**: No rompe datos existentes

## ⚠️ Migración de Datos Existentes

Los datos existentes en la estructura antigua seguirán funcionando gracias al `FinancialDataAccessor`.

Para migrar datos antiguos a nueva estructura (opcional):

```python
# Script de migración (ejemplo)
old_data = {
    "activo_total_actual": 1000.0,
    "activo_total_anterior": 900.0
}

new_data = [
    {
        "concepto_code": "activo_total",
        "concepto": "Activo Total",
        "monto_actual": 1000.0,
        "monto_anterior": 900.0
    }
]
```

## 📚 Ejemplos de Uso

### Crear Modelo Balance

```python
from app.services.tenant_config import get_tenant_config

tenant_config = get_tenant_config("mi_tenant")
BalanceMainResults = tenant_config.create_balance_model()
```

### Validar Datos

```python
from app.utils.financial_data_accessor import create_accessor

balance_accessor = create_accessor(balance_data['resultados_principales'])

# Validación 1: A = P + PN
activo = balance_accessor.get('activo_total', 'actual')
pasivo = balance_accessor.get('pasivo_total', 'actual')
pn = balance_accessor.get('patrimonio_neto', 'actual')

if activo and pasivo and pn:
    if abs(activo - (pasivo + pn)) > TOLERANCE:
        # Error de validación
        pass
```

## 🎓 Nombres de Conceptos

Los nombres de conceptos deben seguir convención `snake_case`:

### Balance

- `activo_total`, `activo_corriente`, `activo_no_corriente`
- `pasivo_total`, `pasivo_corriente`, `pasivo_no_corriente`
- `patrimonio_neto`
- `disponibilidades`
- `bienes_de_cambio` (opcional)

### Income Statement

- `ingresos_por_venta` (antes: `ingresos_operativos_empresa`)
- `resultados_antes_de_impuestos`
- `resultados_del_ejercicio`

---

**Fecha de implementación**: 2025-10-01  
**Versión**: 2.0  
**Principio aplicado**: KISS (Keep It Simple, Stupid)
