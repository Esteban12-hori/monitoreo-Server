import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import uuid
import unicodedata

from .config import DB_PATH, DEFAULT_ALERTS, ALLOWED_ORIGINS, DASHBOARD_TOKEN, CACHE_MAX_ITEMS, ALLOWED_USERS
from .models import Base, Server, Metric, AlertConfig
from .schemas import MetricsIngestSchema, RegisterServerSchema, AlertConfigSchema, LoginSchema


def get_engine():
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    return engine


engine = get_engine()
Base.metadata.create_all(engine)

app = FastAPI(title="Monitor Integral")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def ensure_default_alerts(sess: Session):
    cfg = sess.execute(select(AlertConfig)).scalar_one_or_none()
    if not cfg:
        cfg = AlertConfig(
            cpu_total_percent=DEFAULT_ALERTS["cpu_total_percent"],
            memory_used_percent=DEFAULT_ALERTS["memory_used_percent"],
            disk_used_percent=DEFAULT_ALERTS["disk_used_percent"],
        )
        sess.add(cfg)
        sess.commit()


@app.on_event("startup")
def startup():
    with Session(engine) as sess:
        ensure_default_alerts(sess)


# Caché en memoria de métricas recientes por servidor
_cache: dict[str, list[dict]] = {}
_cache_order: dict[str, int] = {}

# Sesiones en memoria: token -> { email, name }
_sessions: dict[str, dict] = {}


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    try:
        s = unicodedata.normalize('NFKD', s)
        s = ''.join(c for c in s if not unicodedata.combining(c))
    except Exception:
        pass
    return s


def _check_dashboard_token(x_dashboard_token: Optional[str]):
    # Requiere token válido ya sea por env o sesión creada via login
    if DASHBOARD_TOKEN:
        if x_dashboard_token == DASHBOARD_TOKEN:
            return
    # Validar token de sesión
    if x_dashboard_token and x_dashboard_token in _sessions:
        return
    raise HTTPException(status_code=401, detail="Unauthorized dashboard token")


@app.post("/api/login")
def login(payload: LoginSchema):
    identifier = _norm(payload.email or "")
    password = (payload.password or "").strip()
    user = None
    # Buscar por correo exacto
    for email, info in ALLOWED_USERS.items():
        if _norm(email) == identifier:
            user = {"email": email, **info}
            break
    # Si no se encontró, buscar por nombre (usuario)
    if not user:
        for email, info in ALLOWED_USERS.items():
            if _norm(info.get("name", "")) == identifier:
                user = {"email": email, **info}
                break
    # Si no se encontró, probar con usuario corto (parte local del correo antes de @)
    if not user:
        for email, info in ALLOWED_USERS.items():
            local = email.split('@')[0]
            if _norm(local) == identifier:
                user = {"email": email, **info}
                break
    if not user or user.get("password") != password:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = uuid.uuid4().hex
    _sessions[token] = {"email": user.get("email"), "name": user.get("name")}
    return {"token": token, "email": user.get("email"), "name": user.get("name")}


@app.post("/api/logout")
def logout(x_dashboard_token: Optional[str] = Header(None)):
    if x_dashboard_token and x_dashboard_token in _sessions:
        _sessions.pop(x_dashboard_token, None)
        return {"status": "logged_out"}
    raise HTTPException(status_code=401, detail="Unauthorized dashboard token")


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
def list_servers(x_dashboard_token: Optional[str] = Header(None)):
    _check_dashboard_token(x_dashboard_token)
    with Session(engine) as sess:
        servers = sess.execute(select(Server)).scalars().all()
        return [{"server_id": s.server_id, "created_at": str(s.created_at)} for s in servers]


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
        return {"status": "ok"}


@app.get("/api/metrics/history")
def metrics_history(server_id: Optional[str] = None, limit: int = 100, x_dashboard_token: Optional[str] = Header(None)):
    _check_dashboard_token(x_dashboard_token)
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
def get_alerts(x_dashboard_token: Optional[str] = Header(None)):
    _check_dashboard_token(x_dashboard_token)
    with Session(engine) as sess:
        cfg = sess.execute(select(AlertConfig)).scalar_one()
        return {
            "cpu_total_percent": cfg.cpu_total_percent,
            "memory_used_percent": cfg.memory_used_percent,
            "disk_used_percent": cfg.disk_used_percent,
        }


@app.post("/api/alerts")
def set_alerts(payload: AlertConfigSchema, x_dashboard_token: Optional[str] = Header(None)):
    _check_dashboard_token(x_dashboard_token)
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
    except Exception:
        return {"ok": False}