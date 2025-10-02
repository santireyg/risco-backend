# app/core/domain_validation.py

import os
from app.core.config import ALLOWED_EMAIL_DOMAIN, SKIP_DOMAIN_VALIDATION_LOCAL, ENVIRONMENT


def validate_email_domain(email: str) -> bool:
    """
    Valida el dominio del email según configuración.
    En ambiente local puede saltarse la validación.
    """
        
    if SKIP_DOMAIN_VALIDATION_LOCAL:
        return True

    email_l = email.lower()

    # Compatibilidad: ALLOWED_EMAIL_DOMAIN debería ser una cadena leída desde env (posible coma-separada),
    # pero soportamos también listas por si hubiera cambios anteriores.
    if isinstance(ALLOWED_EMAIL_DOMAIN, (list, tuple)):
        parts = [p.strip().lower() for p in ALLOWED_EMAIL_DOMAIN if p]
    else:
        raw = (ALLOWED_EMAIL_DOMAIN or "").strip()
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]

    # Normalizar: asegurar que cada dominio comience con '@'
    allowed = [(p if p.startswith("@") else "@" + p) for p in parts]

    return any(email_l.endswith(domain) for domain in allowed)


def extract_company_domain(email: str) -> str:
    """
    Extrae el dominio de la empresa del email.
    """
    return email.split("@")[1] if "@" in email else ""
