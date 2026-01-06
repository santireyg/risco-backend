# app/utils/indicators_calculator.py
"""
Calculadora de indicadores financieros para reportes.

Calcula 7 KPIs principales con clasificaciones basadas en criterios definidos:
- Capital de Trabajo
- % CT sobre Activo Total
- Rotación del Capital de Trabajo
- Liquidez Corriente
- Prueba Ácida
- Cash Ratio
- Endeudamiento
- Margen Operativo
"""

from typing import List, Dict, Any, Optional, Literal
from app.models.report import IndicatorResult
from app.utils.financial_data_accessor import create_accessor
import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------
# DEFINICIÓN DE INDICADORES
# ------------------------------------------------------------------------------------
INDICATORS_CONFIG = {
    "capital_trabajo": {
        "name": "Capital de Trabajo",
        "description": "Recursos disponibles para la operación a corto plazo.",
        "formula": "Activo Corriente - Pasivo Corriente",
        "criteria": {
            "deficiente": "< 10% del activo total",
            "admisible": "10% - 30% del activo total",
            "excelente": "> 30% del activo total"
        }
    },
    "ct_sobre_activo": {
        "name": "% CT sobre Activo Total",
        "description": "Proporción del activo total que representa el capital de trabajo.",
        "formula": "(Capital de Trabajo / Activo Total) × 100",
        "criteria": {
            "deficiente": "< 10%",
            "admisible": "10% - 30%",
            "excelente": "> 30%"
        }
    },
    "rotacion_ct": {
        "name": "Rotación del Capital de Trabajo",
        "description": "Eficiencia en el uso del capital de trabajo para generar ventas.",
        "formula": "Ventas / Capital de Trabajo",
        "criteria": {
            "deficiente": "< 1x",
            "admisible": "1x - 3x",
            "excelente": "> 3x"
        }
    },
    "liquidez_corriente": {
        "name": "Liquidez Corriente",
        "description": "Capacidad para cubrir obligaciones de corto plazo.",
        "formula": "Activo Corriente / Pasivo Corriente",
        "criteria": {
            "deficiente": "< 1.2x",
            "admisible": "1.2x - 2.0x",
            "excelente": "> 2.0x"
        }
    },
    "prueba_acida": {
        "name": "Prueba Ácida",
        "description": "Liquidez sin contar inventarios.",
        "formula": "(Activo Corriente - Inventarios) / Pasivo Corriente",
        "criteria": {
            "deficiente": "< 0.8x",
            "admisible": "0.8x - 1.0x",
            "excelente": "> 1.0x"
        }
    },
    "cash_ratio": {
        "name": "Cash Ratio",
        "description": "Liquidez inmediata (caja/bancos).",
        "formula": "Disponibilidades / Pasivo Corriente",
        "criteria": {
            "deficiente": "< 0.2x",
            "admisible": "0.2x - 0.5x",
            "excelente": "> 0.5x"
        }
    },
    "endeudamiento": {
        "name": "Endeudamiento",
        "description": "Porcentaje de activos financiados con deuda.",
        "formula": "(Pasivo Total / Activo Total) × 100",
        "criteria": {
            "deficiente": "> 60%",
            "admisible": "40% - 60%",
            "excelente": "< 40%"
        }
    },
    "margen_operativo": {
        "name": "Margen Operativo",
        "description": "Rentabilidad operativa sobre ventas.",
        "formula": "(Resultado Operativo / Ventas) × 100",
        "criteria": {
            "deficiente": "< 8%",
            "admisible": "8% - 15%",
            "excelente": "> 15%"
        }
    }
}


