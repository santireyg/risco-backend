# app/models/users.py
from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info):
        if not ObjectId.is_valid(v):
            raise ValueError("ID de objeto inválido")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}


# ────────────────────────────────────────────────────────────────
# Modelo completo que refleja TODO lo que guardamos en MongoDB.
# Sólo se usa en la capa interna (DAO, servicios, etc.).
# ────────────────────────────────────────────────────────────────
class User(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    password_hash: str
    role: str = "user"
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None

    # Nuevos campos para el sistema de registro
    company_domain: Optional[str] = None  # Extraído del email
    email_verified: bool = False  # Para usuarios existentes será True por defecto
    email_verification_token: Optional[str] = None
    email_verification_expires: Optional[datetime] = None
    approved_by: Optional[str] = None  # Username del admin que aprobó

    # Nuevos campos para reset de contraseña
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    last_password_change: Optional[datetime] = None

    # Nuevos campos para administración
    deactivated_by: Optional[str] = None  # Username del admin que desactivó
    deactivated_at: Optional[datetime] = None
    role_changed_by: Optional[str] = None  # Username del admin que cambió el rol
    role_changed_at: Optional[datetime] = None

    # Campo para multi-tenant
    tenant_id: str = "default"  # Identificador del tenant al que pertenece el usuario

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ────────────────────────────────────────────────────────────────
# Esquema **público**: lo que el backend devuelve al frontend.
# No incluye password_hash ni otros datos sensibles.
# ────────────────────────────────────────────────────────────────
class UserPublic(BaseModel):
    id: PyObjectId = Field(alias="_id")
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    role: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime] = None
    company_domain: Optional[str] = None
    email_verified: bool = False
    tenant_id: str = "default"  # Identificador del tenant al que pertenece el usuario

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ────────────────────────────────────────────────────────────────
# Esquemas para requests
# ────────────────────────────────────────────────────────────────
class UserRegistrationRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    current_password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str


class UserManagementRequest(BaseModel):
    action: str  # "deactivate" | "activate" | "change_role"
    new_role: Optional[str] = None  # Solo para change_role
