# app/models/docs_report.py

from pydantic import BaseModel, Field
from typing import List, Literal

class Indicator(BaseModel):
    indicador: str
    formula: str
    tolerancia_minima: float
    tolerancia_recomendada: float
    criterio: str
    valor_periodo_actual: float
    valor_periodo_anterior: float
    situacion_actual: Literal["Deficiente", "Aceptable", "Excelente"]
    situacion_anterior: Literal["Deficiente", "Aceptable", "Excelente"]

class IndicatorResult(BaseModel):
    indicador: str
    valor_periodo_actual: float
    valor_periodo_anterior: float
    situacion_actual: Literal["Deficiente", "Aceptable", "Excelente"]
    situacion_anterior: Literal["Deficiente", "Aceptable", "Excelente"]

class Recommendation(BaseModel):
    emitir: str = Field(..., description="Si emitir o no la póliza: 'Si', 'No' o 'Advertencia'")
    titulo: str = Field(..., description="Título de la recomendación")
    descripcion: str = Field(..., description="Descripción detallada de la recomendación")

class AIReport(BaseModel):
    resultado_indicadores: List[IndicatorResult]
    descripcion_situacion: str
    sugerencia: Recommendation
    advertencias: List[str]
