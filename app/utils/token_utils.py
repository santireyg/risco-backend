# app/utils/token_utils.py

import secrets
from datetime import datetime, timedelta
from app.core.config import TOKEN_EXPIRATION_HOURS


def generate_token() -> str:
    """
    Genera un token seguro único para verificación de email o reset de contraseña.
    """
    return secrets.token_urlsafe(32)


def get_token_expiration() -> datetime:
    """
    Retorna la fecha de expiración para tokens (24h por defecto).
    """
    return datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Verifica si un token ha expirado.
    """
    return datetime.utcnow() > expires_at
