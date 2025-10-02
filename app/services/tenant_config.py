# app/services/tenant_config.py
"""
Sistema de configuración multi-tenant.
Carga y cachea configuraciones de tenants desde MongoDB y archivos Python.
"""

import importlib
from typing import Optional, List, Type
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Cache de configuraciones cargadas
_tenant_configs: dict[str, "TenantConfig"] = {}

# Campos mínimos requeridos para validaciones
# Formato: {"concepto": "Etiqueta legible"}
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

INCOME_REQUIRED_FIELDS = {
    "ingresos_por_venta": "Ingresos por Venta",
    "resultados_antes_de_impuestos": "Resultados Antes de Impuestos",
    "resultados_del_ejercicio": "Resultados del Ejercicio"
}


class TenantConfig:
    """
    Configuración consolidada de un tenant.

    Carga configuración desde:
    - MongoDB (colección 'tenants'): Campos dinámicos
    - Archivos Python (app/tenants/{tenant_id}/): Prompts
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._db_config: Optional[dict] = None
        self._prompts_module = None

        # Cargar configuración
        self._load_config()

    def _load_config(self):
        """Carga configuración desde MongoDB y archivos."""
        # 1. Cargar desde MongoDB usando pymongo (síncrono)
        from pymongo import MongoClient
        from app.core.config import MONGO_URI, MONGO_DB
        
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        
        self._db_config = db.tenants.find_one({"tenant_id": self.tenant_id})

        if not self._db_config:
            logger.warning(f"Tenant '{self.tenant_id}' no encontrado en BD, usando 'default'")
            self._db_config = db.tenants.find_one({"tenant_id": "default"})
            if not self._db_config:
                client.close()
                raise ValueError("Tenant 'default' no existe en la base de datos")
        
        client.close()

        # 2. Cargar prompts desde archivos Python
        try:
            self._prompts_module = importlib.import_module(f"app.tenants.{self.tenant_id}.prompts")
            logger.info(f"Prompts cargados para tenant '{self.tenant_id}'")
        except ImportError:
            logger.warning(f"No se encontraron prompts para tenant '{self.tenant_id}', usando 'default'")
            self._prompts_module = importlib.import_module("app.tenants.default.prompts")

    @property
    def tenant_name(self) -> str:
        """Nombre legible del tenant."""
        return self._db_config.get("tenant_name", "Unknown")

    @property
    def status(self) -> str:
        """Status del tenant."""
        return self._db_config.get("status", "inactive")

    @property
    def balance_fields(self) -> dict:
        """
        Campos de resultados principales del Balance.
        
        Retorna dict con formato: {"concepto": "Etiqueta legible"}
        Ejemplo: {"activo_total": "Activo Total", "pasivo_total": "Pasivo Total"}
        """
        return self._db_config.get("balance_main_results_fields", {})

    @property
    def income_fields(self) -> dict:
        """
        Campos de resultados principales del Income Statement.
        
        Retorna dict con formato: {"concepto": "Etiqueta legible"}
        Ejemplo: {"ingresos_por_venta": "Ingresos por venta"}
        """
        return self._db_config.get("income_statement_main_results_fields", {})

    @property
    def prompt_extract_balance(self) -> str:
        """Prompt para extracción de Balance."""
        return getattr(self._prompts_module, "PROMPT_EXTRACT_BALANCE", "")

    @property
    def prompt_extract_income(self) -> str:
        """Prompt para extracción de Income."""
        return getattr(self._prompts_module, "PROMPT_EXTRACT_INCOME", "")

    def create_balance_model(self) -> Type[BaseModel]:
        """
        Crea dinámicamente el modelo Pydantic BalanceMainResults
        basado en los campos configurados del tenant.
        """
        from app.models.docs_balance import create_balance_main_results_model
        return create_balance_main_results_model(self.balance_fields)

    def create_income_model(self) -> Type[BaseModel]:
        """
        Crea dinámicamente el modelo Pydantic IncomeStatementMainResults
        basado en los campos configurados del tenant.
        """
        from app.models.docs_income import create_income_statement_main_results_model
        return create_income_statement_main_results_model(self.income_fields)

    def get_s3_prefix(self, docfile_id: str) -> str:
        """
        Retorna el prefijo S3 para documentos de este tenant.

        Formato: {S3_ENVIRONMENT}/{tenant_id}/documents/{docfile_id}/
        """
        from app.core.config import S3_ENVIRONMENT
        return f"{S3_ENVIRONMENT}/{self.tenant_id}/documents/{docfile_id}"


def get_tenant_config(tenant_id: str) -> TenantConfig:
    """
    Factory con cache para configuraciones de tenant.

    Args:
        tenant_id: Identificador del tenant

    Returns:
        TenantConfig: Configuración del tenant
    """
    if tenant_id not in _tenant_configs:
        _tenant_configs[tenant_id] = TenantConfig(tenant_id)

    return _tenant_configs[tenant_id]


def clear_tenant_cache(tenant_id: Optional[str] = None):
    """
    Limpia el cache de configuraciones de tenant.

    Args:
        tenant_id: Si se especifica, limpia solo ese tenant. Si es None, limpia todo.
    """
    global _tenant_configs

    if tenant_id:
        _tenant_configs.pop(tenant_id, None)
        logger.info(f"Cache limpiado para tenant '{tenant_id}'")
    else:
        _tenant_configs.clear()
        logger.info("Cache de tenants completamente limpiado")
