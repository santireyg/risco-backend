# app/utils/cookies.py
import secrets
from datetime import timedelta
from fastapi import Response
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES

def attach_auth_cookies(
    response: Response,
    jwt_token: str,
    *,
    is_production: bool,
    csrf_cookie_name: str = "csrf_token",
    jwt_cookie_name: str = "token",
) -> str:
    """
    • Coloca el JWT HttpOnly + una cookie CSRF accesible al front.
    • Devuelve el valor del CSRF por si quieres mandarlo en el body.
    """
    # 1️⃣  cookie HttpOnly con el JWT
    response.set_cookie(
        key=jwt_cookie_name,
        value=jwt_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # 2️⃣  cookie accesible con el CSRF
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=is_production,
        samesite="strict",      # Lax también es válido aquí
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return csrf_token
