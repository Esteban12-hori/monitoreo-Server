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
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY", "")
EMAIL_API_SECRET = os.getenv("EMAIL_API_SECRET", "")
EMAIL_SENDER_EMAIL = os.getenv("EMAIL_SENDER_EMAIL", "")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS", "").split(",") if os.getenv("EMAIL_RECEIVERS") else []

# Tema de los correos (Subject Prefix)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[Monitoreo]")
