# app/core/config.py

import os
from dotenv import load_dotenv
from datetime import timedelta, timezone

load_dotenv()

# Configuración de la base de datos
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

# Configuración de autenticación
SECRET_KEY_AUTH = os.getenv("SECRET_KEY_AUTH")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# Configuración de CORS
API_COOKIE_DOMAIN = os.getenv("API_COOKIE_DOMAIN", "localhost")

# Definición de la zona horaria para Argentina (UTC-3)
ARGENTINA_TZ = timezone(timedelta(hours=-3))

# Configuración para LLMs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Configuración de AWS S3
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-2")  # Puedes ajustar la región por defecto
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_ENVIRONMENT = os.getenv("S3_ENVIRONMENT") 
ENVIRONMENT = os.getenv("ENVIRONMENT")  # Ej: "test" o "prod"

# Email Configuration - BREVO
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Integrity | IA Caución")

# Domain Configuration
# Keep only a simple read from the environment; parsing/normalization is handled elsewhere.
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "@empresa.com").strip()
SKIP_DOMAIN_VALIDATION_LOCAL = os.getenv("SKIP_DOMAIN_VALIDATION_LOCAL", "true").lower() == "true"

# Admin Notifications
ADMIN_NOTIFICATION_EMAILS = os.getenv("ADMIN_NOTIFICATION_EMAILS", "").split(",")
NOTIFY_ALL_ADMINS = os.getenv("NOTIFY_ALL_ADMINS", "false").lower() == "true"

# Frontend URLs
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
EMAIL_VERIFICATION_URL = os.getenv("EMAIL_VERIFICATION_URL", f"{FRONTEND_URL}/auth/verify-email")
PASSWORD_RESET_URL = os.getenv("PASSWORD_RESET_URL", f"{FRONTEND_URL}/auth/reset-password")

# Security
TOKEN_EXPIRATION_HOURS = int(os.getenv("TOKEN_EXPIRATION_HOURS", "24"))