# ------------------------------------------------------------------------------------
# FUNCIONES DE CLASIFICACIÓN
# ------------------------------------------------------------------------------------
def classify_capital_trabajo(ct: float, activo_total: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica el Capital de Trabajo según el % del activo total."""
    if activo_total == 0:
        return "Deficiente"
    ratio = (ct / activo_total) * 100
    if ratio > 30:
        return "Excelente"
    elif ratio >= 10:
        return "Admisible"
    return "Deficiente"


def classify_ct_sobre_activo(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica el % CT sobre Activo Total."""
    if ratio > 30:
        return "Excelente"
    elif ratio >= 10:
        return "Admisible"
    return "Deficiente"


def classify_rotacion_ct(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica la Rotación del CT."""
    if ratio > 3:
        return "Excelente"
    elif ratio >= 1:
        return "Admisible"
    return "Deficiente"


def classify_liquidez_corriente(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica la Liquidez Corriente."""
    if ratio > 2.0:
        return "Excelente"
    elif ratio >= 1.2:
        return "Admisible"
    return "Deficiente"


def classify_prueba_acida(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica la Prueba Ácida."""
    if ratio > 1.0:
        return "Excelente"
    elif ratio >= 0.8:
        return "Admisible"
    return "Deficiente"


def classify_cash_ratio(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica el Cash Ratio."""
    if ratio > 0.5:
        return "Excelente"
    elif ratio >= 0.2:
        return "Admisible"
    return "Deficiente"


def classify_endeudamiento(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica el Endeudamiento (invertido: menor es mejor)."""
    if ratio < 40:
        return "Excelente"
    elif ratio <= 60:
        return "Admisible"
    return "Deficiente"


def classify_margen_operativo(ratio: float) -> Literal["Excelente", "Admisible", "Deficiente"]:
    """Clasifica el Margen Operativo."""
    if ratio > 15:
        return "Excelente"
    elif ratio >= 8:
        return "Admisible"
    return "Deficiente"


# ------------------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE CÁLCULO
# ------------------------------------------------------------------------------------
def calculate_indicators(
    balance_data: Dict[str, Any],
    income_data: Dict[str, Any]
) -> List[IndicatorResult]:
    """
    Calcula todos los indicadores financieros para ambos períodos.
    
    Args:
        balance_data: Datos del balance (debe contener resultados_principales)
        income_data: Datos del estado de resultados (debe contener resultados_principales)
        
    Returns:
        Lista de IndicatorResult con todos los indicadores calculados
    """
    indicators = []
    
    # Crear accessors para extraer valores
    balance_accessor = create_accessor(balance_data.get("resultados_principales", []))
    income_accessor = create_accessor(income_data.get("resultados_principales", []))
    
    # Obtener valores del balance
    activo_total_actual = balance_accessor.get("activo_total", "actual") or 0
    activo_total_anterior = balance_accessor.get("activo_total", "anterior") or 0
    activo_corriente_actual = balance_accessor.get("activo_corriente", "actual") or 0
    activo_corriente_anterior = balance_accessor.get("activo_corriente", "anterior") or 0
    pasivo_total_actual = balance_accessor.get("pasivo_total", "actual") or 0
    pasivo_total_anterior = balance_accessor.get("pasivo_total", "anterior") or 0
    pasivo_corriente_actual = balance_accessor.get("pasivo_corriente", "actual") or 0
    pasivo_corriente_anterior = balance_accessor.get("pasivo_corriente", "anterior") or 0
    disponibilidades_actual = balance_accessor.get("disponibilidades", "actual") or 0
    disponibilidades_anterior = balance_accessor.get("disponibilidades", "anterior") or 0
    bienes_cambio_actual = balance_accessor.get("bienes_de_cambio", "actual") or 0
    bienes_cambio_anterior = balance_accessor.get("bienes_de_cambio", "anterior") or 0
    
    # Obtener valores del estado de resultados
    ventas_actual = income_accessor.get("ingresos_por_venta", "actual") or 0
    ventas_anterior = income_accessor.get("ingresos_por_venta", "anterior") or 0
    resultado_operativo_actual = income_accessor.get("resultado_operativo", "actual") or 0
    resultado_operativo_anterior = income_accessor.get("resultado_operativo", "anterior") or 0
    
    # ------------------------------------------------------------------------------------
    # 1. CAPITAL DE TRABAJO
    # ------------------------------------------------------------------------------------
    ct_actual = activo_corriente_actual - pasivo_corriente_actual
    ct_anterior = activo_corriente_anterior - pasivo_corriente_anterior
    
    indicators.append(IndicatorResult(
        code="capital_trabajo",
        name=INDICATORS_CONFIG["capital_trabajo"]["name"],
        description=INDICATORS_CONFIG["capital_trabajo"]["description"],
        formula=INDICATORS_CONFIG["capital_trabajo"]["formula"],
        criteria=INDICATORS_CONFIG["capital_trabajo"]["criteria"],
        value_current=ct_actual,
        value_previous=ct_anterior,
        variation=ct_actual - ct_anterior if ct_anterior != 0 else None,
        classification_current=classify_capital_trabajo(ct_actual, activo_total_actual),
        classification_previous=classify_capital_trabajo(ct_anterior, activo_total_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 2. % CT SOBRE ACTIVO TOTAL
    # ------------------------------------------------------------------------------------
    ct_ratio_actual = (ct_actual / activo_total_actual * 100) if activo_total_actual else 0
    ct_ratio_anterior = (ct_anterior / activo_total_anterior * 100) if activo_total_anterior else 0
    
    indicators.append(IndicatorResult(
        code="ct_sobre_activo",
        name=INDICATORS_CONFIG["ct_sobre_activo"]["name"],
        description=INDICATORS_CONFIG["ct_sobre_activo"]["description"],
        formula=INDICATORS_CONFIG["ct_sobre_activo"]["formula"],
        criteria=INDICATORS_CONFIG["ct_sobre_activo"]["criteria"],
        value_current=round(ct_ratio_actual, 2),
        value_previous=round(ct_ratio_anterior, 2),
        variation=round(ct_ratio_actual - ct_ratio_anterior, 2),
        classification_current=classify_ct_sobre_activo(ct_ratio_actual),
        classification_previous=classify_ct_sobre_activo(ct_ratio_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 3. ROTACIÓN DEL CAPITAL DE TRABAJO
    # ------------------------------------------------------------------------------------
    rotacion_actual = (ventas_actual / ct_actual) if ct_actual else 0
    rotacion_anterior = (ventas_anterior / ct_anterior) if ct_anterior else 0
    
    indicators.append(IndicatorResult(
        code="rotacion_ct",
        name=INDICATORS_CONFIG["rotacion_ct"]["name"],
        description=INDICATORS_CONFIG["rotacion_ct"]["description"],
        formula=INDICATORS_CONFIG["rotacion_ct"]["formula"],
        criteria=INDICATORS_CONFIG["rotacion_ct"]["criteria"],
        value_current=round(rotacion_actual, 2),
        value_previous=round(rotacion_anterior, 2),
        variation=round(rotacion_actual - rotacion_anterior, 2),
        classification_current=classify_rotacion_ct(rotacion_actual),
        classification_previous=classify_rotacion_ct(rotacion_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 4. LIQUIDEZ CORRIENTE
    # ------------------------------------------------------------------------------------
    liquidez_actual = (activo_corriente_actual / pasivo_corriente_actual) if pasivo_corriente_actual else 0
    liquidez_anterior = (activo_corriente_anterior / pasivo_corriente_anterior) if pasivo_corriente_anterior else 0
    
    indicators.append(IndicatorResult(
        code="liquidez_corriente",
        name=INDICATORS_CONFIG["liquidez_corriente"]["name"],
        description=INDICATORS_CONFIG["liquidez_corriente"]["description"],
        formula=INDICATORS_CONFIG["liquidez_corriente"]["formula"],
        criteria=INDICATORS_CONFIG["liquidez_corriente"]["criteria"],
        value_current=round(liquidez_actual, 2),
        value_previous=round(liquidez_anterior, 2),
        variation=round(liquidez_actual - liquidez_anterior, 2),
        classification_current=classify_liquidez_corriente(liquidez_actual),
        classification_previous=classify_liquidez_corriente(liquidez_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 5. PRUEBA ÁCIDA
    # ------------------------------------------------------------------------------------
    acida_actual = ((activo_corriente_actual - bienes_cambio_actual) / pasivo_corriente_actual) if pasivo_corriente_actual else 0
    acida_anterior = ((activo_corriente_anterior - bienes_cambio_anterior) / pasivo_corriente_anterior) if pasivo_corriente_anterior else 0
    
    indicators.append(IndicatorResult(
        code="prueba_acida",
        name=INDICATORS_CONFIG["prueba_acida"]["name"],
        description=INDICATORS_CONFIG["prueba_acida"]["description"],
        formula=INDICATORS_CONFIG["prueba_acida"]["formula"],
        criteria=INDICATORS_CONFIG["prueba_acida"]["criteria"],
        value_current=round(acida_actual, 2),
        value_previous=round(acida_anterior, 2),
        variation=round(acida_actual - acida_anterior, 2),
        classification_current=classify_prueba_acida(acida_actual),
        classification_previous=classify_prueba_acida(acida_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 6. CASH RATIO
    # ------------------------------------------------------------------------------------
    cash_actual = (disponibilidades_actual / pasivo_corriente_actual) if pasivo_corriente_actual else 0
    cash_anterior = (disponibilidades_anterior / pasivo_corriente_anterior) if pasivo_corriente_anterior else 0
    
    indicators.append(IndicatorResult(
        code="cash_ratio",
        name=INDICATORS_CONFIG["cash_ratio"]["name"],
        description=INDICATORS_CONFIG["cash_ratio"]["description"],
        formula=INDICATORS_CONFIG["cash_ratio"]["formula"],
        criteria=INDICATORS_CONFIG["cash_ratio"]["criteria"],
        value_current=round(cash_actual, 2),
        value_previous=round(cash_anterior, 2),
        variation=round(cash_actual - cash_anterior, 2),
        classification_current=classify_cash_ratio(cash_actual),
        classification_previous=classify_cash_ratio(cash_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 7. ENDEUDAMIENTO
    # ------------------------------------------------------------------------------------
    endeud_actual = (pasivo_total_actual / activo_total_actual * 100) if activo_total_actual else 0
    endeud_anterior = (pasivo_total_anterior / activo_total_anterior * 100) if activo_total_anterior else 0
    
    indicators.append(IndicatorResult(
        code="endeudamiento",
        name=INDICATORS_CONFIG["endeudamiento"]["name"],
        description=INDICATORS_CONFIG["endeudamiento"]["description"],
        formula=INDICATORS_CONFIG["endeudamiento"]["formula"],
        criteria=INDICATORS_CONFIG["endeudamiento"]["criteria"],
        value_current=round(endeud_actual, 2),
        value_previous=round(endeud_anterior, 2),
        variation=round(endeud_actual - endeud_anterior, 2),
        classification_current=classify_endeudamiento(endeud_actual),
        classification_previous=classify_endeudamiento(endeud_anterior)
    ))
    
    # ------------------------------------------------------------------------------------
    # 8. MARGEN OPERATIVO
    # ------------------------------------------------------------------------------------
    margen_actual = (resultado_operativo_actual / ventas_actual * 100) if ventas_actual else 0
    margen_anterior = (resultado_operativo_anterior / ventas_anterior * 100) if ventas_anterior else 0
    
    indicators.append(IndicatorResult(
        code="margen_operativo",
        name=INDICATORS_CONFIG["margen_operativo"]["name"],
        description=INDICATORS_CONFIG["margen_operativo"]["description"],
        formula=INDICATORS_CONFIG["margen_operativo"]["formula"],
        criteria=INDICATORS_CONFIG["margen_operativo"]["criteria"],
        value_current=round(margen_actual, 2),
        value_previous=round(margen_anterior, 2),
        variation=round(margen_actual - margen_anterior, 2),
        classification_current=classify_margen_operativo(margen_actual),
        classification_previous=classify_margen_operativo(margen_anterior)
    ))
    
    logger.info(f"[INDICATORS] Calculados {len(indicators)} indicadores")
    return indicators
