# app/utils/bcra_client.py
"""
Cliente HTTP para la API del BCRA (Banco Central de la República Argentina).
Permite consultar la Central de Deudores y cheques rechazados.

API Documentation: https://api.bcra.gob.ar/
"""

import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# URL base de la API del BCRA
BASE_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0"

# Timeout para las requests (en segundos)
BCRA_TIMEOUT = 30.0


class BCRAClientError(Exception):
    """Excepción personalizada para errores del cliente BCRA."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_messages: Optional[list] = None):
        self.message = message
        self.status_code = status_code
        self.error_messages = error_messages or []
        super().__init__(self.message)


async def _make_request(endpoint: str) -> Dict[str, Any]:
    """
    Realiza una request HTTP a la API del BCRA.
    
    Args:
        endpoint: Endpoint relativo (ej: "/Deudas/30500001735")
        
    Returns:
        Dict con la respuesta de la API
        
    Raises:
        BCRAClientError: Si hay un error en la request o respuesta
    """
    url = f"{BASE_URL}{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=BCRA_TIMEOUT, verify=False) as client:
            logger.info(f"[BCRA] Consultando: {url}")
            response = await client.get(url)
            
            data = response.json()
            status = data.get("status", response.status_code)
            
            if status == 200:
                logger.info(f"[BCRA] Respuesta exitosa de: {endpoint}")
                return data
            elif status == 404:
                logger.warning(f"[BCRA] No se encontraron datos para: {endpoint}")
                return {"status": 404, "results": None, "error_messages": data.get("errorMessages", [])}
            elif status == 400:
                error_msgs = data.get("errorMessages", ["Parámetro inválido"])
                raise BCRAClientError(
                    f"Parámetro inválido: {error_msgs}",
                    status_code=400,
                    error_messages=error_msgs
                )
            else:
                error_msgs = data.get("errorMessages", ["Error desconocido"])
                raise BCRAClientError(
                    f"Error BCRA: {error_msgs}",
                    status_code=status,
                    error_messages=error_msgs
                )
                
    except httpx.TimeoutException:
        raise BCRAClientError(f"Timeout al consultar BCRA: {endpoint}", status_code=408)
    except httpx.RequestError as e:
        raise BCRAClientError(f"Error de conexión con BCRA: {str(e)}", status_code=503)
    except Exception as e:
        if isinstance(e, BCRAClientError):
            raise
        raise BCRAClientError(f"Error inesperado consultando BCRA: {str(e)}")


def validate_cuit(cuit: str) -> str:
    """
    Valida y normaliza un CUIT.
    
    Args:
        cuit: CUIT a validar (puede tener guiones o espacios)
        
    Returns:
        CUIT normalizado (11 dígitos numéricos)
        
    Raises:
        BCRAClientError: Si el CUIT no es válido
    """
    # Remover caracteres no numéricos
    cuit_clean = "".join(filter(str.isdigit, str(cuit)))
    
    if len(cuit_clean) != 11:
        raise BCRAClientError(
            f"CUIT inválido: debe tener 11 dígitos (se recibió {len(cuit_clean)})",
            status_code=400
        )
    
    return cuit_clean


async def get_deudas(cuit: str) -> Dict[str, Any]:
    """
    Obtiene la situación crediticia del último período informado.
    
    Args:
        cuit: CUIT/CUIL/CDI de 11 dígitos
        
    Returns:
        Dict con identificacion, denominacion y periodos con entidades
        
    Raises:
        BCRAClientError: Si hay un error en la consulta
    """
    cuit_clean = validate_cuit(cuit)
    return await _make_request(f"/Deudas/{cuit_clean}")


async def get_deudas_historicas(cuit: str) -> Dict[str, Any]:
    """
    Obtiene el historial de situación crediticia de los últimos 24 meses.
    
    Args:
        cuit: CUIT/CUIL/CDI de 11 dígitos
        
    Returns:
        Dict con identificacion, denominacion y periodos históricos
        
    Raises:
        BCRAClientError: Si hay un error en la consulta
    """
    cuit_clean = validate_cuit(cuit)
    return await _make_request(f"/Deudas/Historicas/{cuit_clean}")


async def get_cheques_rechazados(cuit: str) -> Dict[str, Any]:
    """
    Obtiene los cheques rechazados con sus causales.
    
    Args:
        cuit: CUIT/CUIL/CDI de 11 dígitos
        
    Returns:
        Dict con identificacion, denominacion y causales con detalles
        
    Raises:
        BCRAClientError: Si hay un error en la consulta
    """
    cuit_clean = validate_cuit(cuit)
    return await _make_request(f"/Deudas/ChequesRechazados/{cuit_clean}")


async def get_all_bcra_data(cuit: str) -> Dict[str, Any]:
    """
    Obtiene todos los datos BCRA consolidados para un CUIT.
    
    Incluye: deudas actuales, historial de deudas y cheques rechazados.
    
    Args:
        cuit: CUIT/CUIL/CDI de 11 dígitos
        
    Returns:
        Dict consolidado con todos los datos BCRA
    """
    cuit_clean = validate_cuit(cuit)
    
    result = {
        "identificacion": cuit_clean,
        "denominacion": None,
        "fecha_consulta": datetime.utcnow().isoformat(),
        "deudas_ultimo_periodo": None,
        "deudas_historia": [],
        "cheques_rechazados": []
    }
    
    # Obtener deudas del último período
    try:
        deudas_response = await get_deudas(cuit_clean)
        if deudas_response.get("status") == 200 and deudas_response.get("results"):
            results = deudas_response["results"]
            result["denominacion"] = results.get("denominacion")
            if results.get("periodos"):
                periodo = results["periodos"][0] if results["periodos"] else None
                if periodo:
                    # Los montos de la API vienen en miles de pesos, convertir a pesos
                    for entidad in periodo.get("entidades", []):
                        if entidad.get("monto") is not None:
                            entidad["monto"] = entidad["monto"] * 1000
                result["deudas_ultimo_periodo"] = periodo
    except BCRAClientError as e:
        logger.warning(f"[BCRA] Error obteniendo deudas: {e.message}")

    # Obtener historial de deudas
    try:
        historicas_response = await get_deudas_historicas(cuit_clean)
        if historicas_response.get("status") == 200 and historicas_response.get("results"):
            results = historicas_response["results"]
            if not result["denominacion"]:
                result["denominacion"] = results.get("denominacion")
            periodos = results.get("periodos", [])
            # Los montos de la API vienen en miles de pesos, convertir a pesos
            for periodo in periodos:
                for entidad in periodo.get("entidades", []):
                    if entidad.get("monto") is not None:
                        entidad["monto"] = entidad["monto"] * 1000
            result["deudas_historia"] = periodos
    except BCRAClientError as e:
        logger.warning(f"[BCRA] Error obteniendo historial de deudas: {e.message}")
    
    # Obtener cheques rechazados
    try:
        cheques_response = await get_cheques_rechazados(cuit_clean)
        if cheques_response.get("status") == 200 and cheques_response.get("results"):
            results = cheques_response["results"]
            if not result["denominacion"]:
                result["denominacion"] = results.get("denominacion")
            result["cheques_rechazados"] = results.get("causales", [])
    except BCRAClientError as e:
        logger.warning(f"[BCRA] Error obteniendo cheques rechazados: {e.message}")
    
    return result
