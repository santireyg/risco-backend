# app/api/endpoints/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Endpoints de autenticación:
#   • /register  → crea usuario con status "pending"
#   • /login     → solo permite entrar si status == "active"
#   • /me        → devuelve el usuario actual autenticado
#   • /logout    → borra las cookies de sesión
# ─────────────────────────────────────────────────────────────────────────────

import os
import logging
from datetime import datetime, timedelta
from time import time

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Response,
    Request,
    status,
)

from app.core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, API_COOKIE_DOMAIN
from app.core.database import users_collection
from app.models.users import User, UserPublic
from app.utils.cookies import attach_auth_cookies
from app.core.limiter import limiter

router = APIRouter()

# --- Configuración de rate limiting y bloqueo temporal ---
MAX_LOGIN_ATTEMPTS = 5
BLOCK_TIME_SECONDS = 10  # 5 minutos
login_attempts = {}  # {username: {"count": int, "last_attempt": float, "blocked_until": float}}

# ─────────────────────────── REGISTRO ELIMINADO ────────────────────────────
# El endpoint /register ha sido movido a user_registration.py
# para implementar el nuevo flujo de registro con verificación de email


# ───────────────────────────── /login ─────────────────────────────
@router.post("/login", response_model=dict)
async def login_for_access_token(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    request: Request = None,
):
    """
    • Verifica credenciales.  
    • Solo emite JWT si el usuario está `status="active"`.  
    • En caso contrario responde *403 Forbidden*.
    • Aplica rate limiting y bloqueo temporal tras varios intentos fallidos.
    """
    global login_attempts
    now = time()
    # --- Rate limiting y bloqueo temporal ---
    user_attempt = login_attempts.get(username, {"count": 0, "last_attempt": 0, "blocked_until": 0})
    if user_attempt.get("blocked_until", 0) > now:
        logging.warning(f"Intento de login bloqueado para usuario {username} desde IP {request.client.host if request else 'unknown'}")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos fallidos. Intenta nuevamente en unos minutos.")

    # Obtiene al usuario (case insensitive)
    user_data = await users_collection.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
    if not user_data or not verify_password(password, user_data["password_hash"]):
        # Logging de intento fallido
        logging.warning(f"Login fallido para usuario {username} desde IP {request.client.host if request else 'unknown'}")
        # Actualiza contador de intentos
        user_attempt["count"] = user_attempt.get("count", 0) + 1
        user_attempt["last_attempt"] = now
        # Si supera el máximo, bloquea
        if user_attempt["count"] >= MAX_LOGIN_ATTEMPTS:
            user_attempt["blocked_until"] = now + BLOCK_TIME_SECONDS
            user_attempt["count"] = 0  # Reinicia el contador tras bloquear
        login_attempts[username] = user_attempt
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas"
        )
    # Si login exitoso, limpia el registro de intentos
    if username in login_attempts:
        del login_attempts[username]

    # ¿Cuenta eliminada?
    if user_data.get("status") == "deleted":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Esta cuenta ha sido eliminada y ya no está disponible.",
        )

    # ¿Cuenta activada?
    if user_data.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta no se encuentra activada. Por favor, solicita a un administrador que la apruebe.",
        )

    # Genera JWT
    access_token = create_access_token(
        data={"sub": user_data["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # Actualiza último login
    await users_collection.update_one(
        {"_id": user_data["_id"]},
        {"$set": {"last_login": datetime.utcnow()}},
    )

    # Coloca cookies (token + CSRF)
    is_production = os.getenv("ENVIRONMENT") == "production"
    csrf_token = attach_auth_cookies(
        response, access_token, is_production=is_production
    )

    # Log de login exitoso
    logging.info(f"[AUTH] Login exitoso: usuario {username}")

    # Opcional: devolvemos el CSRF también en el body
    return {"message": "Login successful", "csrf_token": csrf_token}


# ───────────────────────────── /me ────────────────────────────────
@router.get("/me", response_model=UserPublic)
@limiter.limit("45/minute")
async def read_users_me(current_user: User = Depends(get_current_user), request: Request = None):
    return UserPublic(**current_user.model_dump())


# ──────────────────────────── /logout ─────────────────────────────
@router.post("/logout", response_model=dict)
@limiter.limit("30/minute")
async def logout(response: Response, request: Request = None):
    """
    Borra cookies de sesión (token + csrf_token).
    """
    for name in ("token", "csrf_token"):
        response.delete_cookie(name, path="/", domain=API_COOKIE_DOMAIN or None)
    return {"message": "Logout successful"}
