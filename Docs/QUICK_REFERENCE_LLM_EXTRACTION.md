# Guía Rápida: Extracción de Datos Financieros con LLM

## TL;DR - Para Desarrolladores

Cuando el LLM extrae datos financieros:

1. **Extrae** → Modelos `*ForLLM` (sin campo `concepto`)
2. **Post-procesa** → Agrega `concepto` desde `tenant_config`
3. **Almacena** → Modelos completos con `concepto` exacto de configuración

## ¿Por Qué?

**Problema:** LLM reescribía el campo `concepto` con sus propias interpretaciones
**Solución:** LLM no extrae `concepto`, se agrega programáticamente desde tenant config

## Modelos Disponibles

### Balance Sheet

```python
# Para LLM (extracción)
from app.models.docs_balance import BalanceDataForLLM, BalanceItemForLLM

# Para almacenamiento (completo)
from app.models.docs_balance import BalanceData, BalanceItem
```

**BalanceItemForLLM** - Solo 3 campos:

- `concepto_code: str` ← LLM extrae
- `monto_actual: float` ← LLM extrae
- `monto_anterior: float` ← LLM extrae
- ❌ `concepto` NO existe (se agrega después)

**BalanceItem** - Completo (4 campos):

- `concepto_code: str`
- `concepto: Optional[str]` ← De tenant_config
- `monto_actual: float`
- `monto_anterior: float`

### Income Statement

```python
# Para LLM (extracción)
from app.models.docs_income import IncomeStatementDataForLLM, IncomeStatementItemForLLM

# Para almacenamiento (completo)
from app.models.docs_income import IncomeStatementData, IncomeStatementItem
```

Misma estructura que balance.

## Patrón de Uso

### Paso 1: Extracción con LLM

```python
# Usar modelo ForLLM (sin 'concepto')
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    max_tokens=13000,
    max_retries=1
).with_structured_output(BalanceDataForLLM)  # ← Modelo simplificado

# Extraer
extracted_balance_llm = await model.ainvoke(prompt)
```

### Paso 2: Post-procesamiento

```python
from app.models.docs_balance import BalanceItem

# Agregar 'concepto' desde tenant_config
resultados_principales_completos = []
for item_llm in extracted_balance_llm.resultados_principales:
    # Obtener etiqueta de configuración
    concepto_label = tenant_config.balance_fields.get(
        item_llm.concepto_code,
        item_llm.concepto_code  # fallback
    )

    # Crear item completo
    item_completo = BalanceItem(
        concepto_code=item_llm.concepto_code,
        concepto=concepto_label,  # ← De config, NO del LLM
        monto_actual=item_llm.monto_actual,
        monto_anterior=item_llm.monto_anterior
    )
    resultados_principales_completos.append(item_completo)
```

### Paso 3: Crear modelo completo

```python
# Crear modelo final para almacenar
extracted_balance = BalanceData(
    informacion_general=extracted_balance_llm.informacion_general,
    resultados_principales=resultados_principales_completos,  # ← Con 'concepto'
    detalles_activo=extracted_balance_llm.detalles_activo,
    detalles_pasivo=extracted_balance_llm.detalles_pasivo,
    detalles_patrimonio_neto=extracted_balance_llm.detalles_patrimonio_neto
)
```

## Configuración de Tenant

Las etiquetas se definen en `/app/services/tenant_config.py`:

```python
class TenantConfig:
    balance_fields: Dict[str, str] = {
        "activo_total": "Total Activo",
        "pasivo_total": "Total Pasivo",
        # ...
    }

    income_fields: Dict[str, str] = {
        "ingresos_por_venta": "Ingresos por Venta",
        "costo_de_ventas": "Costo de Ventas",
        # ...
    }
```

## Nodos de Extracción

### Balance: `n3_extract_balance.py`

```python
async def extract_balance_llm(state: DocumentProcessingState):
    # 1. Configurar LLM con BalanceDataForLLM
    model = ChatGoogleGenerativeAI(...).with_structured_output(BalanceDataForLLM)

    # 2. Extraer
    extracted_balance_llm = await model.ainvoke(prompt)

    # 3. Post-procesar (agregar 'concepto')
    for item_llm in extracted_balance_llm.resultados_principales:
        concepto_label = tenant_config.balance_fields.get(item_llm.concepto_code)
        # ... crear BalanceItem completo

    # 4. Crear BalanceData completo
    extracted_balance = BalanceData(...)
```

