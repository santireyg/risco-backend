# app/models/docs_income.py
"""
Modelos base para datos de Estado de Resultados (Income Statement).

Estos modelos sirven como plantillas base para crear versiones dinámicas
específicas de cada tenant en runtime.
"""

from typing import List, Type, Optional
from pydantic import BaseModel, Field, RootModel, create_model

from app.models.docs_financial_items import DocumentGeneralInformation, SheetItem


class IncomeStatementItem(BaseModel):
    """
    Representa un ítem individual del estado de resultados con sus valores actual y anterior.
    
    Attributes:
        concepto_code: Identificador del concepto (ej: 'ingresos_por_venta')
        concepto: Nombre legible del concepto (ej: 'Ingresos por venta') - Opcional
        monto_actual: Valor del período actual
        monto_anterior: Valor del período anterior
    """
    concepto_code: str = Field(..., description="Identificador del concepto contable")
    concepto: Optional[str] = Field(None, description="Etiqueta legible del concepto")
    monto_actual: float = Field(..., description="Monto del período actual")
    monto_anterior: float = Field(..., description="Monto del período anterior")


class IncomeStatementItemForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM (sin campo 'concepto').
    
    El LLM solo extrae concepto_code y montos. El campo 'concepto' se agrega
    en post-procesamiento desde la configuración del tenant.
    """
    concepto_code: str = Field(..., description="Identificador del concepto contable")
    monto_actual: float = Field(..., description="Monto del período actual")
    monto_anterior: float = Field(..., description="Monto del período anterior")


# Tipo alias para lista de IncomeStatementItem (resultados principales es directamente una lista)
IncomeStatementMainResultsBase = List[IncomeStatementItem]


class IncomeStatementDataBase(BaseModel):
    """
    Modelo base para datos completos del Estado de Resultados.
    
    Este modelo define la estructura general que siempre se mantiene.
    """
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[IncomeStatementItem] = Field(..., description="Lista de ítems principales del estado de resultados")
    detalles_estado_resultados: List[SheetItem]


class IncomeStatementDataForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM (resultados principales sin campo 'concepto').
    
    El LLM extrae solo concepto_code y montos para los resultados principales.
    El campo 'concepto' se agrega en post-procesamiento desde la configuración del tenant.
    """
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[IncomeStatementItemForLLM] = Field(..., description="Lista de ítems principales del estado de resultados (sin concepto)")
    detalles_estado_resultados: List[SheetItem]


def create_income_statement_main_results_model(fields: dict) -> Type[List[IncomeStatementItem]]:
    """
    Crea dinámicamente el modelo IncomeStatementMainResults basado en campos configurados.
    
    La estructura usa directamente una lista de IncomeStatementItem (sin wrapper).
    
    Args:
        fields: Dict con formato {concepto: etiqueta} (ej: {"ingresos_por_venta": "Ingresos por Venta"})
    
    Returns:
        Type: Tipo List[IncomeStatementItem]
    
    Ejemplo:
        >>> fields = {"ingresos_por_venta": "Ingresos por Venta", "resultado_neto": "Resultado Neto"}
        >>> Model = create_income_statement_main_results_model(fields)
        >>> # El modelo es directamente List[IncomeStatementItem]
    """
    # La nueva estructura retorna el tipo List[IncomeStatementItem]
    # Los campos se validan en la configuración del tenant
    # El dict de fields se usa en los prompts para generar la estructura correcta
    return List[IncomeStatementItem]


def create_income_data_model(main_results_model: Type[BaseModel]) -> Type[BaseModel]:
    """
    Crea dinámicamente el modelo IncomeStatementData completo.
    
    Args:
        main_results_model: Modelo de resultados principales (IncomeStatementMainResultsBase)
    
    Returns:
        Type[BaseModel]: Modelo Pydantic completo para datos de estado de resultados
    
    Ejemplo:
        >>> MainResults = create_income_statement_main_results_model(["resultado_neto"])
        >>> IncomeData = create_income_data_model(MainResults)
    """
    return create_model(
        "IncomeStatementData",
        __base__=IncomeStatementDataBase,
        __module__=IncomeStatementDataBase.__module__
    )
