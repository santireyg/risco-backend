# Solución: Consistencia del Campo 'concepto' con Configuración de Tenant

## Problema Identificado

Al extraer datos financieros con el LLM (Gemini 2.5 Flash), el modelo sobrescribía el campo `concepto` con sus propias interpretaciones en lugar de respetar los valores exactos definidos en la configuración del tenant.

**Comportamiento observado:**

- LLM recibía: `concepto_code: "ingresos_por_venta"`, `concepto: "Ingresos por Venta"`
- LLM devolvía: `concepto_code: "ingresos_por_venta"` ✅, `concepto: "Ventas"` ❌

**Causa raíz:** Aunque usamos `.with_structured_output()`, el LLM tiene libertad para "mejorar" campos de texto opcionales, interpretando y reformulando las etiquetas según su conocimiento.

## Solución Implementada: Modelos Simplificados para LLM

### Estrategia

Aplicamos el patrón de **modelos separados** para extracción y almacenamiento:

1. **LLM extrae** → Modelos simplificados sin campo `concepto` (`*ForLLM`)
2. **Post-procesamiento** → Agrega `concepto` desde `tenant_config`
3. **Almacenamiento** → Modelos completos con `concepto` (`BalanceData`, `IncomeStatementData`)

### Ventajas

✅ **100% consistencia** - El LLM no puede modificar lo que no extrae
✅ **Tenant config como fuente única de verdad** - `concepto` siempre proviene de configuración
✅ **Sin cambios en base de datos** - Estructura final permanece igual
✅ **KISS (Keep It Simple, Stupid)** - Solución directa y mantenible

## Cambios Implementados

### 1. Modelos Simplificados para LLM

#### `/app/models/docs_balance.py`

```python
class BalanceItemForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM (sin campo 'concepto').

    El LLM solo extrae concepto_code y montos. El campo 'concepto' se agrega
    en post-procesamiento desde la configuración del tenant.
    """
    concepto_code: str = Field(..., description="Identificador del concepto contable")
    monto_actual: float = Field(..., description="Monto del período actual")
    monto_anterior: float = Field(..., description="Monto del período anterior")
    # ⚠️ NO incluye campo 'concepto' - se agrega después


class BalanceDataForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM (resultados principales sin campo 'concepto').
    """
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[BalanceItemForLLM]  # Items sin 'concepto'
    detalles_activo: List[SheetItem]
    detalles_pasivo: List[SheetItem]
    detalles_patrimonio_neto: List[SheetItem]
```

#### `/app/models/docs_income.py`

```python
class IncomeStatementItemForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM (sin campo 'concepto').
    """
    concepto_code: str = Field(..., description="Identificador del concepto contable")
    monto_actual: float = Field(..., description="Monto del período actual")
    monto_anterior: float = Field(..., description="Monto del período anterior")
    # ⚠️ NO incluye campo 'concepto' - se agrega después


class IncomeStatementDataForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM.
    """
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[IncomeStatementItemForLLM]  # Items sin 'concepto'
    detalles_estado_resultados: List[SheetItem]
```

### 2. Extracción y Post-procesamiento

#### `/app/services/graph_nodes/n3_extract_balance.py`

