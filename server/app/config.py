from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "monitor.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_ALERTS = {
    "cpu_total_percent": 90.0,
    "memory_used_percent": 90.0,
    "disk_used_percent": 90.0,
}

ALLOWED_ORIGINS = ["*"]

DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

CACHE_MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "500"))

ALLOWED_USERS = {
    "rlarenas@wingsoft.com": {"name": "Ramiro Larenas", "password": "q0<>E55NV"},
    "jguajardo@wingsoft.com": {"name": "Joaquín Guajardo", "password": "Pombolita1"},
}

SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_TLS = os.getenv("SMTP_TLS", "True").lower() == "true"

EMAIL_API_KEY = os.getenv("EMAIL_API_KEY", "4cc4901cb8203fb46673d8e641d947b6")
EMAIL_API_SECRET = os.getenv("EMAIL_API_SECRET", "3c394600895a3466ab0b5aba092ed91d")
EMAIL_SENDER_EMAIL = os.getenv("EMAIL_SENDER_EMAIL", "developer@wingsoft.com")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "DevOps Wingsoft")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS", "jguajardo@wingsoft.com").split(",")

EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[Monitoreo]")

OFFLINE_CHECK_INTERVAL = int(os.getenv("OFFLINE_CHECK_INTERVAL", "60"))
OFFLINE_MULTIPLIER = float(os.getenv("OFFLINE_MULTIPLIER", "3"))
OFFLINE_MIN_SECONDS = int(os.getenv("OFFLINE_MIN_SECONDS", "300"))

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_SESSION_TTL_MINUTES = int(os.getenv("WHATSAPP_SESSION_TTL_MINUTES", "30"))
WHATSAPP_FREE_MAX_SERVERS = int(os.getenv("WHATSAPP_FREE_MAX_SERVERS", "3"))
WHATSAPP_FAVORITE_SERVERS = os.getenv("WHATSAPP_FAVORITE_SERVERS", "")

APP_ENV = os.getenv("APP_ENV", "development")
IS_PRODUCTION = APP_ENV.lower() == "production"

AGENT_LATEST_VERSION = os.getenv("AGENT_LATEST_VERSION", "1.0.0")
