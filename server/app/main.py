import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import os
import uuid
import unicodedata

from fastapi import FastAPI, HTTPException, Header, Depends, status, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import DB_PATH, DEFAULT_ALERTS, ALLOWED_ORIGINS, DASHBOARD_TOKEN, CACHE_MAX_ITEMS, ALLOWED_USERS
from .models import Base, Server, Metric, AlertConfig, User, UserSession, AlertRecipient, AlertRule
from .schemas import (
    MetricsIngestSchema, RegisterServerSchema, AlertConfigSchema, LoginSchema,
    UserCreateSchema, UserResponseSchema, ChangePasswordSchema,
    ServerConfigUpdateSchema, AlertRecipientSchema, AlertRecipientCreateSchema,
    ServerAssignmentSchema, AlertRuleCreate, AlertRuleResponse, ServerUpdateGroupSchema
)
from .email_utils import send_alert_email
import time

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

@app.on_event("startup")
def startup():
    # Usar un lock o simplemente un try-except robusto
    try:
        with Session(engine) as sess:
            ensure_default_alerts(sess)
            # Deshabilitado temporalmente para evitar conflictos de concurrencia en reinicios rápidos
            # ensure_default_users(sess)
    except Exception as e:
        print(f"Advertencia en startup: {e}")

# Caché en memoria de métricas recientes por servidor
_cache: dict[str, list[dict]] = {}
_cache_order: dict[str, int] = {}

# Estado de alertas enviadas: {(server_id, alert_type): timestamp}
_alert_state: dict[tuple[str, str], float] = {}
ALERT_COOLDOWN = 3600  # 1 hora

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

@app.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginSchema):
    identifier = _norm(payload.email or "")
    password = (payload.password or "").strip()
    
    with Session(engine) as sess:
        # Buscar usuario por email
        # Primero intentamos coincidencia exacta
        user = sess.execute(select(User).where(User.email == identifier)).scalar_one_or_none()
        
        # Si no, buscar si el identificador coincide con la parte local del correo
        if not user:
             # Esto es menos eficiente pero permite login corto. 
             # Idealmente el cliente debería enviar el email completo.
             all_users = sess.execute(select(User)).scalars().all()
             for u in all_users:
                 if _norm(u.email) == identifier or _norm(u.email.split('@')[0]) == identifier:
                     user = u
                     break
        
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        
        token = uuid.uuid4().hex
        
        # Guardar sesión en DB
        new_session = UserSession(token=token, user_id=user.id)
        sess.add(new_session)
        sess.commit()
        
        return {
            "token": token, 
            "email": user.email, 
            "name": user.name, 
            "is_admin": user.is_admin
        }

@app.post("/api/logout")
def logout(x_dashboard_token: Optional[str] = Header(None)):
    if not x_dashboard_token:
        raise HTTPException(status_code=401, detail="Missing token")
        
    with Session(engine) as sess:
        sess.execute(delete(UserSession).where(UserSession.token == x_dashboard_token))
        sess.commit()
    
    return {"status": "logged_out"}

# --- Gestión de Usuarios (Admin) ---

@app.get("/api/admin/users", response_model=List[UserResponseSchema])
def list_users(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        users = sess.execute(select(User)).scalars().all()
        return users

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
            is_admin=payload.is_admin
        )
        sess.add(new_user)
        sess.commit()
        sess.refresh(new_user)
        return new_user

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

