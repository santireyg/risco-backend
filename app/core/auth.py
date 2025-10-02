# app/core/auth.py
from datetime import datetime, timedelta, timezone
from typing import Union
import jwt
from jwt import PyJWTError, ExpiredSignatureError
from fastapi import Depends, HTTPException, status, Request
import bcrypt
from app.core.config import SECRET_KEY_AUTH, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.database import users_collection
from app.models.users import User

# Nueva dependencia: extrae el token de las cookies de la solicitud
async def get_token_from_cookie(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# Se actualiza get_current_user para usar el token proveniente de la cookie
async def get_current_user(token: str = Depends(get_token_from_cookie)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY_AUTH, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_data = await users_collection.find_one({"username": username})
        if user_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return User(**user_data)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token ha expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_AUTH, algorithm=ALGORITHM)
    return encoded_jwt

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ────────────────────────────────────────────────────────────────
# Nuevas dependencias de autorización para el sistema de usuarios
# ────────────────────────────────────────────────────────────────

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Requiere rol admin (no incluye superadmin)"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user


async def get_admin_or_superadmin_user(current_user: User = Depends(get_current_user)) -> User:
    """Requiere rol admin o superadmin"""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user


async def get_superadmin_user(current_user: User = Depends(get_current_user)) -> User:
    """Requiere rol superadmin únicamente"""
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de super administrador"
        )
    return current_user


def can_manage_user(admin_user: User, target_user: User) -> bool:
    """
    Determina si un admin puede gestionar a otro usuario.
    """
    # Superadmin puede gestionar a cualquiera excepto otros superadmin
    if admin_user.role == "superadmin":
        return target_user.role != "superadmin"

    # Admin solo puede gestionar usuarios básicos
    if admin_user.role == "admin":
        return target_user.role == "user"

    return False


def validate_password_strength(password: str) -> bool:
    """
    Valida que la contraseña cumpla con criterios mínimos de seguridad.
    """
    if len(password) < 8:
        return False
    
    # Al menos una letra mayúscula, una minúscula y un número
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    return has_upper and has_lower and has_digit
