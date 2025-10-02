# Product Requirements Prompt (PRP) - Exportación a Excel

## Contexto del Sistema

### Arquitectura General

La API de Risco es un sistema de análisis automatizado de estados financieros construido con **FastAPI** y **LangGraph** que procesa documentos PDF de balances contables mediante IA. El sistema extrae y estructura datos financieros que se almacenan en MongoDB y ahora necesita ofrecer capacidades de exportación a formato Excel.

### Estructura del Codebase Relevante

```
risco-backend/
├── app/
│   ├── main.py                          # Aplicación FastAPI principal
│   ├── api/
│   │   └── endpoints/
│   │       ├── crud.py                  # Endpoints CRUD de documentos
│   │       ├── export.py                # [NUEVO] Endpoint de exportación
│   │       └── ...
│   │
│   ├── core/
│   │   ├── auth.py                      # JWT, get_current_user()
│   │   ├── database.py                  # docs_collection (MongoDB)
│   │   └── ...
│   │
│   ├── models/
│   │   ├── docs.py                      # DocFile (documento principal)
│   │   ├── docs_balance.py              # BalanceData
│   │   ├── docs_income.py               # IncomeStatementData
│   │   ├── docs_company_info.py         # CompanyInfo
│   │   └── docs_financial_items.py      # SheetItem
│   │
│   └── services/
│       ├── download_service.py          # Servicio de descarga de archivos
│       └── export_xlsx.py               # [NUEVO] Servicio de exportación Excel
│
└── requirements.txt
```

### Modelos de Datos Relevantes

#### DocFile (app/models/docs.py)

```python
class DocFile(BaseModel):
    name: str
    status: str
    uploaded_by: str
    balance_data: Optional[Dict[str, Any]]  # Estructura dinámica por tenant
    income_statement_data: Optional[Dict[str, Any]]  # Estructura dinámica por tenant
    company_info: Optional["CompanyInfo"]
    tenant_id: str
```

#### CompanyInfo (app/models/docs_company_info.py)

```python
class CompanyInfo(BaseModel):
    company_cuit: Optional[str]  # 11 dígitos
    company_name: str
    company_activity: str | None
    company_address: str | None
```

#### BalanceData (app/models/docs_balance.py)

```python
class BalanceDataBase(BaseModel):
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[BalanceItem]
    detalles_activo: List[SheetItem]
    detalles_pasivo: List[SheetItem]
    detalles_patrimonio_neto: List[SheetItem]
```

#### IncomeStatementData (app/models/docs_income.py)

```python
class IncomeStatementDataBase(BaseModel):
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[IncomeStatementItem]
    detalles_estado_resultados: List[SheetItem]
```

#### SheetItem (app/models/docs_financial_items.py)

```python
class SheetItem(BaseModel):
    concepto: str
    monto_actual: float
    monto_anterior: float
```

#### DocumentGeneralInformation (app/models/docs_financial_items.py)

```python
class DocumentGeneralInformation(BaseModel):
    empresa: str
    periodo_actual: datetime
    periodo_anterior: Optional[datetime]
```

### Patrones de Endpoints Existentes

Los endpoints en `app/api/endpoints/` siguen estos patrones:

- Autenticación vía `get_current_user()` (JWT en cookies)
- Validación de `ObjectId` de MongoDB
- Filtrado por `tenant_id` del usuario actual
- Rate limiting con `@limiter.limit()`
- Manejo de errores con `HTTPException`
- Responses con JSONResponse o modelos Pydantic

Ejemplo de endpoint similar (`/document/{docfile_id}/download` en `crud.py`):

```python
@router.get("/document/{docfile_id}/download")
@limiter.limit("10/minute")
async def download_document_pdf(
    docfile_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    # Validación de ObjectId
    # Verificación de pertenencia al tenant
    # Generación de URL/archivo
    # Manejo de errores
```

## Objetivo

Implementar un sistema de exportación de datos financieros a formato Excel (.xlsx) que permita a los usuarios descargar la información estructurada de un documento procesado en un formato profesional y listo para análisis.

## Requerimientos Funcionales

### 1. Nuevo Endpoint REST

**Ruta**: `GET /export_xlsx/{docfile_id}`

**Ubicación**: `app/api/endpoints/export.py` (nuevo archivo)

**Router**: Debe incluirse en `app/main.py` como:

```python
from app.api.endpoints import export
app.include_router(export.router, tags=["export"])
```

**Características**:

