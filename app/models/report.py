# app/models/report.py
"""
Modelos para Reportes Financieros generados a partir de balances analizados.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from bson import ObjectId


# ------------------------------------------------------------------------------------
# MODELOS DE CREADOR Y EMPRESA
# ------------------------------------------------------------------------------------
class CreatedBy(BaseModel):
    """Información del usuario que creó el reporte."""
    user_id: str
    name: str
    tenant_id: str


class CompanyInfoReport(BaseModel):
    """Información de la empresa para el reporte."""
    company_cuit: Optional[str] = None
    company_name: str
    company_activity: Optional[str] = None
    company_address: Optional[str] = None


# ------------------------------------------------------------------------------------
# MODELOS DE DATOS FINANCIEROS
# ------------------------------------------------------------------------------------
class BalanceDataSummary(BaseModel):
    """Resumen de datos del balance para el reporte."""
    resultados_principales: List[Dict[str, Any]]
    detalles_activo: List[Dict[str, Any]] = []
    detalles_pasivo: List[Dict[str, Any]] = []
    detalles_patrimonio_neto: List[Dict[str, Any]] = []


class IncomeDataSummary(BaseModel):
    """Resumen de datos del estado de resultados para el reporte."""
    resultados_principales: List[Dict[str, Any]]
    detalles_estado_resultados: List[Dict[str, Any]] = []


class StatementData(BaseModel):
    """Datos consolidados del balance y estado de resultados."""
    statement_date: Optional[datetime] = None
    statement_date_previous: Optional[datetime] = None
    balance_data: Optional[BalanceDataSummary] = None
    income_statement_data: Optional[IncomeDataSummary] = None


# ------------------------------------------------------------------------------------
# MODELOS DE INDICADORES
# ------------------------------------------------------------------------------------
class IndicatorResult(BaseModel):
    """Resultado de cálculo de un indicador financiero."""
    code: str = Field(..., description="Código único del indicador")
    name: str = Field(..., description="Nombre legible del indicador")
    description: str = Field(..., description="Descripción del indicador")
    formula: str = Field(..., description="Fórmula de cálculo")
    criteria: Dict[str, str] = Field(..., description="Criterios de clasificación")
    value_current: Optional[float] = Field(None, description="Valor período actual")
    value_previous: Optional[float] = Field(None, description="Valor período anterior")
    variation: Optional[float] = Field(None, description="Variación entre períodos")
    classification_current: Optional[Literal["Excelente", "Admisible", "Deficiente"]] = None
    classification_previous: Optional[Literal["Excelente", "Admisible", "Deficiente"]] = None


# ------------------------------------------------------------------------------------
# MODELOS DE DATOS BCRA
# ------------------------------------------------------------------------------------
class BCRADeuda(BaseModel):
    """Información de deuda con una entidad según BCRA."""
    entidad: str
    situacion: int
    fecha_sit: Optional[str] = None
    monto: float
    dias_atraso_pago: int = 0
    refinanciaciones: bool = False
    recategorizacion_oblig: bool = False
    situacion_juridica: bool = False
    irrec_disposicion_tecnica: bool = False
    en_revision: bool = False
    proceso_jud: bool = False


class BCRAPeriodo(BaseModel):
    """Período de deudas con sus entidades."""
    periodo: str  # Formato AAAAMM
    entidades: List[BCRADeuda] = []


class BCRAChequeDetalle(BaseModel):
    """Detalle de un cheque rechazado."""
    nro_cheque: int
    fecha_rechazo: str
    monto: float
    fecha_pago: Optional[str] = None
    fecha_pago_multa: Optional[str] = None
    estado_multa: Optional[str] = None
    cta_personal: bool = False
    denom_juridica: Optional[str] = None
    en_revision: bool = False
    proceso_jud: bool = False


class BCRAChequeEntidad(BaseModel):
    """Entidad con cheques rechazados."""
    entidad: int
    detalle: List[BCRAChequeDetalle] = []


class BCRAChequeCausal(BaseModel):
    """Causal de rechazo con sus entidades."""
    causal: str
    entidades: List[BCRAChequeEntidad] = []


class BCRAData(BaseModel):
    """Datos consolidados del BCRA."""
    identificacion: Optional[str] = None
    denominacion: Optional[str] = None
    fecha_consulta: Optional[datetime] = None
    deudas_ultimo_periodo: Optional[BCRAPeriodo] = None
    deudas_historia: List[BCRAPeriodo] = []
    cheques_rechazados: List[BCRAChequeCausal] = []


# ------------------------------------------------------------------------------------
# MODELOS DEL ANÁLISIS DE IA
# ------------------------------------------------------------------------------------
from typing import Annotated, List
from pydantic import BaseModel, Field

class KeyInsights(BaseModel):
    """Insights clave generados por IA."""
    strengths: List[str] = Field(default_factory=list, description="Lista de puntos fuertes (formato Markdown)")
    watchouts: List[str] = Field(default_factory=list, description="Lista de alertas (formato Markdown)")
    red_flags: List[str] = Field(default_factory=list, description="Lista de alarmas (formato Markdown)")

class AIReport(BaseModel):
    """Reporte generado por IA del Análisis de riesgo."""
    reasoned_analysis: str = Field(..., description="Análisis razonado en formato Markdown")
    executive_summary: str = Field(..., description="Resumen ejecutivo en formato Markdown")
    key_insights: KeyInsights


# ------------------------------------------------------------------------------------
# MODELO PRINCIPAL DE REPORTE
# ------------------------------------------------------------------------------------
class Report(BaseModel):
    """Modelo principal del reporte financiero."""
    tenant_id: str
    docfile_id: str
    status: Literal["Generando reporte", "Finalizado", "Error"] = "Generando reporte"
    company_name: str
    company_cuit: Optional[str] = None
    company_info: Optional[CompanyInfoReport] = None
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    created_by: CreatedBy
    statement_data: Optional[StatementData] = None
    indicators: Optional[List[IndicatorResult]] = None
    bcra_data: Optional[BCRAData] = None
    ai_report: Optional[AIReport] = None
    report_processing_time: Optional[float] = Field(default=None, description="Tiempo total de generación del reporte en segundos")
    error_message: Optional[str] = None

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