### Income: `n3_extract_income.py`

Idéntico a balance, usando `IncomeStatementDataForLLM` y `tenant_config.income_fields`.

## Debugging

### Verificar que LLM no extrae 'concepto'

```python
extracted_balance_llm = await model.ainvoke(prompt)
# ✅ Esto NO debe tener 'concepto'
print(extracted_balance_llm.resultados_principales[0])
# Output: BalanceItemForLLM(concepto_code='activo_total', monto_actual=1000, monto_anterior=900)
```

### Verificar post-procesamiento

```python
for item_llm in extracted_balance_llm.resultados_principales:
    concepto_label = tenant_config.balance_fields.get(item_llm.concepto_code)
    print(f"✅ {item_llm.concepto_code} → '{concepto_label}'")
```

### Verificar almacenamiento

```python
# ✅ Esto DEBE tener 'concepto' de tenant_config
print(extracted_balance.resultados_principales[0])
# Output: BalanceItem(concepto_code='activo_total', concepto='Total Activo', ...)
```

## Errores Comunes

### ❌ Usar modelo completo para LLM

```python
# ❌ MAL - LLM reescribirá 'concepto'
model.with_structured_output(BalanceData)
```

```python
# ✅ BIEN - LLM no puede tocar 'concepto'
model.with_structured_output(BalanceDataForLLM)
```

### ❌ Olvidar post-procesamiento

```python
# ❌ MAL - Faltan campos 'concepto'
extracted_balance = BalanceData(
    resultados_principales=extracted_balance_llm.resultados_principales  # Items sin 'concepto'
)
```

```python
# ✅ BIEN - Agregar 'concepto' antes
resultados_completos = [
    BalanceItem(
        concepto_code=item.concepto_code,
        concepto=tenant_config.balance_fields.get(item.concepto_code),  # ← Agregar
        monto_actual=item.monto_actual,
        monto_anterior=item.monto_anterior
    )
    for item in extracted_balance_llm.resultados_principales
]
extracted_balance = BalanceData(resultados_principales=resultados_completos)
```

### ❌ Hardcodear etiquetas

```python
# ❌ MAL - No usa tenant_config
concepto = "Total Activo"  # hardcoded
```

```python
# ✅ BIEN - Desde tenant_config
concepto = tenant_config.balance_fields.get("activo_total")
```

## Testing

### Test unitario de post-procesamiento

```python
def test_balance_post_processing():
    # Mock tenant config
    tenant_config = TenantConfig(
        balance_fields={"activo_total": "Total Activo"}
    )

    # Mock LLM extraction
    item_llm = BalanceItemForLLM(
        concepto_code="activo_total",
        monto_actual=1000,
        monto_anterior=900
    )

    # Post-procesamiento
    concepto_label = tenant_config.balance_fields.get(item_llm.concepto_code)
    item_completo = BalanceItem(
        concepto_code=item_llm.concepto_code,
        concepto=concepto_label,
        monto_actual=item_llm.monto_actual,
        monto_anterior=item_llm.monto_anterior
    )

    # Verificar
    assert item_completo.concepto == "Total Activo"
    assert item_completo.concepto_code == "activo_total"
```

## Checklist para Nuevos Nodos de Extracción

Cuando crees un nuevo nodo que extrae datos financieros:

- [ ] Usar `*ForLLM` models para `.with_structured_output()`
- [ ] Post-procesar para agregar campos faltantes desde `tenant_config`
- [ ] Crear modelo completo antes de guardar en MongoDB
- [ ] Liberar `*_llm` variables con `del` después de post-procesar
- [ ] Agregar logs: `logger.info(f"Post-processing: {code} → '{label}'")`
- [ ] Test: verificar que campos vienen de `tenant_config`

## Más Información

- Documentación completa: `/Docs/LLM_FIELD_CONSISTENCY_FIX.md`
- PRP Tenants: `/PRPs/PRP_TENANTS.md`
- Tenant Config: `/app/services/tenant_config.py`

---

**Última actualización:** 2025-01-XX
