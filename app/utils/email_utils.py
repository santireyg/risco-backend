# app/utils/email_utils.py

import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from jinja2 import Template
from app.core.email import email_service
from app.core.config import (
    EMAIL_VERIFICATION_URL, 
    PASSWORD_RESET_URL,
    FRONTEND_URL,
    ADMIN_NOTIFICATION_EMAILS,
    NOTIFY_ALL_ADMINS,
    ARGENTINA_TZ,
)
from app.core.database import users_collection


def load_template(template_name: str) -> Template:
    """
    Carga una plantilla de email desde el directorio templates como Jinja2 Template.
    """
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        "templates", 
        template_name
    )
    with open(template_path, 'r', encoding='utf-8') as file:
        template_content = file.read()
    return Template(template_content)


# Helper para convertir datetimes a timezone de Argentina
def to_argentina(dt: datetime) -> datetime:
    """Convierte un datetime a la zona horaria ARGENTINA_TZ.
    Si el datetime es naive, se asume que está en UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ARGENTINA_TZ)


async def send_verification_email(user_data: Dict[str, Any], token: str) -> bool:
    """
    Envía email de verificación a un nuevo usuario.
    """
    if not email_service:
        return False
    
    template = load_template("email_verification.html")
    verification_url = f"{EMAIL_VERIFICATION_URL}/{token}"
    
    html_content = template.render(
        first_name=user_data["first_name"],
        verification_url=verification_url
    )
    
    return await email_service.send_email(
        to=user_data["email"],
        subject="Verifica tu email - Sistama IA Caución | Integrity",
        html_content=html_content
    )


async def send_welcome_email(user_data: Dict[str, Any]) -> bool:
    """
    Envía email de bienvenida cuando un usuario es aprobado.
    """
    if not email_service:
        return False
    
    template = load_template("welcome_email.html")
    
    html_content = template.render(
        first_name=user_data["first_name"],
        username=user_data["username"],
        email=user_data["email"],
        role=user_data["role"],
        frontend_url=FRONTEND_URL
    )
    
    return await email_service.send_email(
        to=user_data["email"],
        subject="¡Cuenta aprobada! - Sistama IA Caución | Integrity",
        html_content=html_content
    )


async def send_admin_notification_email(user_data: Dict[str, Any]) -> bool:
    """
    Envía notificación a administradores cuando hay un nuevo usuario pendiente.
    """
    if not email_service:
        return False
    
    # Determinar a quién enviar
    admin_emails = []
    if NOTIFY_ALL_ADMINS:
        # Obtener todos los admins de la base de datos
        admins_cursor = users_collection.find({"role": {"$in": ["admin", "superadmin"]}})
        admin_emails = [admin["email"] async for admin in admins_cursor]
    else:
        # Usar lista específica de emails
        admin_emails = [email.strip() for email in ADMIN_NOTIFICATION_EMAILS if email.strip()]
    
    if not admin_emails:
        return False
    
    template = load_template("admin_notification.html")
    admin_panel_url = f"{FRONTEND_URL}/admin"
    
    # Asegurarse de convertir created_at a timezone de Argentina
    created_at_arg = to_argentina(user_data["created_at"]) if user_data.get("created_at") else None

    html_content = template.render(
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        username=user_data["username"],
        email=user_data["email"],
        company_domain=user_data.get("company_domain", ""),
        created_at=created_at_arg.strftime("%d/%m/%Y %H:%M") if created_at_arg else "",
        admin_panel_url=admin_panel_url
    )
    
    results = await email_service.send_bulk_email(
        emails=admin_emails,
        subject="Nuevo usuario pendiente de aprobación",
        html_content=html_content
    )
    
    return any(results.values())


async def send_password_reset_email(user_data: Dict[str, Any], token: str) -> bool:
    """
    Envía email de reset de contraseña.
    """
    if not email_service:
        return False
    
    template = load_template("password_reset.html")
    reset_url = f"{PASSWORD_RESET_URL}?token={token}"
    
    html_content = template.render(
        first_name=user_data["first_name"],
        reset_url=reset_url
    )
    
    return await email_service.send_email(
        to=user_data["email"],
        subject="Restablecer contraseña - Sistama IA Caución | Integrity",
        html_content=html_content
    )


async def send_password_changed_email(user_data: Dict[str, Any]) -> bool:
    """
    Envía confirmación de cambio de contraseña.
    """
    if not email_service:
        return False
    
    template = load_template("password_changed.html")
    
    changed_at_arg = to_argentina(datetime.now(timezone.utc))
    
    html_content = template.render(
        first_name=user_data["first_name"],
        changed_at=changed_at_arg.strftime("%d/%m/%Y %H:%M")
    )
    
    return await email_service.send_email(
        to=user_data["email"],
        subject="Contraseña actualizada - Sistama IA Caución | Integrity",
        html_content=html_content
    )


async def send_profile_update_email(user_data: Dict[str, Any], changes: List[str]) -> bool:
    """
    Envía notificación de actualización de perfil.
    """
    if not email_service:
        return False
    
    template = load_template("profile_update.html")
    changes_list = "".join([f"<li>{change}</li>" for change in changes])
    
    updated_at_arg = to_argentina(datetime.now(timezone.utc))
    
    html_content = template.render(
        first_name=user_data["first_name"],
        changes_list=changes_list,
        updated_at=updated_at_arg.strftime("%d/%m/%Y %H:%M")
    )
    
    return await email_service.send_email(
        to=user_data["email"],
        subject="Perfil actualizado - Sistama IA Caución | Integrity",
        html_content=html_content
    )