- Autenticación obligatoria mediante `get_current_user()`
- Rate limiting: `@limiter.limit("10/minute")`
- Validación de `ObjectId` y pertenencia al tenant del usuario
- Respuesta: Archivo Excel descargable (tipo MIME: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)
- Nombre del archivo: `{company_name}_{periodo_actual}.xlsx` (sanitizado para filesystem)

**Validaciones**:

- Documento debe existir en MongoDB
- Documento debe pertenecer al tenant del usuario actual
- Documento debe tener `status == "Analizado"` o `status == "Exportado"` (documentos viejos pueden tener estatus "Exportado", que indica que fueron exportados a un sistema externo, independiente del sistema de exportación actual)
- Documento **debe tener** `company_info` (no puede ser `None`)
- Documento debe tener datos financieros disponibles (`balance_data` y/o `income_statement_data`)

**Manejo de Errores**:

- 400: ID de documento inválido
- 403: Documento no pertenece al tenant del usuario
- 404: Documento no encontrado
- 422: Documento con status inválido, sin company_info, o sin datos financieros para exportar
- 500: Error interno al generar el archivo Excel

### 2. Servicio de Exportación

**Archivo**: `app/services/export_xlsx.py`

**Función Principal**: `generate_excel_export(docfile_id: str, current_user: User) -> bytes`

**Responsabilidades**:

- Obtener documento de MongoDB por `docfile_id`
- Validar existencia de datos requeridos
- Crear archivo Excel en memoria usando `openpyxl`
- Generar 3 hojas de cálculo
- Aplicar formato profesional
- Retornar archivo como bytes

**Dependencias**:

- `openpyxl`: Manipulación de archivos Excel
- `app.core.database`: Acceso a `docs_collection`
- `app.models.users`: Modelo `User`

### 3. Estructura del Archivo Excel

El archivo debe contener **3 hojas**:

#### 3.1. Hoja "Situación Patrimonial"

**Estructura**:

1. **Encabezado (filas 1-5)**: Información general en formato clave-valor (columna A: etiqueta, columna B: valor)

   - CUIT: `company_info.company_cuit`
   - Razón social: `company_info.company_name`
   - Período actual: `balance_data.informacion_general.periodo_actual` (formato: "DD/MM/YYYY")
   - Período anterior: `balance_data.informacion_general.periodo_anterior` (formato: "DD/MM/YYYY")
   - Fecha y hora exportación: Timestamp actual (formato: "DD/MM/YYYY HH:MM")

2. **Separación**: 2 filas vacías

3. **Tabla 1 - Activo** (fila 8 en adelante):

   - Título: "Activo" (fila 7, columna A, en negrita)
   - Columnas: Concepto | Actual | Anterior
   - Datos: `balance_data.detalles_activo[]`
   - Mapeo: `concepto` → Concepto, `monto_actual` → Actual, `monto_anterior` → Anterior

4. **Separación**: 2 filas vacías

5. **Tabla 2 - Pasivo**:

   - Título: "Pasivo" (en negrita)
   - Columnas: Concepto | Actual | Anterior
   - Datos: `balance_data.detalles_pasivo[]`
   - Mapeo: igual que Activo

6. **Separación**: 2 filas vacías

7. **Tabla 3 - Patrimonio Neto**:
   - Título: "Patrimonio Neto" (en negrita)
   - Columnas: Concepto | Actual | Anterior
   - Datos: `balance_data.detalles_patrimonio_neto[]`
   - Mapeo: igual que Activo

#### 3.2. Hoja "Estado Resultados"

**Estructura**:

1. **Encabezado (filas 1-5)**: Misma información general que en "Situación Patrimonial"

2. **Separación**: 2 filas vacías

3. **Tabla - Estado de Resultados** (fila 8 en adelante):
   - Título: "Estado de Resultados" (fila 7, columna A, en negrita)
   - Columnas: Concepto | Actual | Anterior
   - Datos: `income_statement_data.detalles_estado_resultados[]`
   - Mapeo: `concepto` → Concepto, `monto_actual` → Actual, `monto_anterior` → Anterior

#### 3.3. Hoja "Cuentas Principales"

**Estructura**:

1. **Encabezado (filas 1-5)**: Misma información general que las demás hojas

2. **Separación**: 2 filas vacías

3. **Tabla - Cuentas Principales** (fila 8 en adelante):
   - Título: "Cuentas Principales" (fila 7, columna A, en negrita)
   - Columnas: Concepto | Actual | Anterior
   - Datos:
     - `balance_data.resultados_principales[]` (primero)
     - `income_statement_data.resultados_principales[]` (inmediatamente después, sin filas vacías)
   - Mapeo:
     - Para items con `concepto`: usar ese valor
     - Para items con `concepto_code` sin `concepto`: buscar etiqueta en tenant config o usar el código