```python
async def extract_balance_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    # ... configuración tenant y páginas ...

    from app.models.docs_balance import create_balance_data_model, BalanceDataForLLM, BalanceItem

    # Usar modelo simplificado para LLM
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        max_tokens=13000,
        max_retries=1
    ).with_structured_output(BalanceDataForLLM)  # ← Modelo sin 'concepto'

    # ... preparar prompt con imágenes ...

    # Extracción del LLM (sin campo 'concepto')
    extracted_balance_llm = await model.ainvoke(prompt)

    # 🔧 POST-PROCESAMIENTO: Agregar campo 'concepto' desde tenant_config
    resultados_principales_completos = []
    for item_llm in extracted_balance_llm.resultados_principales:
        # Obtener etiqueta exacta desde configuración del tenant
        concepto_label = tenant_config.balance_fields.get(
            item_llm.concepto_code,
            item_llm.concepto_code  # fallback si no existe
        )

        # Crear item completo con 'concepto' de tenant_config
        item_completo = BalanceItem(
            concepto_code=item_llm.concepto_code,
            concepto=concepto_label,  # ← De tenant_config, no del LLM
            monto_actual=item_llm.monto_actual,
            monto_anterior=item_llm.monto_anterior
        )
        resultados_principales_completos.append(item_completo)

    # Crear modelo completo para almacenar
    extracted_balance = BalanceData(
        informacion_general=extracted_balance_llm.informacion_general,
        resultados_principales=resultados_principales_completos,
        detalles_activo=extracted_balance_llm.detalles_activo,
        detalles_pasivo=extracted_balance_llm.detalles_pasivo,
        detalles_patrimonio_neto=extracted_balance_llm.detalles_patrimonio_neto
    )

    # ... continuar con actualización de estado ...
```

#### `/app/services/graph_nodes/n3_extract_income.py`

Implementación idéntica para estado de resultados:

```python
async def extract_income_llm(state: DocumentProcessingState) -> DocumentProcessingState:
    from app.models.docs_income import create_income_data_model, IncomeStatementDataForLLM, IncomeStatementItem

    # Usar modelo simplificado
    model = ChatGoogleGenerativeAI(...).with_structured_output(IncomeStatementDataForLLM)

    extracted_income_llm = await model.ainvoke(prompt)

    # POST-PROCESAMIENTO: Agregar 'concepto' desde tenant_config
    resultados_principales_completos = []
    for item_llm in extracted_income_llm.resultados_principales:
        concepto_label = tenant_config.income_fields.get(item_llm.concepto_code, item_llm.concepto_code)

        item_completo = IncomeStatementItem(
            concepto_code=item_llm.concepto_code,
            concepto=concepto_label,  # ← De tenant_config
            monto_actual=item_llm.monto_actual,
            monto_anterior=item_llm.monto_anterior
        )
        resultados_principales_completos.append(item_completo)

    extracted_income = IncomeStatementData(
        informacion_general=extracted_income_llm.informacion_general,
        resultados_principales=resultados_principales_completos,
        detalles_estado_resultados=extracted_income_llm.detalles_estado_resultados
    )
```

## Flujo Completo

```
┌─────────────────┐
│   Tenant Config │
│                 │
│ balance_fields: │
│   "activo_tot": │
│     "Total      │
│      Activo"    │
└────────┬────────┘
         │
         │ (config se carga)
         ▼
┌─────────────────┐
│  LLM Extraction │
│                 │
│ → Gemini recibe │
│   imágenes      │
│ → Extrae solo:  │
│   * concepto_   │
│     code        │
│   * monto_      │
│     actual      │
│   * monto_      │
│     anterior    │
│                 │
│ ❌ NO extrae    │
│    'concepto'   │
└────────┬────────┘
         │
         │ (BalanceDataForLLM)
         ▼
┌─────────────────┐
│ Post-Processing │
│                 │
│ for item in llm │
│   concepto =    │
│     config.get( │
│       concepto_ │
│       code)     │
│                 │
│ ✅ Agrega       │
│    'concepto'   │
│    exacto de    │
│    config       │
└────────┬────────┘
         │
         │ (BalanceData completo)
         ▼
┌─────────────────┐
│    MongoDB      │
│                 │
│ balance_data: { │
│   resultados_   │
│   principales:[ │
│     {           │
│       concepto_ │
│       code: "..." │
│       concepto: │
│         "..." ✅ │
│     }           │
│   ]             │
│ }               │
└─────────────────┘
```

## Configuración de Tenant

La fuente única de verdad para las etiquetas está en `/app/services/tenant_config.py`:

```python
class TenantConfig:
    balance_fields: Dict[str, str] = {
        "activo_total": "Total Activo",
        "pasivo_total": "Total Pasivo",
        "patrimonio_neto": "Patrimonio Neto",
        # ... más campos ...
    }

    income_fields: Dict[str, str] = {
        "ingresos_por_venta": "Ingresos por Venta",
        "costo_de_ventas": "Costo de Ventas",
        "resultado_bruto": "Resultado Bruto",
        # ... más campos ...
    }
```

## Casos de Uso

### 1. Campo existe en tenant_config

```python
# Tenant config
balance_fields = {"activo_total": "Total Activo"}

# LLM extrae
{concepto_code: "activo_total", monto_actual: 1000, monto_anterior: 900}

# Post-procesamiento
concepto_label = tenant_config.balance_fields.get("activo_total")  # "Total Activo"

# Resultado final
{concepto_code: "activo_total", concepto: "Total Activo", monto_actual: 1000, monto_anterior: 900}
```

### 2. Campo NO existe en tenant_config (fallback)

```python
# Tenant config no tiene "activo_no_corriente"

# LLM extrae
{concepto_code: "activo_no_corriente", monto_actual: 500, monto_anterior: 450}

# Post-procesamiento con fallback
concepto_label = tenant_config.balance_fields.get("activo_no_corriente", "activo_no_corriente")

# Resultado final
{concepto_code: "activo_no_corriente", concepto: "activo_no_corriente", monto_actual: 500, monto_anterior: 450}
```

## Validación

### ✅ Tests de Consistencia

1. **Test de extracción**: Verificar que `BalanceDataForLLM` NO tiene campo `concepto` en `resultados_principales`
2. **Test de post-procesamiento**: Verificar que todos los `BalanceItem` finales tienen `concepto` de `tenant_config`
3. **Test de almacenamiento**: Verificar que MongoDB guarda estructura completa con `concepto`

### ✅ Logs de Verificación

Agregar logs en post-procesamiento:

```python
logger.info(f"Post-processing: {item_llm.concepto_code} → '{concepto_label}' (from tenant_config)")
```

## Beneficios de la Solución

| Aspecto            | Antes                      | Después                    |
| ------------------ | -------------------------- | -------------------------- |
| **Consistencia**   | ❌ LLM podía modificar     | ✅ 100% desde config       |
| **Mantenibilidad** | ⚠️ Prompts complejos       | ✅ Código simple y directo |
| **Debugging**      | ❌ Difícil rastrear origen | ✅ Claro: config → DB      |
| **Multi-tenant**   | ⚠️ Variaciones por LLM     | ✅ Config por tenant       |
| **Performance**    | ➡️ Igual                   | ➡️ Igual (sin overhead)    |

## Archivos Modificados

1. `/app/models/docs_balance.py` - Agregado `BalanceItemForLLM` y `BalanceDataForLLM`
2. `/app/models/docs_income.py` - Agregado `IncomeStatementItemForLLM` y `IncomeStatementDataForLLM`
3. `/app/services/graph_nodes/n3_extract_balance.py` - Post-procesamiento de balance
4. `/app/services/graph_nodes/n3_extract_income.py` - Post-procesamiento de income

## Próximos Pasos

1. ✅ Modelos simplificados creados
2. ✅ Extracción con post-procesamiento implementada
3. ⏳ Testing con documentos reales
4. ⏳ Validación de consistencia en base de datos
5. ⏳ Logs de verificación en producción

## Referencias

- PRP: `/PRPs/PRP_TENANTS.md` - Arquitectura multi-tenant
- Refactoring v2: `/Docs/FINANCIAL_DATA_REFACTORING.md` - Cambios estructurales
- Tenant config: `/app/services/tenant_config.py` - Configuración por tenant

---

**Autor:** Implementado el 2025-01-XX
**Versión:** 1.0
**Estado:** ✅ Implementado y listo para testing
