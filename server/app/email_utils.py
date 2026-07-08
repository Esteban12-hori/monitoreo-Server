import requests
import json
import logging
from datetime import datetime
from .config import (
    EMAIL_API_KEY,
    EMAIL_API_SECRET,
    EMAIL_SENDER_EMAIL,
    EMAIL_SENDER_NAME,
    EMAIL_RECEIVERS,
    EMAIL_SUBJECT_PREFIX,
)

logger = logging.getLogger(__name__)


def _has_connectivity() -> bool:
    try:
        resp = requests.get("https://api.mailjet.com", timeout=3)
        return resp.status_code < 500
    except Exception:
        logger.warning("Sin conectividad a internet; sistema en modo offline. No se enviará correo.")
        return False


def send_alert_email(server_id: str, alert_type: str, current_value: float, threshold: float, extra_recipients: list = None, full_metrics: dict = None, custom_message: str = None, environment: str = None, severity: str = None, is_recovery: bool = False):
    """
    Envía un correo de alerta usando Mailjet API v3.1.

    - environment: Ambiente del servidor (Producción / QA / Desarrollo).
    - severity: Nivel de severidad a mostrar (ADVERTENCIA / CRÍTICO / NORMALIZACIÓN).
    - is_recovery: Si es una notificación de normalización (colores en verde).
    """
    if not EMAIL_API_KEY or not EMAIL_API_SECRET:
        logger.warning("Credenciales de email no configuradas. No se enviará alerta.")
        return
    if not _has_connectivity():
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    accent = "#2e7d32" if is_recovery else "#d32f2f"
    header_icon = "✅" if is_recovery else "🚨"

    subject_icon = "✅" if is_recovery else "🚨"
    subject = f"{EMAIL_SUBJECT_PREFIX} {subject_icon} {alert_type} en {server_id}"
    if not custom_message:
        subject += f" ({current_value}%)"

    if custom_message:
        text_content = (
            f"{header_icon} {'NORMALIZACIÓN' if is_recovery else 'ALERTA'} DE MONITOREO {header_icon}\n\n"
            f"Servidor: {server_id}\n"
            f"Ambiente: {environment or '-'}\n"
            f"Fecha y hora: {now_str}\n"
            f"Severidad: {severity or ('NORMALIZACIÓN' if is_recovery else '-')}\n"
            f"Tipo: {alert_type}\n"
            f"Detalle: {custom_message}\n\n"
            f"{'El servidor volvió a niveles normales.' if is_recovery else 'Por favor verifique el servidor inmediatamente.'}"
        )
        html_content = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            <div style="background-color: #d32f2f; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px; font-weight: 600;">🚨 ALERTA DE MONITOREO</h1>
            </div>
            
            <div style="padding: 30px; background-color: #ffffff;">
                <div style="background-color: #fff8f8; border-left: 4px solid #d32f2f; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                    <p style="margin: 0; color: #d32f2f; font-weight: bold; font-size: 18px;">{alert_type}</p>
                    <p style="margin: 5px 0 0; color: #555;">{custom_message}</p>
                </div>
                
                <table style="width: 100%; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 140px;"><strong>Servidor:</strong></td>
                        <td style="padding: 8px 0; color: #333; font-weight: 500;">{server_id}</td>
                    </tr>
                </table>
        """
    else:
        text_content = (
            f"{header_icon} {'NORMALIZACIÓN' if is_recovery else 'ALERTA'} DE MONITOREO {header_icon}\n\n"
            f"Servidor: {server_id}\n"
            f"Ambiente: {environment or '-'}\n"
            f"Fecha y hora: {now_str}\n"
            f"Severidad: {severity or ('NORMALIZACIÓN' if is_recovery else '-')}\n"
            f"Problema: {alert_type}\n"
            f"Valor Actual: {current_value}%\n"
            f"Umbral: {threshold}%\n\n"
            f"{'El servidor volvió a niveles normales.' if is_recovery else 'Por favor verifique el servidor inmediatamente.'}"
        )
        html_content = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            <div style="background-color: #d32f2f; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px; font-weight: 600;">🚨 ALERTA DE MONITOREO</h1>
            </div>
            
            <div style="padding: 30px; background-color: #ffffff;">
                <div style="background-color: #fff8f8; border-left: 4px solid #d32f2f; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                    <p style="margin: 0; color: #d32f2f; font-weight: bold; font-size: 18px;">{alert_type}</p>
                    <p style="margin: 5px 0 0; color: #555;">El valor actual ha superado el umbral permitido.</p>
                </div>
                
                <table style="width: 100%; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 140px;"><strong>Servidor:</strong></td>
                        <td style="padding: 8px 0; color: #333; font-weight: 500;">{server_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Valor Actual:</strong></td>
                        <td style="padding: 8px 0; color: #d32f2f; font-weight: bold; font-size: 16px;">{current_value}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Umbral Máximo:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{threshold}%</td>
                    </tr>
                </table>
        """
    metrics_html = ""
    if full_metrics:
        try:
            mem = full_metrics.get('memory', {})
            disk = full_metrics.get('disk', {})
            cpu = full_metrics.get('cpu', {})
            swap = full_metrics.get('swap') or {}

            mem_total = mem.get('total', 0)
            mem_used = mem.get('used', 0)
            mem_free = mem.get('free', 0)
            mem_pct = round((mem_used / mem_total * 100), 1) if mem_total > 0 else 0

            disk_total = disk.get('total', 0)
            disk_used = disk.get('used', 0)
            disk_free = disk.get('free', 0)
            disk_pct = disk.get('percent', 0)

            cpu_total = cpu.get('total', 0)

            swap_total = swap.get('total', 0) or 0
            swap_used = swap.get('used', 0) or 0
            swap_free = swap.get('free', 0) or 0
            swap_pct = swap.get('percent', 0) or 0
            if not swap_pct and swap_total > 0:
                swap_pct = round((swap_used / swap_total * 100), 1)
            swap_row = ""
            if swap_total > 0:
                swap_row = f"""
                        <tr>
                            <td style="padding: 12px 15px; border-top: 1px solid #f0f0f0;"><strong>Swap</strong></td>
                            <td style="padding: 12px 15px; text-align: center; border-top: 1px solid #f0f0f0;">
                                <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; background-color: {'#ffebee' if swap_pct > 80 else '#e8f5e9'}; color: {'#c62828' if swap_pct > 80 else '#2e7d32'}; font-weight: bold; font-size: 13px;">
                                    {round(swap_pct, 1)}%
                                </span>
                            </td>
                            <td style="padding: 12px 15px; color: #666; border-top: 1px solid #f0f0f0;">
                                {int(swap_used)} MB / {int(swap_total)} MB
                                <div style="font-size: 12px; color: #999; margin-top: 2px;">Libre: {int(swap_free)} MB</div>
                            </td>
                        </tr>"""
            
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
                        </tr>{swap_row}
                    </tbody>
                </table>
            </div>
            """
        except Exception as e:
            logger.error(f"Error generando tabla de métricas: {e}")

    intro_text = (
        "El uso ha vuelto a niveles normales." if is_recovery
        else "Se ha detectado que el uso ha superado el umbral seguro."
    )
    env_display = environment or "-"
    severity_display = severity or ("NORMALIZACIÓN" if is_recovery else "-")

    meta_html = f"""
                <table style="width: 100%; margin: 0 auto 20px; max-width: 420px; text-align: left;">
                    <tr>
                        <td style="padding: 6px 0; color: #666; width: 130px;"><strong>Ambiente:</strong></td>
                        <td style="padding: 6px 0; color: #333;">{env_display}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;"><strong>Fecha y hora:</strong></td>
                        <td style="padding: 6px 0; color: #333;">{now_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;"><strong>Severidad:</strong></td>
                        <td style="padding: 6px 0; color: {accent}; font-weight: bold;">{severity_display}</td>
                    </tr>
                </table>
    """

    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
        <div style="background-color: {accent}; color: white; padding: 30px 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.5px;">{header_icon} {alert_type}</h1>
            <p style="margin: 10px 0 0; font-size: 16px; opacity: 0.9; font-weight: 400;">Servidor: <strong style="background-color: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px;">{server_id}</strong></p>
        </div>

        <div style="padding: 30px; background-color: #ffffff;">
            <div style="text-align: center; margin-bottom: 30px;">
                <p style="font-size: 16px; color: #555; margin-bottom: 15px;">{intro_text}</p>
                <div style="display: inline-block; padding: 20px 40px; background-color: {'#f1f8f2' if is_recovery else '#fff5f5'}; border: 2px solid {accent}; border-radius: 12px;">
                    <span style="font-size: 36px; font-weight: 800; color: {accent}; display: block; line-height: 1;">{current_value}%</span>
                    <span style="display: block; font-size: 12px; color: {accent}; text-transform: uppercase; letter-spacing: 1px; margin-top: 8px; font-weight: 600;">Uso Actual</span>
                </div>
                <p style="font-size: 14px; color: #888; margin-top: 15px;">Umbral configurado: <strong>{threshold}%</strong></p>
            </div>

            {meta_html}

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
            
    if extra_recipients:
        for r in extra_recipients:
             # extra_recipients might be list of strings or dicts depending on caller
             # Assuming list of strings based on AlertRule logic
             if isinstance(r, str):
                 to_recipients.append({"Email": r, "Name": "Recipient"})
             elif isinstance(r, dict) and "Email" in r:
                 to_recipients.append(r)

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
