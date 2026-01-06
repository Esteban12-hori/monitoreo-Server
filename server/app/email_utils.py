import requests
import json
import logging
from .config import (
    EMAIL_API_KEY, EMAIL_API_SECRET, 
    EMAIL_SENDER_EMAIL, EMAIL_SENDER_NAME, 
    EMAIL_RECEIVERS, EMAIL_SUBJECT_PREFIX
)

logger = logging.getLogger(__name__)

def send_alert_email(server_id: str, alert_type: str, current_value: float, threshold: float):
    """
    Envía un correo de alerta usando Mailjet API v3.1.
    """
    if not EMAIL_API_KEY or not EMAIL_API_SECRET:
        logger.warning("Credenciales de email no configuradas. No se enviará alerta.")
        return

    subject = f"{EMAIL_SUBJECT_PREFIX} Alerta: {server_id} - {alert_type}"
    text_content = (
        f"Alerta en servidor {server_id}.\n"
        f"Tipo: {alert_type}\n"
        f"Valor actual: {current_value}\n"
        f"Umbral: {threshold}\n\n"
        f"Por favor verifique el estado del servidor."
    )
    
    html_content = (
        f"<h3>Alerta en servidor {server_id}</h3>"
        f"<p><strong>Tipo:</strong> {alert_type}</p>"
        f"<p><strong>Valor actual:</strong> {current_value}</p>"
        f"<p><strong>Umbral:</strong> {threshold}</p>"
        f"<br/>"
        f"<p>Por favor verifique el estado del servidor.</p>"
    )

    to_recipients = []
    # EMAIL_RECEIVERS es una lista de strings (gracias al .split(',') en config.py)
    for receiver in EMAIL_RECEIVERS:
        r = receiver.strip()
        if r:
            to_recipients.append({"Email": r, "Name": "Admin"})

    if not to_recipients:
        logger.warning("No hay destinatarios de correo configurados.")
        return

    # Estructura para Mailjet Send API v3.1
    payload = {
        "Messages": [
            {
                "From": {
                    "Email": EMAIL_SENDER_EMAIL,
                    "Name": EMAIL_SENDER_NAME
                },
                "To": to_recipients,
                "Subject": subject,
                "TextPart": text_content,
                "HTMLPart": html_content,
                "CustomID": f"AppAlert-{server_id}"
            }
        ]
    }
    
    url = "https://api.mailjet.com/v3.1/send"
    
    try:
        response = requests.post(
            url,
            auth=(EMAIL_API_KEY, EMAIL_API_SECRET),
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Email de alerta enviado para {server_id} ({alert_type})")
        else:
            logger.error(f"Error enviando email: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Excepción al enviar email: {e}")