### 4. Formato y Estilo

#### 4.1. Formato Numérico

**Columnas "Actual" y "Anterior"**:

- Tipo: Contabilidad
- Formato: `#,##0.00;[Red](#,##0.00)` (separador de miles, 2 decimales, negativos en rojo y entre paréntesis)
- Alineación: Derecha
- **Valores cero (0)**: Dejar la celda vacía en lugar de mostrar "0.00"
- Ejemplo: `1234567.89` → `1,234,567.89`
- Ejemplo negativo: `-5000` → `(5,000.00)` en rojo
- Ejemplo cero: `0` → celda vacía

#### 4.2. Formato de Fechas

**Períodos** (en encabezado):

- Formato: `DD/MM/YYYY`
- Ejemplo: `datetime(2024, 3, 31)` → `"31/03/2024"`

**Fecha y hora exportación**:

- Formato: `DD/MM/YYYY HH:MM`
- Ejemplo: `"01/10/2025 14:30"`

#### 4.3. Estilo de Tablas

**Encabezados de columnas** (Concepto | Actual | Anterior):

- Fuente: Arial 11pt, Negrita
- Fondo: Color corporativo suave (ej: RGB 79, 129, 189 - azul corporativo)
- Texto: Blanco
- Alineación: Centrado
- Bordes: Todos los bordes con línea media

**Filas de datos**:

- Fuente: Arial 10pt
- Fondo: Alternado (blanco / gris muy claro RGB 242, 242, 242)
- Bordes: Líneas delgadas en todos los lados
- Altura de fila: Auto

**Títulos de tablas** ("Activo", "Pasivo", etc.):

- Fuente: Arial 12pt, Negrita
- Color: Azul oscuro (RGB 31, 73, 125)
- Sin bordes

**Encabezado de información general**:

- Etiquetas (columna A): Arial 10pt, Negrita
- Valores (columna B): Arial 10pt, Normal
- Sin bordes

#### 4.4. Ancho de Columnas

- Columna A (Concepto): 40 caracteres
- Columna B (Actual): 15 caracteres
- Columna C (Anterior): 15 caracteres

#### 4.5. Configuración de Hoja

**Todas las hojas**:

- Líneas de cuadrícula: **Desactivadas** (`sheet.sheet_view.showGridLines = False`)
- Orientación: Vertical (Portrait)
- Márgenes: Normales (2.54 cm)
- Zoom: 100%

### 5. Manejo de Casos Especiales

#### 5.1. Datos Faltantes

**Si `balance_data` es `None` o vacío**:

- No crear la hoja "Situación Patrimonial"
- Continuar con las demás hojas si tienen datos

**Si `income_statement_data` es `None` o vacío**:

- No crear la hoja "Estado Resultados"
- Continuar con las demás hojas si tienen datos

**Si ambos son `None`**:

- Retornar error 422: "El documento no tiene datos financieros para exportar"

**Si `company_info` es `None`**:

- Retornar error 422: "El documento debe tener información de la empresa para exportar"

**Si faltan campos en `company_info`**:

- CUIT faltante: mostrar "No disponible"
- Otros campos: dejar celda vacía

**Si `periodo_anterior` es `None`**:

- Mostrar "No disponible" en el encabezado
- Columna "Anterior" en tablas puede quedar vacía o con guiones

#### 5.2. Listas Vacías

**Si `detalles_activo`, `detalles_pasivo`, etc. están vacíos**:

- Crear la tabla con solo el encabezado (sin filas de datos)
- Agregar una fila con mensaje: "Sin datos disponibles" en columna Concepto

#### 5.3. Nombres de Archivo

**Sanitización**:

- Remover caracteres no válidos para filesystem: `/ \ : * ? " < > |`
- Reemplazar espacios por guiones bajos
- Limitar longitud a 100 caracteres
- Si no hay `company_name`: usar `"documento_{docfile_id}"`
- Si no hay `periodo_actual`: usar fecha actual

**Ejemplo**: `"ACME S.A. - 31/03/2024.xlsx"` → `"ACME_S.A._-_31_03_2024.xlsx"`

#### 5.4. Valores Cero en Tablas

**Cuando `monto_actual` o `monto_anterior` es 0**:

- No mostrar "0.00" en la celda
- Dejar la celda completamente vacía
- Mantener el formato de la celda (bordes, fondo alternado)
- Esto aplica a todas las tablas en todas las hojas

### 6. Dependencias Técnicas

**Librería requerida**: `openpyxl`

Agregar a `requirements.txt`:

```
openpyxl
```

**Imports necesarios en `export_xlsx.py`**:

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from app.core.database import docs_collection
from app.models.users import User
import re
```

## Requerimientos No Funcionales

### Performance

- Generación de archivo Excel en **< 3 segundos** para documentos con hasta 200 filas de datos
- Uso de memoria eficiente (generar archivo en memoria, no en disco), luego haz una limpieza y liberación de la memoria
- No bloquear el event loop de FastAPI (usar operaciones async donde corresponda)

### Seguridad

- **Aislamiento por tenant**: Solo exportar documentos del tenant del usuario autenticado
- **Autenticación obligatoria**: Endpoint protegido con JWT
- **Validación de entrada**: Validar formato de `docfile_id` antes de consultar BD
- **Rate limiting**: Máximo 10 exportaciones por minuto por usuario

### Mantenibilidad

- **Código modular**: Separar lógica de generación de Excel del endpoint
- **Constantes**: Definir colores, fuentes y formatos como constantes al inicio del archivo
- **Logging**: Registrar eventos importantes (errores, éxito)
- **Documentación**: Docstrings completos en funciones principales

## Casos de Uso

### Caso de Uso 1: Exportación Exitosa Completa

**Precondiciones**:

- Usuario autenticado
- Documento con `status == "Analizado"` o `status == "Exportado"`
- Documento tiene `balance_data` y `income_statement_data` completos
- Documento tiene `company_info`

**Flujo**:

1. Usuario solicita `GET /export_xlsx/{docfile_id}`
2. Sistema valida autenticación y pertenencia al tenant
3. Sistema verifica estado del documento
4. Sistema genera archivo Excel con 3 hojas
5. Sistema retorna archivo con nombre apropiado

**Resultado**: Usuario recibe archivo Excel completo y bien formateado

### Caso de Uso 2: Exportación Parcial (Solo Balance)

**Precondiciones**:

- Usuario autenticado
- Documento solo tiene `balance_data` (sin `income_statement_data`)

**Flujo**:

1. Usuario solicita exportación
2. Sistema genera archivo Excel con 2 hojas: "Situación Patrimonial" y "Cuentas Principales"
3. No se incluye "Estado Resultados"

**Resultado**: Usuario recibe archivo Excel parcial pero válido

### Caso de Uso 3: Documento Sin Datos

**Precondiciones**:

- Documento sin `balance_data` ni `income_statement_data`

**Flujo**:

1. Usuario solicita exportación
2. Sistema detecta ausencia de datos
3. Sistema retorna error 422

**Resultado**: Usuario recibe mensaje claro de error

### Caso de Uso 4: Documento en Proceso o Sin Company Info

**Precondiciones**:

- Documento con `status == "En proceso"` o `"Error"`, o sin `company_info`

**Flujo**:

1. Usuario solicita exportación
2. Sistema valida estado del documento y presencia de company_info
3. Sistema retorna error 422 con mensaje apropiado

**Resultado**: Usuario entiende que debe esperar a que termine el procesamiento o que faltan datos necesarios

## Plan de Implementación

### Fase 1: Configuración Inicial

1. Agregar `openpyxl` a `requirements.txt`
2. Crear archivo `app/services/export_xlsx.py` con imports básicos
3. Definir constantes de estilo (colores, fuentes, formatos)

### Fase 2: Función de Generación de Excel

1. Implementar `generate_excel_export()` con estructura básica
2. Implementar función auxiliar para crear encabezado de información general
3. Implementar función auxiliar para crear tabla genérica con formato
4. Implementar generación de hoja "Situación Patrimonial"
5. Implementar generación de hoja "Estado Resultados"
6. Implementar generación de hoja "Cuentas Principales"

### Fase 3: Endpoint REST

1. Crear archivo `app/api/endpoints/export.py` con el router
2. Implementar endpoint `GET /export_xlsx/{docfile_id}`
3. Implementar validaciones (ObjectId, tenant, status, company_info, datos)
4. Integrar con `generate_excel_export()`
5. Configurar respuesta con tipo MIME correcto
6. Implementar generación de nombre de archivo sanitizado
7. Agregar el router en `app/main.py`

### Fase 4: Refinamiento

1. Aplicar todos los estilos y formatos especificados
2. Implementar manejo de valores cero (celdas vacías)
3. Implementar manejo de otros casos especiales
4. Agregar logging apropiado (éxito y errores)
5. Optimizar performance

## Criterios de Aceptación

- [ ] Endpoint `GET /export_xlsx/{docfile_id}` funciona correctamente en `app/api/endpoints/export.py`
- [ ] Router incluido correctamente en `app/main.py`
- [ ] Archivo Excel se genera con 3 hojas cuando hay datos completos
- [ ] Formato numérico de contabilidad aplicado correctamente (negativos en rojo entre paréntesis)
- [ ] Valores cero (0) se muestran como celdas vacías en todas las columnas numéricas
- [ ] Fechas formateadas como especificado (DD/MM/YYYY, DD/MM/YYYY HH:MM)
- [ ] Encabezados de tablas con estilo profesional (fondo azul, texto blanco)
- [ ] Filas alternadas con colores de fondo
- [ ] Líneas de cuadrícula desactivadas en todas las hojas
- [ ] Anchos de columna apropiados
- [ ] Validación de tenant funciona correctamente
- [ ] Validación de status (Analizado o Exportado) funciona correctamente
- [ ] Validación de company_info obligatorio funciona correctamente
- [ ] Manejo de casos especiales implementado (datos faltantes, listas vacías)
- [ ] Errores retornan códigos HTTP apropiados con mensajes claros
- [ ] Rate limiting de 10 requests/minuto activo
- [ ] Nombre de archivo sanitizado correctamente
- [ ] Performance < 3 segundos para documentos típicos
- [ ] Logging implementado para eventos importantes (éxito y errores, sin logging de inicio)

## Notas de Implementación

### Consideraciones de openpyxl

**Creación de Workbook**:

```python
wb = Workbook()
# Primera hoja ya existe (wb.active)
ws1 = wb.active
ws1.title = "Situación Patrimonial"
# Crear hojas adicionales
ws2 = wb.create_sheet("Estado Resultados")
ws3 = wb.create_sheet("Cuentas Principales")
```

**Aplicar formato a celda**:

```python
cell = ws['A1']
cell.font = Font(name='Arial', size=11, bold=True)
cell.fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
cell.alignment = Alignment(horizontal='center', vertical='center')
```

**Desactivar líneas de cuadrícula**:

```python
ws.sheet_view.showGridLines = False
```

**Formato de número contabilidad**:

```python
# Para valores distintos de cero
if valor != 0:
    cell.value = valor
    cell.number_format = '#,##0.00;[Red](#,##0.00)'
else:
    cell.value = None  # Celda vacía para valores cero
```

**Guardar en memoria**:

```python
from io import BytesIO
buffer = BytesIO()
wb.save(buffer)
buffer.seek(0)
return buffer.getvalue()  # bytes
```

### Response del Endpoint

```python
from fastapi.responses import Response

@router.get("/export_xlsx/{docfile_id}")
async def export_xlsx(docfile_id: str, current_user: User = Depends(get_current_user)):
    # ... validaciones ...

    excel_bytes = await generate_excel_export(docfile_id, current_user)
    filename = generate_filename(document)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
```

### Inclusión del Router en main.py

El nuevo endpoint debe incluirse en `app/main.py` junto con los demás routers:

```python
# En app/main.py

# Importar routers de la carpeta de endpoints
from app.api.endpoints import auth, processing, crud, websocket, user_registration, user_management, export

# ... código existente ...

# Incluir los routers de los endpoints
app.include_router(auth.router, tags=["auth"])
app.include_router(user_registration.router, prefix="/user-registration", tags=["user-registration"])
app.include_router(user_management.router, prefix="/admin", tags=["user-management"])
app.include_router(processing.router, tags=["processing"])
app.include_router(crud.router, tags=["CRUD"])
app.include_router(websocket.router, tags=["Websocket"])
app.include_router(export.router, tags=["export"])  # NUEVO
```

### Logging Recomendado

```python
import logging
logger = logging.getLogger(__name__)

# En caso de éxito
logger.info(f"Exportación Excel completada para documento {docfile_id}, tamaño: {len(excel_bytes)} bytes")

# En caso de error
logger.error(f"Error al exportar documento {docfile_id}: {str(e)}")
```

## Referencias

- Documentación de openpyxl: https://openpyxl.readthedocs.io/
- FastAPI Response: https://fastapi.tiangolo.com/advanced/custom-response/
- Formato de número Excel: https://support.microsoft.com/es-es/office/formato-de-números
