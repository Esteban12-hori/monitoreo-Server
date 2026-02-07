from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "monitor.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_ALERTS = {
    "cpu_total_percent": 90.0,
    "memory_used_percent": 90.0,
    "disk_used_percent": 90.0,
}

ALLOWED_ORIGINS = ["*"]

# Token para proteger endpoints de lectura del dashboard.
# Si está vacío, los endpoints son públicos.
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

# Configuración de caché en memoria para métricas recientes
CACHE_MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "500"))

# Usuarios permitidos para autenticación básica (email -> {name, password})
# Nota: Para producción, use almacenamiento seguro y hash de contraseñas.
ALLOWED_USERS = {
    "rlarenas@wingsoft.com": {"name": "Ramiro Larenas", "password": "q0<>E55NV"},
    "jguajardo@wingsoft.com": {"name": "Joaquín Guajardo", "password": "Pombolita1"},
}

# Configuración de Email (SMTP)
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_TLS = os.getenv("SMTP_TLS", "True").lower() == "true"

# Configuración de Email (API)
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY", "4cc4901cb8203fb46673d8e641d947b6")
EMAIL_API_SECRET = os.getenv("EMAIL_API_SECRET", "3c394600895a3466ab0b5aba092ed91d")
EMAIL_SENDER_EMAIL = os.getenv("EMAIL_SENDER_EMAIL", "developer@wingsoft.com")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "DevOps Wingsoft")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS", "jguajardo@wingsoft.com").split(",")

# Tema de los correos (Subject Prefix)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[Monitoreo]")

# Configuración Twilio para SMS urgentes
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")
TWILIO_ALERT_PHONE = os.getenv("TWILIO_ALERT_PHONE", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
TWILIO_WHATSAPP_TO = os.getenv("TWILIO_WHATSAPP_TO", "")
TWILIO_WHATSAPP_CONTENT_SID = os.getenv("TWILIO_WHATSAPP_CONTENT_SID", "")

# Configuración de monitoreo de servidores offline
OFFLINE_CHECK_INTERVAL = int(os.getenv("OFFLINE_CHECK_INTERVAL", "60"))  # cada cuánto revisar (segundos)
OFFLINE_MULTIPLIER = float(os.getenv("OFFLINE_MULTIPLIER", "3"))         # múltiplo del report_interval
OFFLINE_MIN_SECONDS = int(os.getenv("OFFLINE_MIN_SECONDS", "300"))       # mínimo en segundos antes de considerar offline

# Configuración de WhatsApp Business (Cloud API)
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

# Configuración JWT para autenticación de integraciones (p.ej., WhatsApp)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
