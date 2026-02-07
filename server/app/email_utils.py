import requests
import json
import logging
from twilio.rest import Client
from .config import (
    EMAIL_API_KEY,
    EMAIL_API_SECRET,
    EMAIL_SENDER_EMAIL,
    EMAIL_SENDER_NAME,
    EMAIL_RECEIVERS,
    EMAIL_SUBJECT_PREFIX,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_VERIFY_SERVICE_SID,
    TWILIO_ALERT_PHONE,
    TWILIO_WHATSAPP_FROM,
    TWILIO_WHATSAPP_TO,
    TWILIO_WHATSAPP_CONTENT_SID,
)

logger = logging.getLogger(__name__)

def send_alert_email(server_id: str, alert_type: str, current_value: float, threshold: float, extra_recipients: list = None, full_metrics: dict = None):
    """
    Envía un correo de alerta usando Mailjet API v3.1.
    """
    if not EMAIL_API_KEY or not EMAIL_API_SECRET:
        logger.warning("Credenciales de email no configuradas. No se enviará alerta.")
        return

    subject = f"{EMAIL_SUBJECT_PREFIX} 🚨 {alert_type} en {server_id} ({current_value}%)"
    text_content = (
        f"🚨 ALERTA DE MONITOREO 🚨\n\n"
        f"Servidor: {server_id}\n"
        f"Problema: {alert_type}\n"
        f"Valor Actual: {current_value}%\n"
        f"Umbral Máximo: {threshold}%\n\n"
        f"Por favor verifique el servidor inmediatamente."
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
            <div style="margin-top: 25px;">
                <h4 style="margin-bottom: 15px; color: #444; font-size: 16px; border-bottom: 2px solid #eee; padding-bottom: 10px;">📊 Estado Actual de Recursos</h4>
                <table style="width: 100%; border-collapse: collapse; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; background-color: #fff; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden;">
                    <thead>
                        <tr style="background-color: #f8f9fa; color: #555;">
                            <th style="padding: 12px 15px; text-align: left; font-weight: 600; border-bottom: 1px solid #e0e0e0;">Recurso</th>
                            <th style="padding: 12px 15px; text-align: center; font-weight: 600; border-bottom: 1px solid #e0e0e0;">Uso %</th>
                            <th style="padding: 12px 15px; text-align: left; font-weight: 600; border-bottom: 1px solid #e0e0e0;">Detalle (Usado / Total)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 12px 15px; border-bottom: 1px solid #f0f0f0;"><strong>CPU</strong></td>
                            <td style="padding: 12px 15px; text-align: center; border-bottom: 1px solid #f0f0f0;">
                                <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; background-color: {'#ffebee' if cpu_total > 80 else '#e8f5e9'}; color: {'#c62828' if cpu_total > 80 else '#2e7d32'}; font-weight: bold; font-size: 13px;">
                                    {cpu_total}%
                                </span>
                            </td>
                            <td style="padding: 12px 15px; color: #666; border-bottom: 1px solid #f0f0f0;">-</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 15px; border-bottom: 1px solid #f0f0f0;"><strong>Memoria RAM</strong></td>
                            <td style="padding: 12px 15px; text-align: center; border-bottom: 1px solid #f0f0f0;">
                                <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; background-color: {'#ffebee' if mem_pct > 80 else '#e8f5e9'}; color: {'#c62828' if mem_pct > 80 else '#2e7d32'}; font-weight: bold; font-size: 13px;">
                                    {mem_pct}%
                                </span>
                            </td>
                            <td style="padding: 12px 15px; color: #666; border-bottom: 1px solid #f0f0f0;">
                                {int(mem_used)} MB / {int(mem_total)} MB
                                <div style="font-size: 12px; color: #999; margin-top: 2px;">Libre: {int(mem_free)} MB</div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 15px;"><strong>Disco</strong></td>
                            <td style="padding: 12px 15px; text-align: center;">
                                <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; background-color: {'#ffebee' if disk_pct > 80 else '#e8f5e9'}; color: {'#c62828' if disk_pct > 80 else '#2e7d32'}; font-weight: bold; font-size: 13px;">
                                    {disk_pct}%
                                </span>
                            </td>
                            <td style="padding: 12px 15px; color: #666;">
                                {round(disk_used, 1)} GB / {round(disk_total, 1)} GB
                                <div style="font-size: 12px; color: #999; margin-top: 2px;">Libre: {round(disk_free, 1)} GB</div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            """
        except Exception as e:
            logger.error(f"Error generando tabla de métricas: {e}")

    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
        <div style="background-color: #d32f2f; color: white; padding: 30px 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;">⚠️ {alert_type}</h1>
            <p style="margin: 10px 0 0; font-size: 16px; opacity: 0.9; font-weight: 400;">Servidor: <strong style="background-color: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px;">{server_id}</strong></p>
        </div>
        
        <div style="padding: 30px; background-color: #ffffff;">
            <div style="text-align: center; margin-bottom: 30px;">
                <p style="font-size: 16px; color: #555; margin-bottom: 15px;">Se ha detectado que el uso ha superado el umbral seguro.</p>
                <div style="display: inline-block; padding: 20px 40px; background-color: #fff5f5; border: 2px solid #d32f2f; border-radius: 12px;">
                    <span style="font-size: 36px; font-weight: 800; color: #d32f2f; display: block; line-height: 1;">{current_value}%</span>
                    <span style="display: block; font-size: 12px; color: #d32f2f; text-transform: uppercase; letter-spacing: 1px; margin-top: 8px; font-weight: 600;">Uso Actual</span>
                </div>
                <p style="font-size: 14px; color: #888; margin-top: 15px;">Umbral configurado: <strong>{threshold}%</strong></p>
            </div>

            {metrics_html}

            <div style="margin-top: 35px; text-align: center; border-top: 1px solid #eee; padding-top: 25px;">
                <p style="color: #666; font-size: 14px; margin-bottom: 5px;">Por favor, revise el servidor para evitar interrupciones.</p>
            </div>
        </div>
        <div style="background-color: #f9fafb; padding: 15px; text-align: center; font-size: 12px; color: #999; border-top: 1px solid #e0e0e0;">
            Enviado automáticamente por <strong>Monitoreo Server</strong>
        </div>
    </div>
    """

    to_recipients = []

    for receiver in EMAIL_RECEIVERS:
        r = receiver.strip()
        if r:
            to_recipients.append({"Email": r, "Name": "Admin"})

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


def send_offline_sms_alert(server_id: str, to_phone: str | None = None):
    """
    Envía un SMS urgente usando Twilio Verify cuando un servidor no responde.
    Usa las variables de entorno:
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_VERIFY_SERVICE_SID
    - TWILIO_ALERT_PHONE
    """
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID and TWILIO_ALERT_PHONE):
        logger.warning("Twilio no configurado correctamente. No se enviará SMS de servidor offline.")
        return

    to = to_phone or TWILIO_ALERT_PHONE

    url = f"https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/Verifications"
    data = {
        "To": to,
        "Channel": "sms",
    }

    try:
        resp = requests.post(url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
        if resp.status_code in (200, 201):
            logger.info(f"SMS de servidor offline enviado a {to} para {server_id}")
        else:
            logger.error(f"Error enviando SMS offline ({server_id}) {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Excepción al enviar SMS offline ({server_id}): {e}")


def send_whatsapp_twilio_alert(server_id: str, minutes_down: float, to_phone: str | None = None):
    """
    Envía un mensaje de WhatsApp usando Twilio (Content API) cuando un servidor no responde.
    Requiere:
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_WHATSAPP_FROM  (ej: whatsapp:+14155238886)
    - TWILIO_WHATSAPP_TO    (ej: whatsapp:+56966791438) si no se pasa to_phone
    - TWILIO_WHATSAPP_CONTENT_SID
    """
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM and TWILIO_WHATSAPP_CONTENT_SID):
        logger.warning("Twilio WhatsApp no configurado correctamente. No se enviará mensaje.")
        return

    to = to_phone or TWILIO_WHATSAPP_TO
    if not to:
        logger.warning("No se definió destinatario para WhatsApp Twilio.")
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        variables = {
            "1": server_id,
            "2": f"{minutes_down} minutos",
        }
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            content_sid=TWILIO_WHATSAPP_CONTENT_SID,
            content_variables=json.dumps(variables),
            to=to,
        )
        logger.info(f"WhatsApp Twilio enviado a {to} para {server_id}. SID={message.sid}")
    except Exception as e:
        logger.error(f"Excepción al enviar WhatsApp Twilio ({server_id}) a {to}: {e}")


def send_whatsapp_text(to_phone: str, body: str):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM):
        logger.warning("Twilio WhatsApp no configurado. No se enviará mensaje.")
        return
    to = to_phone
    if not to.startswith("whatsapp:"):
        to = "whatsapp:" + to
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=body,
            to=to,
        )
        logger.info(f"WhatsApp enviado a {to}. SID={message.sid}")
    except Exception as e:
        logger.error(f"Excepción al enviar WhatsApp a {to}: {e}")
