from pathlib import Path
import os

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