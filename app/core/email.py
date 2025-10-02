# app/core/email.py

import logging
from typing import List, Dict, Any
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app.core.config import BREVO_API_KEY, MAIL_FROM, MAIL_FROM_NAME

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        if not BREVO_API_KEY:
            raise ValueError("BREVO_API_KEY no está configurado")
        
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = BREVO_API_KEY
        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

    async def send_email(self, to: str, subject: str, html_content: str, sender_name: str = None) -> bool:
        """
        Envía un email usando Brevo.
        
        Args:
            to: Email del destinatario
            subject: Asunto del email
            html_content: Contenido HTML del email
            sender_name: Nombre del remitente (opcional)
        
        Returns:
            bool: True si se envió exitosamente, False en caso contrario
        """
        try:
            sender = {
                "name": sender_name or MAIL_FROM_NAME,
                "email": MAIL_FROM
            }
            
            to_list = [{"email": to}]
            
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=to_list,
                sender=sender,
                subject=subject,
                html_content=html_content
            )
            
            api_response = self.api_instance.send_transac_email(send_smtp_email)
            logger.info(f"Email enviado exitosamente a {to}: {api_response}")
            return True
            
        except ApiException as e:
            logger.error(f"Error enviando email a {to}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado enviando email a {to}: {e}")
            return False

    async def send_bulk_email(self, emails: List[str], subject: str, html_content: str, sender_name: str = None) -> Dict[str, bool]:
        """
        Envía el mismo email a múltiples destinatarios.
        
        Args:
            emails: Lista de emails de destinatarios
            subject: Asunto del email
            html_content: Contenido HTML del email
            sender_name: Nombre del remitente (opcional)
        
        Returns:
            Dict[str, bool]: Diccionario con el resultado de cada envío
        """
        results = {}
        for email in emails:
            if email.strip():  # Solo enviar si el email no está vacío
                results[email] = await self.send_email(email, subject, html_content, sender_name)
        return results


# Instancia global del servicio de email
email_service = EmailService() if BREVO_API_KEY else None
