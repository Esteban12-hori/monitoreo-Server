import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import uuid
import unicodedata
import io
import csv
import logging
import html

import requests

from fastapi import FastAPI, HTTPException, Header, Depends, status, Request, Response, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import create_engine, select, delete, text
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel, Field

from .config import (
    DB_PATH,
    DEFAULT_ALERTS,
    ALLOWED_ORIGINS,
    DASHBOARD_TOKEN,
    CACHE_MAX_ITEMS,
    ALLOWED_USERS,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_VERIFY_TOKEN,
    WHATSAPP_SESSION_TTL_MINUTES,
    WHATSAPP_FREE_MAX_SERVERS,
    WHATSAPP_FAVORITE_SERVERS,
)
from .models import Base, Server, Metric, AlertConfig, User, UserSession, AlertRecipient, AlertRule, ServerThreshold, AuditLog, UserServerLink, DataMonitoring, DataMonitoringServerConfig, DataMonitoringUserConfig, ServerGroup, AgentCommand
from .schemas import (
    MetricsIngestSchema, RegisterServerSchema, AlertConfigSchema, LoginSchema,
    UserCreateSchema, UserResponseSchema, ChangePasswordSchema,
    ServerConfigUpdateSchema, AlertRecipientSchema, AlertRecipientCreateSchema,
    ServerAssignmentSchema, AlertRuleCreate, AlertRuleResponse, ServerUpdateGroupSchema,
    ServerThresholdResponse, ServerThresholdUpdate, AuditLogResponse, ServerThresholdImport,
    ServerDataMonitoringUpdateSchema,
    UserUpdateSchema, UserServerAssignmentResponse, DataMonitoringSchema, DataMonitoringResponseSchema,
    ServerGroupSchema, ServerGroupCreateSchema, ServiceSchema, AgentCommandResponse, ServiceActionSchema,
    BulkServiceActionSchema, SidebarConfigUpdateSchema
)
from .email_utils import send_alert_email
import time
import asyncio
import jwt

logger = logging.getLogger("whatsapp-bot")

# Configuración de Passlib para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_engine():
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    return engine

engine = get_engine()
Base.metadata.create_all(engine)

app = FastAPI(title="Monitor Integral")

class WhatsAppSessionState:
    INICIO = "inicio"
    PIDIENDO_EMAIL = "pidiendo_email"
    PIDIENDO_PASSWORD = "pidiendo_password"
    MENU_PRINCIPAL = "menu_principal"
    VIENDO_SERVIDOR = "viendo_servidor"


class WhatsAppSessionData(dict):
    pass


_wa_sessions: Dict[str, WhatsAppSessionData] = {}
_wa_favorite_server_ids = {
    s.strip() for s in (WHATSAPP_FAVORITE_SERVERS or "").split(",") if s.strip()
}


def _wa_get_session(wa_id: str) -> WhatsAppSessionData:
    now = datetime.utcnow()
    sess = _wa_sessions.get(wa_id)
    if not sess:
        sess = WhatsAppSessionData(
            wa_id=wa_id,
            state=WhatsAppSessionState.INICIO,
            created_at=now.isoformat(),
            last_activity=now.isoformat(),
        )
        _wa_sessions[wa_id] = sess
        return sess
    try:
        last = datetime.fromisoformat(sess.get("last_activity"))
        delta = now - last
        if delta.total_seconds() > WHATSAPP_SESSION_TTL_MINUTES * 60:
            sess = WhatsAppSessionData(
                wa_id=wa_id,
                state=WhatsAppSessionState.INICIO,
                created_at=now.isoformat(),
                last_activity=now.isoformat(),
            )
            _wa_sessions[wa_id] = sess
            return sess
    except Exception:
        sess["created_at"] = now.isoformat()
    sess["last_activity"] = now.isoformat()
    return sess


def _wa_reset_session(wa_id: str):
    if wa_id in _wa_sessions:
        del _wa_sessions[wa_id]


def _wa_send_messages(to: str, lines: List[str]) -> None:
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp credentials not configured; skipping send")
        return
    body_text = "\n".join(lines).strip()
    if not body_text:
        return
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": body_text},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code >= 400:
            logger.error(
                "Error sending WhatsApp message: %s %s",
                resp.status_code,
                resp.text,
            )
    except Exception as exc:
        logger.error("Exception sending WhatsApp message: %s", exc)


def _wa_format_cpu_bar(percent: float) -> str:
    try:
        value = max(0.0, min(100.0, float(percent or 0)))
    except Exception:
        value = 0.0
    total_blocks = 20
    filled = int(round(value / 100.0 * total_blocks))
    empty = total_blocks - filled
    return "█" * filled + "░" * empty


def _wa_list_servers_for_user(user_id: int) -> List[Dict[str, Any]]:
    with Session(engine) as sess:
        configs = sess.execute(select(DataMonitoringServerConfig)).scalars().all()
        cfg_map = {c.server_id: c.enabled for c in configs}
        db_user = sess.get(User, user_id)
        if not db_user:
            return []
        results: List[Dict[str, Any]] = []
        if db_user and not db_user.is_admin:
            for link in db_user.server_links:
                if link.server:
                    results.append(
                        {
                            "server_id": link.server.server_id,
                            "group_name": link.server.group_name,
                            "data_monitoring_enabled": cfg_map.get(link.server.server_id, False),
                        }
                    )
        else:
            servers = sess.execute(select(Server)).scalars().all()
            for s in servers:
                results.append(
                    {
                        "server_id": s.server_id,
                        "group_name": s.group_name,
                        "data_monitoring_enabled": cfg_map.get(s.server_id, False),
                    }
                )
        return results


def _wa_get_latest_metrics(server_id: str) -> Optional[Dict[str, Any]]:
    if server_id in _cache and _cache[server_id]:
        return _cache[server_id][-1]
    with Session(engine) as sess:
        row = (
            sess.execute(
                select(Metric)
                .where(Metric.server_id == server_id)
                .order_by(Metric.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if not row:
            return None
        return {
            "server_id": row.server_id,
            "ts": str(row.ts),
            "memory": {
                "total": row.mem_total,
                "used": row.mem_used,
                "free": row.mem_free,
                "cache": row.mem_cache,
            },
            "cpu": {
                "total": row.cpu_total,
                "per_core": json.loads(row.cpu_per_core or "[]"),
            },
            "disk": {
                "total": row.disk_total,
                "used": row.disk_used,
                "free": row.disk_free,
                "percent": row.disk_percent,
            },
            "docker": {
                "running_containers": row.docker_running,
                "containers": json.loads(row.docker_containers or "[]"),
            },
            "services": json.loads(row.services or "[]"),
        }


def _wa_compute_uptime(server_id: str) -> Optional[str]:
    with Session(engine) as sess:
        first = (
            sess.execute(
                select(Metric)
                .where(Metric.server_id == server_id)
                .order_by(Metric.id.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        last = (
            sess.execute(
                select(Metric)
                .where(Metric.server_id == server_id)
                .order_by(Metric.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if not first or not last:
            return None
        delta = (last.ts - first.ts).total_seconds()
    if delta <= 0:
        return None
    days = int(delta // 86400)
    hours = int((delta % 86400) // 3600)
    minutes = int((delta % 3600) // 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def _wa_build_alerts_summary(server_id: str, metrics: Dict[str, Any]) -> List[str]:
    alerts: List[str] = []
    with Session(engine) as sess:
        cfg = sess.execute(select(AlertConfig)).scalar_one_or_none()
        thr = sess.execute(
            select(ServerThreshold).where(ServerThreshold.server_id == server_id)
        ).scalar_one_or_none()
        if not cfg:
            return []
        cpu_thr = thr.cpu_threshold if thr and thr.cpu_threshold is not None else cfg.cpu_total_percent
        mem_thr = (
            thr.memory_threshold
            if thr and thr.memory_threshold is not None
            else cfg.memory_used_percent
        )
        disk_thr = (
            thr.disk_threshold
            if thr and thr.disk_threshold is not None
            else cfg.disk_used_percent
        )
    cpu_val = (metrics.get("cpu") or {}).get("total") or 0
    mem = metrics.get("memory") or {}
    mem_total = mem.get("total") or 0
    mem_used = mem.get("used") or 0
    mem_pct = (mem_used / mem_total * 100.0) if mem_total else 0
    disk = metrics.get("disk") or {}
    disk_pct = disk.get("percent") or 0
    if cpu_val >= cpu_thr:
        alerts.append(f"CPU alta: {cpu_val:.1f}% (umbral {cpu_thr:.1f}%)")
    if mem_pct >= mem_thr:
        alerts.append(f"Memoria alta: {mem_pct:.1f}% (umbral {mem_thr:.1f}%)")
    if disk_pct >= disk_thr:
        alerts.append(f"Disco alto: {disk_pct:.1f}% (umbral {disk_thr:.1f}%)")
    return alerts


def _wa_show_server_metrics(sess: WhatsAppSessionData, server_id: str) -> List[str]:
    metrics = _wa_get_latest_metrics(server_id)
    if not metrics:
        return [
            f"No hay métricas recientes para el servidor {server_id}.",
            "Asegúrate de que el agente esté reportando correctamente.",
            "Envía 0 para volver al menú principal.",
        ]
    cpu = metrics.get("cpu") or {}
    disk = metrics.get("disk") or {}
    mem = metrics.get("memory") or {}
    services = metrics.get("services") or []
    cpu_val = cpu.get("total") or 0
    cpu_bar = _wa_format_cpu_bar(cpu_val)
    mem_total = mem.get("total") or 0
    mem_used = mem.get("used") or 0
    mem_free = mem.get("free") or 0
    disk_total = disk.get("total") or 0
    disk_used = disk.get("used") or 0
    disk_free = disk.get("free") or 0
    disk_pct = disk.get("percent") or 0
    uptime = _wa_compute_uptime(server_id)
    problematic_services = [s for s in services if s.get("status") != "running"]
    svc_lines: List[str] = []
    if problematic_services:
        for s in problematic_services[:5]:
            name = s.get("display_name") or s.get("name")
            status = s.get("status")
            svc_lines.append(f"- {name}: {status}")
        if len(problematic_services) > 5:
            svc_lines.append(f"... y {len(problematic_services) - 5} servicios más con problemas.")
    else:
        svc_lines.append("Todos los servicios reportan estado 'running'.")
    alerts = _wa_build_alerts_summary(server_id, metrics)
    alert_lines: List[str] = []
    if alerts:
        alert_lines.append("⚠️ Alertas activas:")
        alert_lines.extend(f"- {a}" for a in alerts)
    else:
        alert_lines.append("✅ Sin alertas activas según umbrales configurados.")
    ts = metrics.get("ts")
    lines: List[str] = []
    lines.append(f"📊 Estado de {server_id}")
    if ts:
        lines.append(f"Última muestra: {ts}")
    lines.append("")
    lines.append(f"CPU: {cpu_val:.1f}%")
    lines.append(cpu_bar)
    lines.append("")
    lines.append(
        f"Memoria: {mem_used:.1f}/{mem_total:.1f} MB (libre {mem_free:.1f} MB)"
    )
    lines.append(
        f"Disco: {disk_used:.1f}/{disk_total:.1f} GB usados ({disk_pct:.1f}%)"
    )
    if uptime:
        lines.append(f"Tiempo de actividad estimado: {uptime}")
    lines.append("")
    lines.append("Servicios críticos:")
    lines.extend(svc_lines)
    lines.append("")
    lines.extend(alert_lines)
    lines.append("")
    lines.append("Opciones:")
    lines.append("1. Refrescar métricas")
    lines.append("0. Volver al menú principal")
    with Session(engine) as db:
        try:
            db.add(
                AuditLog(
                    action="whatsapp_view_metrics",
                    target_type="server",
                    target_id=server_id,
                    changes=json.dumps({"wa_id": sess.get("wa_id")}),
                    user_email=sess.get("user_email"),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
    return lines


def _wa_build_main_menu(sess: WhatsAppSessionData) -> List[str]:
    user_id = sess.get("user_id")
    if not user_id:
        sess["state"] = WhatsAppSessionState.INICIO
        return [
            "No encuentro una sesión activa ahora mismo.",
            "Envía tu correo de acceso para iniciar de nuevo.",
        ]
    servers = _wa_list_servers_for_user(int(user_id))
    pinned = [s for s in servers if s["server_id"] in _wa_favorite_server_ids]
    others = [s for s in servers if s["server_id"] not in _wa_favorite_server_ids]
    ordered = pinned + others
    limited = False
    visible_servers = ordered
    if WHATSAPP_FREE_MAX_SERVERS and len(ordered) > WHATSAPP_FREE_MAX_SERVERS:
        visible_servers = ordered[:WHATSAPP_FREE_MAX_SERVERS]
        limited = True
    sess["servers_menu"] = visible_servers
    lines: List[str] = []
    lines.append("📋 Estos son los servidores disponibles para tu usuario:")
    if not visible_servers:
        lines.append("(No tienes servidores asignados todavía.)")
    else:
        for idx, srv in enumerate(visible_servers, start=1):
            label = srv["server_id"]
            if srv["server_id"] in _wa_favorite_server_ids:
                label = f"⭐ {label}"
            if srv.get("group_name"):
                label = f"{label} ({srv['group_name']})"
            lines.append(f"{idx}. {label}")
    lines.append("")
    lines.append("Responde con el número del servidor para ver sus métricas.")
    lines.append("Escribe 0 para refrescar este menú.")
    lines.append("Escribe CAMBIAR USUARIO para iniciar sesión con otra cuenta.")
    if limited:
        lines.append("")
        lines.append(
            f"Versión gratuita: se muestran solo los primeros {WHATSAPP_FREE_MAX_SERVERS} servidores."
        )
        lines.append("Para ver el resto, entra al panel web o consulta la versión completa.")
    with Session(engine) as db:
        try:
            db.add(
                AuditLog(
                    action="whatsapp_menu",
                    target_type="whatsapp",
                    target_id=sess.get("wa_id"),
                    changes=json.dumps(
                        {"servers": [s.get("server_id") for s in servers]}
                    ),
                    user_email=sess.get("user_email"),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
    return lines


def handle_whatsapp_conversation(wa_id: str, text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return [
            "No he recibido ningún texto.",
            "Envía un saludo (por ejemplo, hola) o una opción del menú.",
        ]
    upper = raw.upper()
    if upper == "CAMBIAR USUARIO":
        sess = _wa_get_session(wa_id)
        with Session(engine) as db:
            try:
                db.add(
                    AuditLog(
                        action="whatsapp_logout",
                        target_type="user",
                        target_id=str(sess.get("user_id")),
                        changes=json.dumps({"wa_id": wa_id}),
                        user_email=sess.get("user_email"),
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
        _wa_reset_session(wa_id)
        return [
            "Has cerrado sesión.",
            "Envía tu correo de acceso para iniciar sesión con otro usuario.",
        ]
    sess = _wa_get_session(wa_id)
    state = sess.get("state", WhatsAppSessionState.INICIO)
    norm = _norm(raw)
    greeting_triggers = {
        "hola",
        "hi",
        "hello",
        "buenas",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
    }
    if norm in greeting_triggers:
        if not sess.get("user_id"):
            sess["state"] = WhatsAppSessionState.PIDIENDO_EMAIL
            return [
                "👋 Hola, bienvenido al monitoreo de servidores de Wingsoft.",
                "Te ayudo a revisar el estado de tus servidores desde aquí.",
                "Para empezar, envía el correo que usas en el monitor (ej: usuario@empresa.com).",
                "En cualquier momento puedes escribir CAMBIAR USUARIO para entrar con otra cuenta.",
            ]
        sess["state"] = WhatsAppSessionState.MENU_PRINCIPAL
        return _wa_build_main_menu(sess)
    if state == WhatsAppSessionState.INICIO:
        sess["state"] = WhatsAppSessionState.PIDIENDO_EMAIL
        return [
            "👋 Hola, bienvenido al monitoreo de servidores de Wingsoft.",
            "Te ayudo a revisar el estado de tus servidores desde aquí.",
            "Para empezar, envía el correo que usas en el monitor (ej: usuario@empresa.com).",
            "En cualquier momento puedes escribir CAMBIAR USUARIO para entrar con otra cuenta.",
        ]
    if state == WhatsAppSessionState.PIDIENDO_EMAIL:
        sess["pending_email"] = raw
        sess["state"] = WhatsAppSessionState.PIDIENDO_PASSWORD
        return [
            f"✅ Correo recibido: {raw}",
            "🔒 Ahora envía tu contraseña de acceso al monitor.",
            "Solo tú ves estos datos; si te equivocas podrás intentarlo de nuevo.",
        ]
    if state == WhatsAppSessionState.PIDIENDO_PASSWORD:
        email = sess.get("pending_email")
        if not email:
            sess["state"] = WhatsAppSessionState.PIDIENDO_EMAIL
            return [
                "No tengo registrado tu correo.",
                "Por favor envía primero tu correo de acceso.",
            ]
        try:
            login_data = perform_login(email, raw)
        except HTTPException:
            return [
                "❌ Credenciales inválidas.",
                "Revisa tu correo y contraseña e inténtalo nuevamente.",
                "Envía de nuevo tu contraseña o escribe CAMBIAR USUARIO para usar otra cuenta.",
            ]
        sess["state"] = WhatsAppSessionState.MENU_PRINCIPAL
        sess["user_email"] = login_data["email"]
        sess["user_name"] = login_data["name"]
        sess["dashboard_token"] = login_data["token"]
        sess["user_id"] = login_data["user_id"]
        with Session(engine) as db:
            try:
                db.add(
                    AuditLog(
                        action="whatsapp_login",
                        target_type="user",
                        target_id=str(login_data["user_id"]),
                        changes=json.dumps({"wa_id": wa_id}),
                        user_email=login_data["email"],
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
        return _wa_build_main_menu(sess)
    if state == WhatsAppSessionState.MENU_PRINCIPAL:
        if raw == "0":
            return _wa_build_main_menu(sess)
        if raw.isdigit():
            idx = int(raw)
            servers = sess.get("servers_menu") or []
            if 1 <= idx <= len(servers):
                srv = servers[idx - 1]
                sess["state"] = WhatsAppSessionState.VIENDO_SERVIDOR
                sess["selected_server_id"] = srv["server_id"]
                return _wa_show_server_metrics(sess, srv["server_id"])
            return [
                "No reconozco esa opción.",
                "Envía un número de la lista o 0 para refrescar el menú.",
            ]
        return [
            "No he podido entender esa opción.",
            "Envía un número de servidor, 0 para menú o CAMBIAR USUARIO.",
        ]
    if state == WhatsAppSessionState.VIENDO_SERVIDOR:
        if raw == "0":
            sess["state"] = WhatsAppSessionState.MENU_PRINCIPAL
            return _wa_build_main_menu(sess)
        if raw == "1":
            server_id = sess.get("selected_server_id")
            if not server_id:
                sess["state"] = WhatsAppSessionState.MENU_PRINCIPAL
                return _wa_build_main_menu(sess)
            return _wa_show_server_metrics(sess, server_id)
        return [
            "Opciones:",
            "1. Refrescar métricas del servidor actual",
            "0. Volver al menú principal",
        ]
    sess["state"] = WhatsAppSessionState.INICIO
    return [
        "Estado interno inválido, reiniciando conversación.",
        "Envía tu correo de acceso para comenzar.",
    ]


@app.get("/api/whatsapp/webhook")
def whatsapp_verify(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN and challenge:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    try:
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", []) or []
                for msg in messages:
                    from_id = msg.get("from")
                    if not from_id:
                        continue
                    msg_type = msg.get("type")
                    text = None
                    if msg_type == "text":
                        text = (msg.get("text") or {}).get("body")
                    elif msg_type == "button":
                        text = (msg.get("button") or {}).get("text")
                    if text is None:
                        continue
                    replies = handle_whatsapp_conversation(from_id, text)
                    if replies:
                        _wa_send_messages(from_id, replies)
        return {"status": "ok"}
    except Exception:
        logger.exception("Error processing WhatsApp webhook")
        raise HTTPException(status_code=500, detail="Error processing webhook")


@app.post("/api/twilio/whatsapp/webhook")
async def twilio_whatsapp_webhook(request: Request):
    try:
        form = await request.form()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form payload")
    from_number = form.get("From") or ""
    body = form.get("Body") or ""
    wa_id = from_number.replace("whatsapp:", "") if from_number else "unknown"
    replies = handle_whatsapp_conversation(wa_id, body)
    text = "\n".join(replies) if replies else "No hay respuesta disponible."
    escaped = html.escape(text)
    twiml = f"<Response><Message>{escaped}</Message></Response>"
    return Response(content=twiml, media_type="application/xml")


# --- Rate Limiting Setup ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# --- Security Middlewares ---
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "::1", "*"]
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:;"
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def ensure_default_alerts(sess: Session):
    # Usamos scalars().first() para evitar error si hay múltiples (aunque no debería)
    cfg = sess.execute(select(AlertConfig)).scalars().first()
    if not cfg:
        cfg = AlertConfig(
            cpu_total_percent=DEFAULT_ALERTS["cpu_total_percent"],
            memory_used_percent=DEFAULT_ALERTS["memory_used_percent"],
            disk_used_percent=DEFAULT_ALERTS["disk_used_percent"],
        )
        sess.add(cfg)
        sess.commit()

def ensure_default_users(sess: Session):
    # Sincronizar usuarios permitidos desde config
    print("Verificando usuarios por defecto...")
    try:
        for email, info in ALLOWED_USERS.items():
            # Usamos scalars().first() para ser más robustos
            user = sess.execute(select(User).where(User.email == email)).scalars().first()
            if user:
                # Opcional: Actualizar contraseña si se desea forzar desde config
                current_hash = user.password_hash
                if not verify_password(info["password"], current_hash):
                    print(f"Actualizando contraseña para {email}")
                    user.password_hash = get_password_hash(info["password"])
                
                if not user.is_admin:
                    user.is_admin = True
                
                # Importante: flush aquí para evitar conflictos si se agrega más lógica
                sess.flush()
            else:
                print(f"Creando usuario por defecto: {email}")
                user = User(
                    email=email,
                    name=info["name"],
                    password_hash=get_password_hash(info["password"]),
                    is_admin=True
                )
                sess.add(user)
                # Flush inmediato para atrapar errores de integridad antes del commit final
                sess.flush()
        sess.commit()
    except Exception as e:
        print(f"Advertencia al crear usuarios por defecto (posible concurrencia): {e}")
        sess.rollback()

def ensure_recipient_type_column():
    """Migración manual para agregar recipient_type a AlertRecipient si no existe."""
    with Session(engine) as sess:
        try:
            # Intenta seleccionar la columna
            sess.execute(select(AlertRecipient.recipient_type).limit(1))
        except Exception:
            # Si falla, probablemente no existe la columna
            print("Agregando columna recipient_type a alert_recipients...")
            try:
                sess.execute(text("ALTER TABLE alert_recipients ADD COLUMN recipient_type VARCHAR(50) DEFAULT 'OTROS'"))
                sess.commit()
            except Exception as e:
                print(f"Error migrando recipient_type: {e}")
                sess.rollback()

def ensure_link_column():
    """Migración manual para agregar receive_alerts a user_server_link si no existe."""
    with Session(engine) as sess:
        try:
            sess.execute(select(UserServerLink.receive_alerts).limit(1))
        except Exception:
            print("Agregando columna receive_alerts a user_server_link...")
            try:
                sess.execute(text("ALTER TABLE user_server_link ADD COLUMN receive_alerts BOOLEAN DEFAULT 1"))
                sess.commit()
            except Exception as e:
                print(f"Error migrando user_server_link: {e}")
                sess.rollback()

def ensure_environment_column():
    """Migración manual para agregar environment a DataMonitoring si no existe."""
    with Session(engine) as sess:
        try:
            sess.execute(select(DataMonitoring.environment).limit(1))
        except Exception:
            print("Agregando columna environment a data_monitoring...")
            try:
                sess.execute(text("ALTER TABLE data_monitoring ADD COLUMN environment VARCHAR(50)"))
                sess.commit()
            except Exception as e:
                print(f"Error migrando environment: {e}")
                sess.rollback()

def ensure_server_group_column():
    """Migración manual para agregar group_name a servers si no existe."""
    with Session(engine) as sess:
        try:
            sess.execute(select(Server.group_name).limit(1))
        except Exception:
            print("Agregando columna group_name a servers...")
            try:
                sess.execute(text("ALTER TABLE servers ADD COLUMN group_name VARCHAR(50)"))
                sess.commit()
            except Exception as e:
                print(f"Error migrando group_name: {e}")
                sess.rollback()

def ensure_admin_assignments():
    """Asegura que todos los administradores tengan asignados todos los servidores (para alertas)."""
    with Session(engine) as sess:
        try:
            admins = sess.execute(select(User).where(User.is_admin == True)).scalars().all()
            servers = sess.execute(select(Server)).scalars().all()
            
            for admin in admins:
                existing_links = {l.server_id for l in admin.server_links}
                for srv in servers:
                    if srv.id not in existing_links:
                        print(f"Auto-asignando {srv.server_id} al admin {admin.email}")
                        link = UserServerLink(user_id=admin.id, server_id=srv.id, receive_alerts=True, postman_access_level='admin')
                        sess.add(link)
            sess.commit()
        except Exception as e:
            print(f"Error en ensure_admin_assignments: {e}")
            sess.rollback()

def ensure_postman_access_column():
    """Migración manual para agregar postman_access_level a user_server_link si no existe."""
    with Session(engine) as sess:
        try:
            sess.execute(select(UserServerLink.postman_access_level).limit(1))
        except Exception:
            print("Agregando columna postman_access_level a user_server_link...")
            try:
                sess.execute(text("ALTER TABLE user_server_link ADD COLUMN postman_access_level VARCHAR(20) DEFAULT 'none'"))
                sess.commit()
            except Exception as e:
                print(f"Error migrando user_server_link: {e}")
                sess.rollback()

def ensure_sidebar_config_column():
    """Migración manual para agregar sidebar_config a users si no existe."""
    with Session(engine) as sess:
        try:
            sess.execute(select(User.sidebar_config).limit(1))
        except Exception:
            print("Agregando columna sidebar_config a users...")
            try:
                sess.execute(text("ALTER TABLE users ADD COLUMN sidebar_config TEXT DEFAULT NULL"))
                sess.commit()
            except Exception as e:
                print(f"Error migrando users: {e}")
                sess.rollback()

@app.on_event("startup")
def startup():
    try:
        ensure_recipient_type_column()
        ensure_link_column()
        ensure_postman_access_column()
        ensure_sidebar_config_column()
        ensure_environment_column()
        ensure_server_group_column()
        ensure_admin_assignments()
        with Session(engine) as sess:
            ensure_default_alerts(sess)
    except Exception as e:
        print(f"Advertencia en startup: {e}")



# Caché en memoria de métricas recientes por servidor
_cache: dict[str, list[dict]] = {}
_cache_order: dict[str, int] = {}

# Caché de umbrales: server_id -> {cpu_threshold, memory_threshold, disk_threshold}
_threshold_cache: dict[str, dict] = {}

# Estado de alertas enviadas: {(server_id, alert_type): timestamp}
_alert_state: dict[tuple[str, str], float] = {}
ALERT_COOLDOWN = 3600


def create_jwt_for_user(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except Exception:
        return None



def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    try:
        s = unicodedata.normalize('NFKD', s)
        s = ''.join(c for c in s if not unicodedata.combining(c))
    except Exception:
        pass
    return s

def get_current_user_from_token(x_dashboard_token: Optional[str] = Header(None)):
    if not x_dashboard_token:
        raise HTTPException(status_code=401, detail="Unauthorized dashboard token")
    
    with Session(engine) as sess:
        session_record = sess.execute(
            select(UserSession).where(UserSession.token == x_dashboard_token)
        ).scalar_one_or_none()
        
        if not session_record:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Cargar usuario relacionado
        user = sess.get(User, session_record.user_id)
        if not user:
            # Sesión huérfana
            sess.delete(session_record)
            sess.commit()
            raise HTTPException(status_code=401, detail="User not found")
            
        return {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin
        }

def require_admin(user: dict = Depends(get_current_user_from_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Requiere privilegios de administrador")
    return user


def require_data_monitoring_access(user: dict = Depends(get_current_user_from_token)):
    with Session(engine) as sess:
        db_user = sess.get(User, user["user_id"])
        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")
        cfg = sess.execute(
            select(DataMonitoringUserConfig).where(
                DataMonitoringUserConfig.user_id == db_user.id
            )
        ).scalar_one_or_none()
        if not (db_user.is_admin or (cfg and cfg.enabled)):
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para ver el dashboard de datos",
            )
    return user


def perform_login(identifier: str, password: str) -> Dict[str, Any]:
    identifier = _norm(identifier or "")
    password = (password or "").strip()
    with Session(engine) as sess:
        user = sess.execute(select(User).where(User.email == identifier)).scalar_one_or_none()
        if not user:
            all_users = sess.execute(select(User)).scalars().all()
            for u in all_users:
                if _norm(u.email) == identifier or _norm(u.email.split('@')[0]) == identifier:
                    user = u
                    break
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        token = uuid.uuid4().hex
        new_session = UserSession(token=token, user_id=user.id)
        sess.add(new_session)
        cfg = sess.execute(select(DataMonitoringUserConfig).where(DataMonitoringUserConfig.user_id == user.id)).scalar_one_or_none()
        can_view_dm = cfg.enabled if cfg else False
        sess.commit()
        sidebar_conf = None
        if user.sidebar_config:
            try:
                sidebar_conf = json.loads(user.sidebar_config)
            except:
                pass
        return {
            "token": token,
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin,
            "can_view_data_monitoring": can_view_dm,
            "sidebar_config": sidebar_conf,
        }

@app.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginSchema):
    return perform_login(payload.email or "", payload.password or "")

@app.post("/api/logout")
def logout(x_dashboard_token: Optional[str] = Header(None)):
    if not x_dashboard_token:
        raise HTTPException(status_code=401, detail="Missing token")
        
    with Session(engine) as sess:
        sess.execute(delete(UserSession).where(UserSession.token == x_dashboard_token))
        sess.commit()
    
    return {"status": "logged_out"}

@app.get("/api/user/sidebar-config")
def get_sidebar_config(user: dict = Depends(get_current_user_from_token)):
    with Session(engine) as sess:
        db_user = sess.get(User, user["user_id"])
        if not db_user:
             raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        config = None
        if db_user.sidebar_config:
            try:
                config = json.loads(db_user.sidebar_config)
            except:
                pass
        return {"config": config}

@app.put("/api/user/sidebar-config")
def update_sidebar_config(payload: SidebarConfigUpdateSchema, user: dict = Depends(get_current_user_from_token)):
    with Session(engine) as sess:
        db_user = sess.get(User, user["user_id"])
        if not db_user:
             raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Guardar como JSON string
        try:
            db_user.sidebar_config = json.dumps(payload.config)
            sess.commit()
        except Exception as e:
            sess.rollback()
            raise HTTPException(status_code=500, detail=f"Error guardando configuración: {str(e)}")
            
        return {"status": "updated", "config": payload.config}

# --- Gestión de Usuarios (Admin) ---

@app.get("/api/admin/users", response_model=List[UserResponseSchema])
def list_users(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        users = sess.execute(select(User)).scalars().all()
        configs = sess.execute(select(DataMonitoringUserConfig)).scalars().all()
        cfg_map = {c.user_id: c.enabled for c in configs}
        result = []
        for u in users:
            result.append(UserResponseSchema(
                id=u.id,
                email=u.email,
                name=u.name,
                is_admin=u.is_admin,
                receive_alerts=u.receive_alerts,
                can_view_data_monitoring=cfg_map.get(u.id, False),
                created_at=u.created_at
            ))
        return result

@app.post("/api/admin/users", response_model=UserResponseSchema)
def create_user(payload: UserCreateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        existing = sess.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        
        new_user = User(
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            name=payload.name,
            is_admin=payload.is_admin,
            receive_alerts=payload.receive_alerts
        )
        sess.add(new_user)
        sess.flush()
        if payload.can_view_data_monitoring:
            cfg = DataMonitoringUserConfig(user_id=new_user.id, enabled=True)
            sess.add(cfg)
        sess.commit()
        cfg = sess.execute(select(DataMonitoringUserConfig).where(DataMonitoringUserConfig.user_id == new_user.id)).scalar_one_or_none()
        return UserResponseSchema(
            id=new_user.id,
            email=new_user.email,
            name=new_user.name,
            is_admin=new_user.is_admin,
            receive_alerts=new_user.receive_alerts,
            can_view_data_monitoring=cfg.enabled if cfg else False,
            created_at=new_user.created_at
        )

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_admin)):
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
        
    with Session(engine) as sess:
        u = sess.get(User, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        sess.delete(u)
        sess.commit()
        return {"status": "deleted"}

@app.put("/api/admin/users/{user_id}", response_model=UserResponseSchema)
def update_user(user_id: int, payload: UserUpdateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        u = sess.get(User, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        if payload.name is not None:
            u.name = payload.name
        if payload.is_admin is not None:
            # Evitar quitarse admin a sí mismo
            if user_id == user["user_id"] and payload.is_admin is False:
                raise HTTPException(status_code=400, detail="No puedes quitarte privilegios de administrador a ti mismo")
            u.is_admin = payload.is_admin
        if payload.receive_alerts is not None:
            u.receive_alerts = payload.receive_alerts
        if payload.password is not None:
            u.password_hash = get_password_hash(payload.password)
        if payload.can_view_data_monitoring is not None:
            cfg = sess.execute(select(DataMonitoringUserConfig).where(DataMonitoringUserConfig.user_id == user_id)).scalar_one_or_none()
            if not cfg:
                cfg = DataMonitoringUserConfig(user_id=user_id, enabled=payload.can_view_data_monitoring)
                sess.add(cfg)
            else:
                cfg.enabled = payload.can_view_data_monitoring
            
        sess.commit()
        cfg = sess.execute(select(DataMonitoringUserConfig).where(DataMonitoringUserConfig.user_id == user_id)).scalar_one_or_none()
        return UserResponseSchema(
            id=u.id,
            email=u.email,
            name=u.name,
            is_admin=u.is_admin,
            receive_alerts=u.receive_alerts,
            can_view_data_monitoring=cfg.enabled if cfg else False,
            created_at=u.created_at
        )

@app.post("/api/admin/users/{user_id}/servers")
def assign_servers_to_user(user_id: int, payload: ServerAssignmentSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        target_user = sess.get(User, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
        
        # 1. Eliminar asignaciones existentes
        sess.execute(delete(UserServerLink).where(UserServerLink.user_id == user_id))
        
        # 2. Crear nuevas asignaciones
        if payload.assignments:
            # Obtener IDs internos de los servidores
            server_ids_str = [a.server_id for a in payload.assignments]
            servers_map = {
                s.server_id: s.id 
                for s in sess.execute(select(Server).where(Server.server_id.in_(server_ids_str))).scalars().all()
            }
            
            for item in payload.assignments:
                s_int_id = servers_map.get(item.server_id)
                if s_int_id:
                    link = UserServerLink(
                        user_id=user_id,
                        server_id=s_int_id,
                        receive_alerts=item.receive_alerts,
                        postman_access_level=item.postman_access_level
                    )
                    sess.add(link)
        
        sess.commit()
        return {"status": "assigned", "count": len(payload.assignments)}

@app.get("/api/admin/users/{user_id}/servers", response_model=List[UserServerAssignmentResponse])
def get_user_servers(user_id: int, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        target_user = sess.get(User, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
        
        res = []
        for link in target_user.server_links:
            # Asegurarse de que link.server esté cargado
            res.append({
                "server_id": link.server.server_id,
                "receive_alerts": link.receive_alerts,
                "postman_access_level": link.postman_access_level
            })
        return res

# --- Servidores y Métricas ---

@app.post("/api/register")
def register_server(payload: RegisterServerSchema):
    with Session(engine) as sess:
        existing = sess.execute(select(Server).where(Server.server_id == payload.server_id)).scalar_one_or_none()
        if existing:
            existing.token = payload.token
            sess.commit()
            return {"status": "updated", "server_id": existing.server_id}
        
        srv = Server(server_id=payload.server_id, token=payload.token)
        sess.add(srv)
        sess.flush()
        
        # Auto-asignar a todos los admins
        admins = sess.execute(select(User).where(User.is_admin == True)).scalars().all()
        for admin in admins:
            sess.add(UserServerLink(user_id=admin.id, server_id=srv.id, receive_alerts=True))
            
        sess.commit()
        return {"status": "registered", "server_id": payload.server_id}


@app.get("/api/servers")
def list_servers(user: dict = Depends(get_current_user_from_token)):
    with Session(engine) as sess:
        configs = sess.execute(select(DataMonitoringServerConfig)).scalars().all()
        cfg_map = {c.server_id: c.enabled for c in configs}
        db_user = sess.get(User, user["user_id"])
        
        results = []
        
        if db_user and not db_user.is_admin:
            # User sees only assigned servers
            for link in db_user.server_links:
                if link.server:
                    results.append({
                        "server_id": link.server.server_id,
                        "created_at": str(link.server.created_at),
                        "group_name": link.server.group_name,
                        "report_interval": link.server.report_interval,
                        "data_monitoring_enabled": cfg_map.get(link.server.server_id, False),
                        "postman_access_level": link.postman_access_level
                    })
        else:
            # Admin sees all servers
            servers = sess.execute(select(Server)).scalars().all()
            for s in servers:
                results.append({
                    "server_id": s.server_id,
                    "created_at": str(s.created_at),
                    "group_name": s.group_name,
                    "report_interval": s.report_interval,
                    "data_monitoring_enabled": cfg_map.get(s.server_id, False),
                    "postman_access_level": "admin"
                })
                
        return results

@app.delete("/api/admin/servers/{server_id}")
def delete_server(server_id: str, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        srv = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not srv:
            raise HTTPException(status_code=404, detail="Servidor no encontrado")
        sess.delete(srv)
        sess.commit()
        
        # Limpiar caché si existe
        if server_id in _cache:
            del _cache[server_id]
            
        return {"status": "deleted", "server_id": server_id}


@app.put("/api/admin/servers/{server_id}/config")
def update_server_config(server_id: str, payload: ServerConfigUpdateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        srv = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not srv:
            raise HTTPException(status_code=404, detail="Servidor no encontrado")
        
        srv.report_interval = payload.report_interval
        sess.commit()
        return {"status": "updated", "server_id": server_id, "report_interval": srv.report_interval}


@app.put("/api/admin/servers/{server_id}/data-monitoring")
def update_server_data_monitoring(server_id: str, payload: ServerDataMonitoringUpdateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        srv = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not srv:
            raise HTTPException(status_code=404, detail="Servidor no encontrado")
        cfg = sess.execute(select(DataMonitoringServerConfig).where(DataMonitoringServerConfig.server_id == server_id)).scalar_one_or_none()
        if not cfg:
            cfg = DataMonitoringServerConfig(server_id=server_id, enabled=payload.enabled)
            sess.add(cfg)
        else:
            cfg.enabled = payload.enabled
        sess.commit()
        return {"status": "updated", "server_id": server_id, "enabled": cfg.enabled}


# --- Destinatarios de Alertas (Alert Recipients) ---

@app.get("/api/admin/recipients", response_model=List[AlertRecipientSchema])
def list_alert_recipients(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        recipients = sess.execute(select(AlertRecipient)).scalars().all()
    return recipients

def get_alert_recipients(sess: Session, srv: Server, alert_type: str):
    # 1. Alert Rules
    rules = sess.execute(select(AlertRule).where(AlertRule.alert_type == alert_type)).scalars().all()
    recipients = []
    applied_rules = []
    
    for rule in rules:
        match = False
        if rule.server_scope == 'global':
            match = True
        elif rule.server_scope == 'server' and rule.target_id == srv.server_id:
            match = True
        elif rule.server_scope == 'group' and rule.target_id == srv.group_name:
            match = True
            
        if match:
            applied_rules.append(rule.id)
            try:
                rule_emails = json.loads(rule.emails)
                if isinstance(rule_emails, list):
                    recipients.extend(rule_emails)
            except:
                pass

            try:
                extra = json.loads(rule.extra_emails or "[]")
                if isinstance(extra, list):
                    recipients.extend(extra)
            except:
                pass
                
    # 3. Assigned Users
    # srv is a Server object, which has 'user_links' relationship
    if srv.user_links:
        for link in srv.user_links:
            # Check link specific flag (defaults to True).
            # We assume explicit assignment implies permission unless turned off.
            if link.receive_alerts and link.user.email:
                recipients.append(link.user.email)

    return list(set(recipients)), applied_rules

@app.post("/api/admin/recipients", response_model=AlertRecipientSchema)
def create_alert_recipient(payload: AlertRecipientCreateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        existing = sess.execute(select(AlertRecipient).where(AlertRecipient.email == payload.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        
        new_recipient = AlertRecipient(
            email=payload.email, 
            name=payload.name,
            recipient_type=payload.recipient_type
        )
        sess.add(new_recipient)
        sess.commit()
        sess.refresh(new_recipient)
        return new_recipient

@app.delete("/api/admin/recipients/{recipient_id}")
def delete_alert_recipient(recipient_id: int, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        r = sess.get(AlertRecipient, recipient_id)
        if not r:
            raise HTTPException(status_code=404, detail="Destinatario no encontrado")
        sess.delete(r)
        sess.commit()
        return {"status": "deleted"}


@app.post("/api/admin/test-email")
def test_email(payload: AlertRecipientCreateSchema, user: dict = Depends(require_admin)):
    """
    Endpoint para probar la configuración de correo.
    Envía un correo de prueba al destinatario especificado.
    """
    try:
        # Usamos send_alert_email con datos simulados
        send_alert_email(
            server_id="TEST-SERVER",
            alert_type="PRUEBA DE CORREO",
            current_value=100.0,
            threshold=50.0,
            extra_recipients=[payload.email],
            full_metrics={}
        )
        return {"status": "sent", "message": f"Correo de prueba enviado a {payload.email}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error enviando correo: {str(e)}")


# --- Reglas de Alerta y Grupos ---

@app.get("/api/admin/alert-rules", response_model=List[AlertRuleResponse])
def list_alert_rules(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        rules = sess.execute(select(AlertRule)).scalars().all()
        res = []
        for r in rules:
            try:
                emails_list = json.loads(r.emails) if r.emails else []
            except:
                emails_list = []
            res.append(AlertRuleResponse(
                id=r.id,
                alert_type=r.alert_type,
                server_scope=r.server_scope,
                target_id=r.target_id,
                emails=emails_list,
                extra_emails=json.loads(r.extra_emails) if r.extra_emails else [],
                created_at=r.created_at
            ))
        return res

@app.post("/api/admin/alert-rules", response_model=AlertRuleResponse)
def create_alert_rule(payload: AlertRuleCreate, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        new_rule = AlertRule(
            alert_type=payload.alert_type,
            server_scope=payload.server_scope,
            target_id=payload.target_id,
            emails=json.dumps(payload.emails),
            extra_emails=json.dumps(payload.extra_emails)
        )
        sess.add(new_rule)
        sess.commit()
        sess.refresh(new_rule)
        
        return AlertRuleResponse(
            id=new_rule.id,
            alert_type=new_rule.alert_type,
            server_scope=new_rule.server_scope,
            target_id=new_rule.target_id,
            emails=payload.emails,
            extra_emails=payload.extra_emails,
            created_at=new_rule.created_at
        )

@app.delete("/api/admin/alert-rules/{rule_id}")
def delete_alert_rule(rule_id: int, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        r = sess.get(AlertRule, rule_id)
        if not r:
            raise HTTPException(status_code=404, detail="Regla no encontrada")
        sess.delete(r)
        sess.commit()
        return {"status": "deleted"}

# --- Server Groups ---

@app.get("/api/admin/groups", response_model=List[ServerGroupSchema])
def list_server_groups(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        groups = sess.execute(select(ServerGroup)).scalars().all()
        return groups

@app.post("/api/admin/groups", response_model=ServerGroupSchema)
def create_server_group(payload: ServerGroupCreateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        existing = sess.execute(select(ServerGroup).where(ServerGroup.name == payload.name)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="El grupo ya existe")
        
        new_group = ServerGroup(name=payload.name)
        sess.add(new_group)
        sess.commit()
        sess.refresh(new_group)
        return new_group

@app.delete("/api/admin/groups/{group_id}")
def delete_server_group(group_id: int, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        g = sess.get(ServerGroup, group_id)
        if not g:
            raise HTTPException(status_code=404, detail="Grupo no encontrado")
        
        # Check if used by any server
        srv = sess.execute(select(Server).where(Server.group_name == g.name)).first()
        if srv:
            raise HTTPException(status_code=400, detail="No se puede eliminar un grupo que tiene servidores asignados")
            
        sess.delete(g)
        sess.commit()
        return {"status": "deleted"}



@app.put("/api/admin/servers/{server_id}/group")
def update_server_group(server_id: str, payload: ServerUpdateGroupSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        srv = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not srv:
            raise HTTPException(status_code=404, detail="Servidor no encontrado")
        srv.group_name = payload.group_name
        sess.commit()
        return {"status": "updated", "group_name": srv.group_name}


def log_audit(sess: Session, action: str, target_type: str, target_id: str, changes: dict, user_email: str):
    log_entry = AuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        changes=json.dumps(changes) if changes else None,
        user_email=user_email
    )
    sess.add(log_entry)


# --- Gestión de Umbrales (Thresholds) ---

@app.get("/api/umbrales", response_model=List[ServerThresholdResponse])
def list_thresholds(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        thresholds = sess.execute(select(ServerThreshold)).scalars().all()
        return thresholds

@app.get("/api/umbrales/{server_id}", response_model=ServerThresholdResponse)
def get_threshold(server_id: str, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        t = sess.execute(select(ServerThreshold).where(ServerThreshold.server_id == server_id)).scalar_one_or_none()
        if not t:
            # Si no existe, devolver uno vacío con el server_id
            return ServerThresholdResponse(server_id=server_id, cpu_threshold=None, memory_threshold=None, disk_threshold=None, updated_at=None)
        return t

@app.put("/api/umbrales/{server_id}", response_model=ServerThresholdResponse)
def update_threshold(server_id: str, payload: ServerThresholdUpdate, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        # Check if server exists
        srv = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not srv:
             raise HTTPException(status_code=404, detail="Servidor no encontrado")
             
        t = sess.execute(select(ServerThreshold).where(ServerThreshold.server_id == server_id)).scalar_one_or_none()
        
        changes = {}
        if not t:
            t = ServerThreshold(server_id=server_id)
            sess.add(t)
            changes["created"] = True
            
        if payload.cpu_threshold is not None:
            changes["cpu_threshold"] = {"old": t.cpu_threshold, "new": payload.cpu_threshold}
            t.cpu_threshold = payload.cpu_threshold
            
        if payload.memory_threshold is not None:
            changes["memory_threshold"] = {"old": t.memory_threshold, "new": payload.memory_threshold}
            t.memory_threshold = payload.memory_threshold
            
        if payload.disk_threshold is not None:
            changes["disk_threshold"] = {"old": t.disk_threshold, "new": payload.disk_threshold}
            t.disk_threshold = payload.disk_threshold
            
        # Log Audit
        log_audit(sess, "update", "threshold", server_id, changes, user["email"])
        
        sess.commit()
        sess.refresh(t)
        
        # Update Cache
        _threshold_cache[server_id] = {
            "cpu": t.cpu_threshold,
            "memory": t.memory_threshold,
            "disk": t.disk_threshold
        }
        
        return t

@app.get("/api/umbrales/export", response_model=List[ServerThresholdResponse])
def export_thresholds(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        thresholds = sess.execute(select(ServerThreshold)).scalars().all()
        return thresholds

@app.post("/api/umbrales/import")
def import_thresholds(payload: List[ServerThresholdImport], user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        count = 0
        for item in payload:
            # Validate server exists
            srv = sess.execute(select(Server).where(Server.server_id == item.server_id)).scalar_one_or_none()
            if not srv:
                continue 
            
            t = sess.execute(select(ServerThreshold).where(ServerThreshold.server_id == item.server_id)).scalar_one_or_none()
            if not t:
                t = ServerThreshold(server_id=item.server_id)
                sess.add(t)
            
            t.cpu_threshold = item.cpu_threshold
            t.memory_threshold = item.memory_threshold
            t.disk_threshold = item.disk_threshold
            
            # Update cache immediately
            _threshold_cache[item.server_id] = {
                "cpu": t.cpu_threshold,
                "memory": t.memory_threshold,
                "disk": t.disk_threshold
            }
            count += 1
        
        log_audit(sess, "import", "threshold", "bulk", {"count": count}, user["email"])
        sess.commit()
        return {"status": "imported", "count": count}

@app.get("/api/audit-logs", response_model=List[AuditLogResponse])
def list_audit_logs(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        logs = sess.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100)).scalars().all()
        return logs


@app.post("/api/metrics")
def ingest_metrics(payload: MetricsIngestSchema, x_auth_token: Optional[str] = Header(None)):
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    with Session(engine) as sess:
        srv = sess.execute(select(Server).where(Server.server_id == payload.server_id)).scalar_one_or_none()
        if not srv or srv.token != x_auth_token:
            raise HTTPException(status_code=403, detail="Unauthorized server or bad token")

        # Validaciones de rango
        if not (0 <= payload.cpu.total <= 100):
            raise HTTPException(status_code=422, detail="cpu.total fuera de rango")
        if any(c < 0 or c > 100 for c in payload.cpu.per_core):
            raise HTTPException(status_code=422, detail="cpu.per_core fuera de rango")
        if payload.memory.used > payload.memory.total or payload.memory.total <= 0:
            raise HTTPException(status_code=422, detail="memoria inválida")
        if not (0 <= payload.disk.percent <= 100):
            raise HTTPException(status_code=422, detail="disk.percent fuera de rango")

        m = Metric(
            server_id=payload.server_id,
            mem_total=payload.memory.total,
            mem_used=payload.memory.used,
            mem_free=payload.memory.free,
            mem_cache=payload.memory.cache,
            cpu_total=payload.cpu.total,
            cpu_per_core=json.dumps(payload.cpu.per_core),
            disk_total=payload.disk.total,
            disk_used=payload.disk.used,
            disk_free=payload.disk.free,
            disk_percent=payload.disk.percent,
            docker_running=payload.docker.running_containers,
            docker_containers=json.dumps([c.model_dump() for c in payload.docker.containers]),
            services=json.dumps([s.model_dump() for s in payload.services]) if payload.services else "[]"
        )
        sess.add(m)
        sess.commit()

        # Verificar Alertas
        try:
            # Cargar configuración de alertas global
            alert_cfg = sess.execute(select(AlertConfig)).scalar_one_or_none()
            
            # Cargar umbrales específicos (con caché)
            thresholds = _threshold_cache.get(payload.server_id)
            if thresholds is None:
                # Si no está en caché, buscar en DB
                t_db = sess.execute(select(ServerThreshold).where(ServerThreshold.server_id == payload.server_id)).scalar_one_or_none()
                if t_db:
                    thresholds = {
                        "cpu": t_db.cpu_threshold,
                        "memory": t_db.memory_threshold,
                        "disk": t_db.disk_threshold
                    }
                else:
                    thresholds = {}
                _threshold_cache[payload.server_id] = thresholds
            
            # Definir límites efectivos (Global vs Específico)
            # Prioridad: Específico > Global
            
            cpu_limit = thresholds.get("cpu")
            if cpu_limit is None and alert_cfg:
                cpu_limit = alert_cfg.cpu_total_percent
                
            mem_limit = thresholds.get("memory")
            if mem_limit is None and alert_cfg:
                mem_limit = alert_cfg.memory_used_percent
                
            disk_limit = thresholds.get("disk")
            if disk_limit is None and alert_cfg:
                disk_limit = alert_cfg.disk_used_percent

            # Datos completos para el correo
            full_metrics = payload.model_dump()
            current_time = time.time()
            
            # Check CPU
            if cpu_limit and cpu_limit > 0 and payload.cpu.total >= cpu_limit:
                key = (payload.server_id, "cpu")
                last_sent = _alert_state.get(key, 0)
                if current_time - last_sent > ALERT_COOLDOWN:
                    recipients, applied_rules = get_alert_recipients(sess, srv, "cpu")
                    print(f"[ALERT] Sending CPU alert for {srv.server_id}. Threshold: {cpu_limit}% (Global or Custom). Applied rules: {applied_rules}")
                    send_alert_email(payload.server_id, "CPU Alta", payload.cpu.total, cpu_limit, recipients, full_metrics)
                    _alert_state[key] = current_time
            
            # Check Memory
            mem_percent = (payload.memory.used / payload.memory.total) * 100 if payload.memory.total > 0 else 0
            if mem_limit and mem_limit > 0 and mem_percent >= mem_limit:
                key = (payload.server_id, "memory")
                last_sent = _alert_state.get(key, 0)
                if current_time - last_sent > ALERT_COOLDOWN:
                    recipients, applied_rules = get_alert_recipients(sess, srv, "memory")
                    print(f"[ALERT] Sending Memory alert for {srv.server_id}. Threshold: {mem_limit}% (Global or Custom). Applied rules: {applied_rules}")
                    send_alert_email(payload.server_id, "Memoria Alta", mem_percent, mem_limit, recipients, full_metrics)
                    _alert_state[key] = current_time

            # Check Disk
            if disk_limit and disk_limit > 0 and payload.disk.percent >= disk_limit:
                key = (payload.server_id, "disk")
                last_sent = _alert_state.get(key, 0)
                if current_time - last_sent > ALERT_COOLDOWN:
                    recipients, applied_rules = get_alert_recipients(sess, srv, "disk")
                    print(f"[ALERT] Sending Disk alert for {srv.server_id}. Threshold: {disk_limit}% (Global or Custom). Applied rules: {applied_rules}")
                    send_alert_email(payload.server_id, "Disco Lleno", payload.disk.percent, disk_limit, recipients, full_metrics)
                    _alert_state[key] = current_time

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error checking alerts: {e}")
        
        # --- Service Monitoring Logic ---
        try:
            prev_cache = _cache.get(payload.server_id)
            if prev_cache and len(prev_cache) > 0:
                last_entry = prev_cache[-1]
                last_services = {s["name"]: s for s in last_entry.get("services", [])}
                curr_services = {s.name: s for s in payload.services} if payload.services else {}
                
                for name, curr_s in curr_services.items():
                    prev_s = last_services.get(name)
                    if prev_s and prev_s.get("status") != curr_s.status:
                        # Status changed
                        msg = f"El servicio '{curr_s.display_name or name}' cambió de estado: {prev_s.get('status')} -> {curr_s.status}"
                        # Check for service alert recipients
                        recipients, _ = get_alert_recipients(sess, srv, "service_status")
                        
                        print(f"[ALERT] Service status change detected for {srv.server_id}: {msg}")
                        send_alert_email(
                            server_id=payload.server_id, 
                            alert_type="Cambio de Estado de Servicio", 
                            current_value=0, 
                            threshold=0, 
                            extra_recipients=recipients,
                            full_metrics=payload.model_dump(),
                            custom_message=msg
                        )
        except Exception as e:
            print(f"Error checking service alerts: {e}")

        # Actualizar caché en memoria
        try:
            entry = {
                "server_id": payload.server_id,
                "ts": str(m.ts),
                "memory": payload.memory.model_dump(),
                "cpu": payload.cpu.model_dump(),
                "disk": payload.disk.model_dump(),
                "docker": payload.docker.model_dump(),
                "services": [s.model_dump() for s in payload.services] if payload.services else []
            }
            buf = _cache.get(payload.server_id)
            if not buf:
                buf = []
                _cache[payload.server_id] = buf
            buf.append(entry)
            if len(buf) > CACHE_MAX_ITEMS:
                # recortar dejado en el inicio
                del buf[: len(buf) - CACHE_MAX_ITEMS]
        except Exception:
            # No bloquear por errores de caché
            pass
        return {"status": "ok", "report_interval": srv.report_interval}


@app.get("/api/metrics/history")
def metrics_history(server_id: Optional[str] = None, limit: int = 100, user: dict = Depends(get_current_user_from_token)):
    # Intentar servir desde caché si es posible
    if server_id and server_id in _cache:
        buf = _cache[server_id]
        if len(buf) >= 1:
            return buf[-limit:]
    with Session(engine) as sess:
        try:
            q = select(Metric).order_by(Metric.id.desc()).limit(limit)
            if server_id:
                q = q.where(Metric.server_id == server_id)
            rows = sess.execute(q).scalars().all()
            rows = list(reversed(rows))
            def row_to_dict(r: Metric):
                return {
                    "server_id": r.server_id,
                    "ts": str(r.ts),
                    "memory": {"total": r.mem_total, "used": r.mem_used, "free": r.mem_free, "cache": r.mem_cache},
                    "cpu": {"total": r.cpu_total, "per_core": json.loads(r.cpu_per_core or "[]")},
                    "disk": {"total": r.disk_total, "used": r.disk_used, "free": r.disk_free, "percent": r.disk_percent},
                    "docker": {"running_containers": r.docker_running, "containers": json.loads(r.docker_containers or "[]")},
                    "services": json.loads(r.services or "[]")
                }
            data = [row_to_dict(r) for r in rows]
            if server_id:
                _cache[server_id] = data[-CACHE_MAX_ITEMS:]
            return data
        except Exception:
            raise HTTPException(status_code=500, detail="Error consultando historial")


@app.get("/api/alerts")
def get_alerts(user: dict = Depends(get_current_user_from_token)):
    with Session(engine) as sess:
        cfg = sess.execute(select(AlertConfig)).scalar_one()
        return {
            "cpu_total_percent": cfg.cpu_total_percent,
            "memory_used_percent": cfg.memory_used_percent,
            "disk_used_percent": cfg.disk_used_percent,
        }


@app.post("/api/alerts")
def set_alerts(payload: AlertConfigSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        cfg = sess.execute(select(AlertConfig)).scalar_one_or_none()
        if not cfg:
            cfg = AlertConfig(
                cpu_total_percent=payload.cpu_total_percent,
                memory_used_percent=payload.memory_used_percent,
                disk_used_percent=payload.disk_used_percent,
            )
            sess.add(cfg)
        else:
            cfg.cpu_total_percent = payload.cpu_total_percent
            cfg.memory_used_percent = payload.memory_used_percent
            cfg.disk_used_percent = payload.disk_used_percent
        sess.commit()
        return {"status": "updated"}


@app.get("/api/health")
def health():
    try:
        with Session(engine) as sess:
            sess.execute(select(Server)).first()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/data-monitoring", status_code=201)
def create_data_monitoring(payload: DataMonitoringSchema):
    try:
        with Session(engine) as sess:
            data = DataMonitoring(
                        app=payload.app,
                        cash_register_number=payload.cash_register_number,
                        user_name=payload.user_name,
                        flow=payload.flow,
                        patent=payload.patent,
                        vehicle_type=payload.vehicle_type,
                        product=payload.product,
                        created_at_client=payload.created_at_client,
                        entity_id=payload.entity_id,
                        working_day=payload.working_day,
                        environment=payload.environment
                    )
            sess.add(data)
            sess.commit()
            sess.refresh(data)
            return {"status": "created", "id": data.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-monitoring", response_model=List[DataMonitoringResponseSchema])
def list_data_monitoring(
    limit: int = 50,
    offset: int = 0,
    environment: Optional[str] = None,
    app_name: Optional[str] = None,
    entity_id: Optional[str] = None,
    user: dict = Depends(get_current_user_from_token)
):
    with Session(engine) as sess:
        db_user = sess.get(User, user["user_id"])
        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")

        # Check permissions
        has_permission = False
        if db_user.is_admin:
            has_permission = True
        else:
            # Check global flag
            cfg = sess.execute(select(DataMonitoringUserConfig).where(DataMonitoringUserConfig.user_id == db_user.id)).scalar_one_or_none()
            if cfg and cfg.enabled:
                has_permission = True
            
            # Check granular server permission if entity_id provided
            if not has_permission and entity_id:
                srv = sess.execute(select(Server).where(Server.server_id == entity_id)).scalar_one_or_none()
                if srv:
                     link = sess.execute(select(UserServerLink).where(
                         UserServerLink.user_id == db_user.id,
                         UserServerLink.server_id == srv.id
                     )).scalar_one_or_none()
                     if link and link.postman_access_level in ('view', 'edit', 'admin'):
                         has_permission = True

        if not has_permission:
            raise HTTPException(status_code=403, detail="No tienes permiso para ver estos datos")

        # Audit Log
        if entity_id:
             sess.add(AuditLog(
                 action="view_postman_data",
                 target_type="server",
                 target_id=entity_id,
                 user_email=db_user.email,
                 changes=json.dumps({"env": environment, "app": app_name})
             ))
             sess.commit()

        query = select(DataMonitoring).order_by(DataMonitoring.id.desc())

        if environment:
            query = query.where(DataMonitoring.environment == environment)
        if app_name:
            query = query.where(DataMonitoring.app == app_name)
        if entity_id:
            query = query.where(DataMonitoring.entity_id == entity_id)

        data = sess.execute(query.offset(offset).limit(limit)).scalars().all()
        
        result = []
        for d in data:
            result.append(DataMonitoringResponseSchema(
                app=d.app,
                cashRegisterNumber=d.cash_register_number,
                userName=d.user_name,
                flow=d.flow,
                patent=d.patent,
                vehicleType=d.vehicle_type,
                product=d.product,
                createdAt=d.created_at_client,
                entityId=d.entity_id,
                workingDay=d.working_day,
                environment=d.environment,
                id=d.id,
                received_at=d.received_at
            ))
        return result


@app.get("/api/data-monitoring/export")
def export_data_monitoring(user: dict = Depends(require_data_monitoring_access)):
    with Session(engine) as sess:
        query = select(DataMonitoring).order_by(DataMonitoring.id.desc())
        results = sess.execute(query).scalars().all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        headers = ["id", "app", "cash_register_number", "user_name", "flow", "patent", "vehicle_type", "product", "created_at_client", "entity_id", "working_day", "environment", "received_at"]
        writer.writerow(headers)
        
        for row in results:
            writer.writerow([
                row.id, row.app, row.cash_register_number, row.user_name, 
                row.flow, row.patent, row.vehicle_type, row.product, 
                row.created_at_client, row.entity_id, row.working_day, row.environment, row.received_at
            ])
            
        output.seek(0)
        response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=data_monitoring.csv"
        return response

# --- Service Management ---

@app.post("/api/servers/{server_id}/services/action", response_model=AgentCommandResponse)
def execute_service_action(server_id: str, payload: ServiceActionSchema, user: dict = Depends(require_admin)):
    """
    Queue a command to start/stop/restart a service on the agent.
    """
    with Session(engine) as sess:
        server = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Validar comando
        if payload.action not in ["start", "stop", "restart", "update"]:
            raise HTTPException(status_code=400, detail="Invalid action")

        # Crear comando pendiente
        command = AgentCommand(
            server_id=server.server_id,
            command=f"service_{payload.action}",
            params=json.dumps({"service": payload.service}),
            status="pending"
        )
        sess.add(command)
        sess.commit()
        sess.refresh(command)
        return command

@app.post("/api/servers/{server_id}/services/bulk-action", response_model=List[AgentCommandResponse])
def execute_bulk_service_action(server_id: str, payload: BulkServiceActionSchema, user: dict = Depends(require_admin)):
    """
    Queue commands to start/stop/restart multiple services on the agent.
    """
    with Session(engine) as sess:
        server = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Validar comando
        if payload.action not in ["start", "stop", "restart", "update"]:
            raise HTTPException(status_code=400, detail="Invalid action")

        commands = []
        for service_name in payload.services:
            # Crear comando pendiente para cada servicio
            command = AgentCommand(
                server_id=server.server_id,
                command=f"service_{payload.action}",
                params=json.dumps({"service": service_name}),
                status="pending"
            )
            sess.add(command)
            commands.append(command)
        
        sess.commit()
        # Refresh all commands to get their IDs
        for cmd in commands:
            sess.refresh(cmd)
            
        return commands

@app.get("/api/servers/{server_id}/commands/pending", response_model=List[AgentCommandResponse])
def get_pending_commands(server_id: str, x_auth_token: Optional[str] = Header(None)):
    """
    Endpoint for the AGENT to poll pending commands.
    """
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing auth token")
        
    with Session(engine) as sess:
        server = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not server or server.token != x_auth_token:
            raise HTTPException(status_code=403, detail="Unauthorized")
            
        commands = sess.execute(
            select(AgentCommand)
            .where(AgentCommand.server_id == server_id)
            .where(AgentCommand.status == "pending")
            .order_by(AgentCommand.created_at.asc())
        ).scalars().all()
        
        return commands

@app.post("/api/servers/{server_id}/commands/{command_id}/result")
def update_command_result(server_id: str, command_id: int, result: dict, x_auth_token: Optional[str] = Header(None)):
    """
    Endpoint for the AGENT to report command execution result.
    """
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing auth token")
        
    with Session(engine) as sess:
        server = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not server or server.token != x_auth_token:
            raise HTTPException(status_code=403, detail="Unauthorized")
            
        command = sess.get(AgentCommand, command_id)
        if not command or command.server_id != server_id:
            raise HTTPException(status_code=404, detail="Command not found")
            
        command.status = result.get("status", "executed")
        command.result = json.dumps(result.get("output", {}))
        command.executed_at = func.now()
        sess.commit()
        
    return {"status": "ok"}

# --- Servir Frontend con Cache Busting (debe ir al final) ---
import re
# Generar versión al inicio del servidor (timestamp)
APP_VERSION = str(int(time.time()))

frontend_path = Path(__file__).resolve().parent.parent.parent / "frontend"

@app.get("/", response_class=HTMLResponse)
async def serve_spa():
    if not frontend_path.exists():
        return HTMLResponse("Frontend not found", status_code=404)
    
    index_file = frontend_path / "index.html"
    if not index_file.exists():
        return HTMLResponse("index.html not found", status_code=404)
        
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Inyectar versión en app.js y styles.css para forzar recarga (Cache Busting)
        content = re.sub(r'src="assets/app\.js(\?v=[^"]*)?"', f'src="assets/app.js?v={APP_VERSION}"', content)
        content = re.sub(r'href="assets/styles\.css(\?v=[^"]*)?"', f'href="assets/styles.css?v={APP_VERSION}"', content)
        
        return HTMLResponse(content)
    except Exception as e:
        return HTMLResponse(f"Error loading frontend: {str(e)}", status_code=500)

if frontend_path.exists():
    # Montar assets explícitamente
    assets_path = frontend_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    
    # Montar raíz como fallback (ej. favicon.ico), pero html=False para que / sea manejado por serve_spa
    app.mount("/", StaticFiles(directory=frontend_path, html=False), name="frontend_root")
else:
    print(f"Advertencia: No se encontró el frontend en {frontend_path}")
