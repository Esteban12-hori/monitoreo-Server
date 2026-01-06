import requests
import json
import logging
from .config import (
    EMAIL_API_KEY, EMAIL_API_SECRET, 
    EMAIL_SENDER_EMAIL, EMAIL_SENDER_NAME, 
    EMAIL_RECEIVERS, EMAIL_SUBJECT_PREFIX
)

logger = logging.getLogger(__name__)

def send_alert_email(server_id: str, alert_type: str, current_value: float, threshold: float, extra_recipients: list = None, full_metrics: dict = None):
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
    
    metrics_html = ""
    if full_metrics:
        try:
            mem = full_metrics.get('memory', {})
            disk = full_metrics.get('disk', {})
            cpu = full_metrics.get('cpu', {})
            
            # Memoria (MB)
            mem_total = mem.get('total', 0)
            mem_used = mem.get('used', 0)
            mem_free = mem.get('free', 0)
            mem_pct = round((mem_used / mem_total * 100), 1) if mem_total > 0 else 0
            
            # Disco (GB)
            disk_total = disk.get('total', 0)
            disk_used = disk.get('used', 0)
            disk_free = disk.get('free', 0)
            disk_pct = disk.get('percent', 0)
            
            cpu_total = cpu.get('total', 0)
            
            metrics_html = f"""
            <br/>
            <hr/>
            <h4>Estado Actual de Recursos</h4>
            <table style="width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;">
                <tr style="background-color: #f2f2f2;">
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Recurso</th>
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Uso %</th>
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Usado / Total</th>
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Disponible</th>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>CPU</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{cpu_total}%</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">-</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">-</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>Memoria RAM</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{mem_pct}%</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{int(mem_used)} MB / {int(mem_total)} MB</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{int(mem_free)} MB</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>Disco</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{disk_pct}%</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{round(disk_used, 1)} GB / {round(disk_total, 1)} GB</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{round(disk_free, 1)} GB</td>
                </tr>
            </table>
            """
        except Exception as e:
            logger.error(f"Error generando tabla de métricas: {e}")

    html_content = (
        f"<h3>Alerta en servidor {server_id}</h3>"
        f"<p><strong>Tipo:</strong> {alert_type}</p>"
        f"<p><strong>Valor actual:</strong> {current_value}</p>"
        f"<p><strong>Umbral:</strong> {threshold}</p>"
        f"{metrics_html}"
        f"<br/>"
        f"<p>Por favor verifique el estado del servidor.</p>"
    )

    to_recipients = []
    # EMAIL_RECEIVERS es una lista de strings (gracias al .split(',') en config.py)
    for receiver in EMAIL_RECEIVERS:
        r = receiver.strip()
        if r:
            to_recipients.append({"Email": r, "Name": "Admin"})
            
    # Destinatarios extra (desde DB)
    if extra_recipients:
        for r in extra_recipients:
            to_recipients.append({"Email": r['email'], "Name": r.get('name', 'User')})

    # Eliminar duplicados
    unique = {}
    for r in to_recipients:
        unique[r['Email']] = r
    to_recipients = list(unique.values())

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
