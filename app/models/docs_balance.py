# app/models/docs_balance.py
"""
Modelos base para datos de Balance (Estado de Situación Patrimonial).

Estos modelos sirven como plantillas base para crear versiones dinámicas
específicas de cada tenant en runtime.
"""

from typing import List, Type, Optional
from pydantic import BaseModel, Field, RootModel, create_model

from app.models.docs_financial_items import DocumentGeneralInformation, SheetItem


class BalanceItem(BaseModel):
    """
    Representa un ítem individual del balance con sus valores actual y anterior.
    
    Attributes:
        concepto_code: Identificador del concepto (ej: 'activo_total')
        concepto: Nombre legible del concepto (ej: 'Activo Total') - Opcional
        monto_actual: Valor del período actual
        monto_anterior: Valor del período anterior
    """
    concepto_code: str = Field(..., description="Identificador del concepto contable")
    concepto: Optional[str] = Field(None, description="Etiqueta legible del concepto")
    monto_actual: float = Field(..., description="Monto del período actual")
    monto_anterior: float = Field(..., description="Monto del período anterior")


class BalanceItemForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM (sin campo 'concepto').
    
    El LLM solo extrae concepto_code y montos. El campo 'concepto' se agrega
    en post-procesamiento desde la configuración del tenant.
    """
    concepto_code: str = Field(..., description="Identificador del concepto contable")
    monto_actual: float = Field(..., description="Monto del período actual")
    monto_anterior: float = Field(..., description="Monto del período anterior")


# Tipo alias para lista de BalanceItem (resultados principales es directamente una lista)
BalanceMainResultsBase = List[BalanceItem]


class BalanceDataBase(BaseModel):
    """
    Modelo base para datos completos del Balance.
    
    Este modelo define la estructura general que siempre se mantiene.
    """
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[BalanceItem] = Field(..., description="Lista de ítems principales del balance")
    detalles_activo: List[SheetItem]
    detalles_pasivo: List[SheetItem]
    detalles_patrimonio_neto: List[SheetItem]


class BalanceDataForLLM(BaseModel):
    """
    Modelo simplificado para extracción del LLM.
    
    Usa BalanceItemForLLM (sin campo 'concepto') para resultados_principales.
    """
    informacion_general: DocumentGeneralInformation
    resultados_principales: List[BalanceItemForLLM] = Field(..., description="Lista de ítems principales del balance")
    detalles_activo: List[SheetItem]
    detalles_pasivo: List[SheetItem]
    detalles_patrimonio_neto: List[SheetItem]


def create_balance_main_results_model(fields: dict) -> Type[List[BalanceItem]]:
    """
    Crea dinámicamente el modelo BalanceMainResults basado en campos configurados.
    
    La estructura usa directamente una lista de BalanceItem (sin wrapper).
    
    Args:
        fields: Dict con formato {concepto: etiqueta} (ej: {"activo_total": "Activo Total"})
    
    Returns:
        Type: Tipo List[BalanceItem]
    
    Ejemplo:
        >>> fields = {"activo_total": "Activo Total", "pasivo_total": "Pasivo Total"}
        >>> Model = create_balance_main_results_model(fields)
        >>> # El modelo es directamente List[BalanceItem]
    """
    # La nueva estructura retorna el tipo List[BalanceItem]
    # Los campos se validan en la configuración del tenant
    # El dict de fields se usa en los prompts para generar la estructura correcta
    return List[BalanceItem]


def create_balance_data_model(main_results_model: Type[BaseModel]) -> Type[BaseModel]:
    """
    Crea dinámicamente el modelo BalanceData completo.
    
    Args:
        main_results_model: Modelo de resultados principales (BalanceMainResultsBase)
    
    Returns:
        Type[BaseModel]: Modelo Pydantic completo para datos de balance
    
    Ejemplo:
        >>> MainResults = create_balance_main_results_model(["activo_total"])
        >>> BalanceData = create_balance_data_model(MainResults)
    """
    return create_model(
        "BalanceData",
        __base__=BalanceDataBase,
        __module__=BalanceDataBase.__module__
    )
