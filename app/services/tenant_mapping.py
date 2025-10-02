# app/services/tenant_mapping.py
"""
Mapeo de dominios de email a tenant_id.
"""

# Mapeo estático de dominios a tenants
DOMAIN_TO_TENANT = {
    "caucion.com.ar": "default",  # Por ahora todos van a default
    # Futuros mapeos:
    # "empresa1.com": "empresa1",
    # "empresa2.com": "empresa2",
}


def get_tenant_id_from_email(email: str) -> str:
    """
    Determina el tenant_id basado en el dominio del email.

    Args:
        email: Email del usuario

    Returns:
        str: tenant_id correspondiente (default si no hay mapeo)
    """
    if "@" not in email:
        return "default"

    domain = email.split("@")[1].lower()
    return DOMAIN_TO_TENANT.get(domain, "default")
