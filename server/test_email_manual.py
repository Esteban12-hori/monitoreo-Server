import sys
import os
import logging
from pathlib import Path

# Configure logging to show info
logging.basicConfig(level=logging.INFO)

# Add the parent directory to sys.path to allow importing from app
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.email_utils import send_alert_email
from app.config import EMAIL_API_KEY, EMAIL_SENDER_EMAIL

print("--- Iniciando prueba de envío de correo ---")
print(f"API KEY: {EMAIL_API_KEY[:4]}...{EMAIL_API_KEY[-4:] if EMAIL_API_KEY else 'None'}")
print(f"Sender: {EMAIL_SENDER_EMAIL}")

try:
    print("Enviando correo de prueba...")
    send_alert_email("TEST-SERVER", "Prueba de Configuración", 100, 90)
    print("Función ejecutada. Verifique los logs o la bandeja de entrada.")
except Exception as e:
    print(f"Error al ejecutar la prueba: {e}")