@app.post("/api/admin/users/{user_id}/servers")
def assign_servers_to_user(user_id: int, payload: ServerAssignmentSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        target_user = sess.get(User, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
        
        # Buscar los servidores por server_id (string)
        servers = sess.execute(select(Server).where(Server.server_id.in_(payload.server_ids))).scalars().all()
        
        target_user.servers = servers
        sess.commit()
        return {"status": "assigned", "count": len(servers)}

@app.get("/api/admin/users/{user_id}/servers")
def get_user_servers(user_id: int, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        target_user = sess.get(User, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
        
        return [s.server_id for s in target_user.servers]

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
        sess.commit()
        return {"status": "registered", "server_id": payload.server_id}


@app.get("/api/servers")
def list_servers(user: dict = Depends(get_current_user_from_token)):
    with Session(engine) as sess:
        servers = sess.execute(select(Server)).scalars().all()
        return [
            {
                "server_id": s.server_id, 
                "created_at": str(s.created_at), 
                "group_name": s.group_name,
                "report_interval": s.report_interval
            } 
            for s in servers
        ]

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


# --- Destinatarios de Alertas (Alert Recipients) ---

@app.get("/api/admin/recipients", response_model=List[AlertRecipientSchema])
def list_alert_recipients(user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        recipients = sess.execute(select(AlertRecipient)).scalars().all()
        return recipients

@app.post("/api/admin/recipients", response_model=AlertRecipientSchema)
def create_alert_recipient(payload: AlertRecipientCreateSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        existing = sess.execute(select(AlertRecipient).where(AlertRecipient.email == payload.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        
        new_recipient = AlertRecipient(email=payload.email, name=payload.name)
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
            emails=json.dumps(payload.emails)
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

@app.put("/api/admin/servers/{server_id}/group")
def update_server_group(server_id: str, payload: ServerUpdateGroupSchema, user: dict = Depends(require_admin)):
    with Session(engine) as sess:
        srv = sess.execute(select(Server).where(Server.server_id == server_id)).scalar_one_or_none()
        if not srv:
            raise HTTPException(status_code=404, detail="Servidor no encontrado")
        srv.group_name = payload.group_name
        sess.commit()
        return {"status": "updated", "group_name": srv.group_name}


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
            docker_containers=json.dumps([c.model_dump() for c in payload.docker.containers])
        )
        sess.add(m)
        sess.commit()

        # Verificar Alertas
        try:
            # Cargar configuración de alertas
            alert_cfg = sess.execute(select(AlertConfig)).scalar_one_or_none()
            
            if alert_cfg:
                # Datos completos para el correo
                full_metrics = payload.model_dump()

                current_time = time.time()
                
                # Check CPU
                if alert_cfg.cpu_total_percent > 0 and payload.cpu.total >= alert_cfg.cpu_total_percent:
                    key = (payload.server_id, "cpu")
                    last_sent = _alert_state.get(key, 0)
                    if current_time - last_sent > ALERT_COOLDOWN:
                        recipients, applied_rules = get_alert_recipients(sess, srv, "cpu")
                        print(f"[ALERT] Sending CPU alert for {srv.server_id}. Applied rules: {applied_rules}")
                        send_alert_email(payload.server_id, "CPU Alta", payload.cpu.total, alert_cfg.cpu_total_percent, recipients, full_metrics)
                        _alert_state[key] = current_time
                        
                # Check Memory
                mem_percent = (payload.memory.used / payload.memory.total) * 100 if payload.memory.total > 0 else 0
                if alert_cfg.memory_used_percent > 0 and mem_percent >= alert_cfg.memory_used_percent:
                    key = (payload.server_id, "memory")
                    last_sent = _alert_state.get(key, 0)
                    if current_time - last_sent > ALERT_COOLDOWN:
                        recipients, applied_rules = get_alert_recipients(sess, srv, "memory")
                        print(f"[ALERT] Sending Memory alert for {srv.server_id}. Applied rules: {applied_rules}")
                        send_alert_email(payload.server_id, "Memoria Alta", mem_percent, alert_cfg.memory_used_percent, recipients, full_metrics)
                        _alert_state[key] = current_time

                # Check Disk
                if alert_cfg.disk_used_percent > 0 and payload.disk.percent >= alert_cfg.disk_used_percent:
                    key = (payload.server_id, "disk")
                    last_sent = _alert_state.get(key, 0)
                    if current_time - last_sent > ALERT_COOLDOWN:
                        recipients, applied_rules = get_alert_recipients(sess, srv, "disk")
                        print(f"[ALERT] Sending Disk alert for {srv.server_id}. Applied rules: {applied_rules}")
                        send_alert_email(payload.server_id, "Disco Lleno", payload.disk.percent, alert_cfg.disk_used_percent, recipients, full_metrics)
                        _alert_state[key] = current_time

        except Exception as e:
            print(f"Error verificando alertas: {e}")

        # Actualizar caché en memoria
        try:
            entry = {
                "server_id": payload.server_id,
                "ts": str(m.ts),
                "memory": payload.memory.model_dump(),
                "cpu": payload.cpu.model_dump(),
                "disk": payload.disk.model_dump(),
                "docker": payload.docker.model_dump(),
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

# --- Servir Frontend (debe ir al final) ---
frontend_path = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"Advertencia: No se encontró el frontend en {frontend_path}")
