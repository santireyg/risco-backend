# app/api/endpoints/user_registration.py

import logging
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import ValidationError

from app.core.auth import (
    get_current_user,
    hash_password,
    verify_password,
    validate_password_strength,
)
from app.core.database import users_collection
from app.core.domain_validation import validate_email_domain, extract_company_domain
from app.core.limiter import limiter
from app.models.users import (
    User,
    UserPublic,
    UserRegistrationRequest,
    UserUpdateRequest,
    PasswordChangeRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.utils.email_utils import (
    send_verification_email,
    send_admin_notification_email,
    send_password_reset_email,
    send_password_changed_email,
    send_profile_update_email,
)
from app.utils.token_utils import (
    generate_token,
    get_token_expiration,
    is_token_expired,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# REGISTRO DE USUARIO
# ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=dict)
@limiter.limit("30/hour")  # Rate limiting para pruebas, luego 5/hour
async def register_user(
    request: Request,
    user_data: UserRegistrationRequest,
):
    """
    Registro de nuevo usuario con verificación de email.
    El usuario queda con status="email_pending" hasta verificar email.
    """
    try:
        # Validar dominio de email
        if not validate_email_domain(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El dominio del email no está permitido para registro"
            )

        # Validar fortaleza de contraseña
        if not validate_password_strength(user_data.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña debe tener al menos 8 caracteres, incluir mayúsculas, minúsculas y números"
            )

        # ¿Ya existe username o email?
        existing_user = await users_collection.find_one(
            {"$or": [{"username": user_data.username}, {"email": user_data.email}]}
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario o correo ya están registrados",
            )

        # Generar token de verificación
        verification_token = generate_token()
        token_expiration = get_token_expiration()

        # Obtener tenant_id basado en el dominio del email
        from app.services.tenant_mapping import get_tenant_id_from_email
        tenant_id = get_tenant_id_from_email(user_data.email)

        # Crear nuevo usuario
        new_user = {
            "username": user_data.username,
            "email": user_data.email,
            "password_hash": hash_password(user_data.password),
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "role": "user",
            "status": "email_pending",  # Esperando verificación de email
            "created_at": datetime.utcnow(),
            "company_domain": extract_company_domain(user_data.email),
            "email_verified": False,
            "email_verification_token": verification_token,
            "email_verification_expires": token_expiration,
            "tenant_id": tenant_id,  # Asignar tenant basado en dominio
        }

        result = await users_collection.insert_one(new_user)
        
        # Enviar email de verificación
        email_sent = await send_verification_email(new_user, verification_token)
        
        if not email_sent:
            logger.warning(f"No se pudo enviar email de verificación a {user_data.email}")

        logger.info(f"Usuario registrado: {user_data.username} ({user_data.email})")
        
        return {
            "message": "Usuario registrado exitosamente. Por favor revisa tu email para verificar tu cuenta.",
            "email_sent": email_sent
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except ValidationError as e:
        logger.error(f"Error de validación registrando usuario {user_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error de validación: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error interno registrando usuario {user_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# VERIFICACIÓN DE EMAIL
# ────────────────────────────────────────────────────────────────

@router.get("/verify-email/{token}", response_model=dict)
async def verify_email(token: str):
    """
    Verifica el email del usuario usando el token enviado por correo.
    Cambia el status de email_pending -> pending_approval.
    """
    try:
        # Buscar usuario por token
        user_data = await users_collection.find_one({
            "email_verification_token": token
        })
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de verificación inválido"
            )

        # Verificar si el token ha expirado
        if is_token_expired(user_data["email_verification_expires"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El token de verificación ha expirado"
            )

        # Verificar si ya está verificado
        if user_data["email_verified"]:
            return {"message": "El email ya ha sido verificado"}

        # Actualizar usuario
        await users_collection.update_one(
            {"_id": user_data["_id"]},
            {
                "$set": {
                    "email_verified": True,
                    "status": "pending_approval",
                },
                "$unset": {
                    "email_verification_token": "",
                    "email_verification_expires": "",
                }
            }
        )

        # Notificar a administradores
        notification_sent = await send_admin_notification_email(user_data)
        
        if not notification_sent:
            logger.warning(f"No se pudo enviar notificación de admin para usuario {user_data['username']}")

        logger.info(f"Email verificado para usuario: {user_data['username']}")
        
        return {
            "message": "Email verificado exitosamente. Tu cuenta está siendo revisada por un administrador.",
            "admin_notified": notification_sent
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error verificando email con token {token}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# ACTUALIZACIÓN DE PERFIL
# ────────────────────────────────────────────────────────────────

@router.put("/update-profile", response_model=dict)
@limiter.limit("10/hour")
async def update_profile(
    request: Request,
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza los datos del perfil del usuario autenticado.
    Requiere contraseña actual para confirmar identidad.
    """
    try:
        # Verificar contraseña actual
        if not verify_password(update_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contraseña actual incorrecta"
            )

        # Preparar campos a actualizar
        update_fields = {}
        changes = []

        if update_data.first_name and update_data.first_name != current_user.first_name:
            update_fields["first_name"] = update_data.first_name
            changes.append(f"Nombre: {current_user.first_name} → {update_data.first_name}")

        if update_data.last_name and update_data.last_name != current_user.last_name:
            update_fields["last_name"] = update_data.last_name
            changes.append(f"Apellido: {current_user.last_name} → {update_data.last_name}")

        if update_data.username and update_data.username != current_user.username:
            # Verificar que el nuevo username no exista
            existing_user = await users_collection.find_one({"username": update_data.username})
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El nombre de usuario ya está en uso"
                )
            update_fields["username"] = update_data.username
            changes.append(f"Usuario: {current_user.username} → {update_data.username}")

        if not update_fields:
            return {"message": "No se detectaron cambios en el perfil"}

        # Actualizar en la base de datos
        await users_collection.update_one(
            {"_id": current_user.id},
            {"$set": update_fields}
        )

        # Enviar email de notificación
        user_dict = current_user.model_dump()
        user_dict.update(update_fields)
        email_sent = await send_profile_update_email(user_dict, changes)
        
        if not email_sent:
            logger.warning(f"No se pudo enviar email de actualización de perfil a {current_user.email}")

        logger.info(f"Perfil actualizado para usuario: {current_user.username}")
        
        return {
            "message": "Perfil actualizado exitosamente",
            "changes": changes,
            "email_sent": email_sent
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error actualizando perfil de usuario {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# CAMBIO DE CONTRASEÑA
# ────────────────────────────────────────────────────────────────

@router.put("/change-password", response_model=dict)
@limiter.limit("5/hour")
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Cambia la contraseña del usuario autenticado.
    """
    try:
        # Verificar contraseña actual
        if not verify_password(password_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contraseña actual incorrecta"
            )

        # Verificar que las nuevas contraseñas coincidan
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Las contraseñas nuevas no coinciden"
            )

        # Validar fortaleza de nueva contraseña
        if not validate_password_strength(password_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe tener al menos 8 caracteres, incluir mayúsculas, minúsculas y números"
            )

        # Actualizar contraseña
        new_password_hash = hash_password(password_data.new_password)
        await users_collection.update_one(
            {"_id": current_user.id},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "last_password_change": datetime.utcnow(),
                }
            }
        )

        # Enviar email de confirmación
        user_dict = current_user.model_dump()
        email_sent = await send_password_changed_email(user_dict)
        
        if not email_sent:
            logger.warning(f"No se pudo enviar email de confirmación de cambio de contraseña a {current_user.email}")

        logger.info(f"Contraseña cambiada para usuario: {current_user.username}")
        
        return {
            "message": "Contraseña cambiada exitosamente",
            "email_sent": email_sent
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error cambiando contraseña de usuario {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# RECUPERACIÓN DE CONTRASEÑA
# ────────────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=dict)
@limiter.limit("10/hour")
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest
):
    """
    Inicia el proceso de recuperación de contraseña.
    Siempre retorna éxito para no revelar si el email existe.
    """
    # Normalizar email a minúsculas
    email_normalized = forgot_data.email.lower().strip()
    
    logger.info(f"Solicitud de restablecimiento de contraseña recibida para el correo electrónico: {email_normalized}")
    try:
        # Buscar usuario por email (case insensitive)
        user_data = await users_collection.find_one({
            "email": {"$regex": f"^{email_normalized}$", "$options": "i"}
        })
        
        # Siempre retornar el mismo mensaje por seguridad
        if not user_data:
            logger.info(f"No se encontró ninguna cuenta asociada al correo electrónico: {email_normalized}")
            return {
                "message": "Si el email existe en nuestro sistema, recibirás instrucciones para restablecer tu contraseña."
            }

        logger.info(f"Usuario encontrado para el correo electrónico: {email_normalized}")

        # Solo enviar si el usuario está activo
        if user_data.get("status") != "active":
            logger.info(f"La cuenta asociada al correo electrónico {email_normalized} no está activa.")
            return {
                "message": "Si el email existe en nuestro sistema, recibirás instrucciones para restablecer tu contraseña."
            }

        # Generar token de reset
        reset_token = generate_token()
        token_expiration = get_token_expiration()

        # Actualizar usuario con token de reset
        await users_collection.update_one(
            {"_id": user_data["_id"]},
            {
                "$set": {
                    "password_reset_token": reset_token,
                    "password_reset_expires": token_expiration,
                }
            }
        )

        # Enviar email de reset
        email_sent = await send_password_reset_email(user_data, reset_token)
        
        if not email_sent:
            logger.warning(f"No se pudo enviar email de reset de contraseña a {email_normalized}")
        else:
            logger.info(f"Correo electrónico de restablecimiento de contraseña enviado a: {email_normalized}")

        logger.info(f"Reset de contraseña solicitado para: {email_normalized}")
        
        return {
            "message": "Si el email existe en nuestro sistema, recibirás instrucciones para restablecer tu contraseña."
        }

    except Exception as e:
        logger.error(f"Error en reset de contraseña para email {email_normalized}: {str(e)}")
        # Siempre retornar el mismo mensaje
        return {
            "message": "Si el email existe en nuestro sistema, recibirás instrucciones para restablecer tu contraseña."
        }

@router.post("/reset-password/{token}", response_model=dict)
async def reset_password(
    token: str,
    reset_data: ResetPasswordRequest
):
    """
    Restablece la contraseña usando el token enviado por email.
    """
    try:
        # Buscar usuario por token
        user_data = await users_collection.find_one({
            "password_reset_token": token
        })
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de reset inválido"
            )

        # Verificar si el token ha expirado
        if is_token_expired(user_data["password_reset_expires"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El token de reset ha expirado"
            )

        # Verificar que las contraseñas coincidan
        if reset_data.new_password != reset_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Las contraseñas no coinciden"
            )

        # Validar fortaleza de nueva contraseña
        if not validate_password_strength(reset_data.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña debe tener al menos 8 caracteres, incluir mayúsculas, minúsculas y números"
            )

        # Actualizar contraseña y limpiar token
        new_password_hash = hash_password(reset_data.new_password)
        await users_collection.update_one(
            {"_id": user_data["_id"]},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "last_password_change": datetime.utcnow(),
                },
                "$unset": {
                    "password_reset_token": "",
                    "password_reset_expires": "",
                }
            }
        )

        # Enviar email de confirmación
        email_sent = await send_password_changed_email(user_data)
        
        if not email_sent:
            logger.warning(f"No se pudo enviar email de confirmación de reset a {user_data['email']}")

        logger.info(f"Contraseña restablecida para usuario: {user_data['username']}")
        
        return {
            "message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña.",
            "email_sent": email_sent
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error restableciendo contraseña con token {token}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )
