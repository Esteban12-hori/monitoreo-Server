# 🧩 Sistema de Monitoreo Integral para Servidores Linux (sin Docker)

Un sistema modular de monitoreo en tiempo real sin dependencia de Docker. Incluye:
- Agente ligero (Python)
- Backend (FastAPI + SQLite)
- Dashboard web estático (React + Chart.js)

---

## 🚀 Características
- Agente envía métricas de memoria, CPU, disco y contenedores Docker (si están presentes en el host).
- API segura con tokens por servidor y autenticación para dashboard.
- Dashboard con gráficos en tiempo real e histórico.
- Alertas configurables desde el panel.

---

## 📦 Estructura
- `agent/python/agent.py`: agente de métricas
- `server/app/`: backend FastAPI
- `frontend/`: UI estática
- `scripts/`: instaladores del agente, backend y frontend (Windows y Linux/macOS)

---

## 🧪 Demo del Dashboard
1. Iniciar servidor estático local:
   ```bash
   cd frontend/
   python -m http.server 8000
   ```
2. Abrir: `http://localhost:8000/index.html?demo=1`

---

## ⚙️ Backend (FastAPI)
Requiere `python >= 3.10`.

Instalación rápida (instalador interactivo):
```bash
# Linux/macOS
./scripts/install_backend.sh

# Windows (PowerShell)
./scripts/install_backend.ps1
```

El instalador:
- Crea un `venv` dedicado para el backend.
- Instala dependencias desde `server/requirements.txt`.
- Genera scripts de ejecución: `run_backend.sh` y `run_backend.ps1`.
- Opcionalmente configura TLS directo (ruta a `.key` y `.crt`).

Ejecución tras la instalación:
```bash
# Linux/macOS
./run_backend.sh

# Windows (PowerShell)
./run_backend.ps1
```

Instalación manual (alternativa):
```bash
python3 -m venv /opt/monitor/venv
/opt/monitor/venv/bin/pip install -r server/requirements.txt
```

Iniciar detrás de Nginx (recomendado):
```bash
/opt/monitor/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir server
```

TLS directo (autofirmado):
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server/certs/server.key -out server/certs/server.crt \
  -subj "/CN=tu-dominio.com"
/opt/monitor/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile server/certs/server.key \
  --ssl-certfile server/certs/server.crt \
  --app-dir server
```

Variables opcionales:
```bash
export DASHBOARD_TOKEN="<token>"
export CACHE_MAX_ITEMS=1000
```

---

## 🔌 Endpoints
- `POST /api/register`: registra `server_id` y `token`
- `POST /api/metrics`: ingesta (header `X-Auth-Token`)
- `GET /api/servers`: listado (requiere login de dashboard)
- `GET /api/metrics/history`: historial
- `GET/POST /api/alerts`: alertas
- `POST /api/login` / `POST /api/logout`: sesión de dashboard
- `GET /api/health`: salud backend

---

## 🧠 Agente (Python)
Instalación rápida:
- Windows: `./scripts/install_agent.ps1`
- Linux/macOS: `./scripts/install_agent.sh`

El asistente verificará dependencias, pedirá parámetros y guardará `agent/python/agent.config.json`.

Ejecutar agente:
```bash
python agent/python/agent.py --config agent/python/agent.config.json
```
Opcional sin config:
```bash
python agent/python/agent.py --server https://tu-dominio --server-id srv-01 --token TOKEN_SRV_01 --interval 5 --verify /etc/ssl/certs/ca-certificates.crt
```

Diagnóstico:
```bash
python agent/python/diagnose.py
```

Logs: `agent/python/logs/agent.log`

---

## 🖼️ Frontend (estático)
Despliegue rápido (instalador interactivo):
```bash
# Linux/macOS
./scripts/install_frontend.sh

# Windows (PowerShell)
./scripts/install_frontend.ps1
```

El instalador:
- Copia los archivos estáticos de `frontend/` al web root indicado (por ejemplo, `/var/www/monitor/frontend`).
- Opcionalmente genera una configuración Nginx desde la plantilla `deploy/nginx/host.conf.template`.
- Muestra instrucciones para habilitar el sitio y recargar Nginx.

Plantilla Nginx disponible:
- `deploy/nginx/host.conf.template` con placeholders de `server_name`, upstream de backend y `root` del frontend.

---

## 🧩 Despliegue en Producción (sin Docker)
1. Backend con Uvicorn (ver sección Backend).
2. Frontend estático en Nginx (`/var/www/monitor/frontend`).
3. Proxy `/api` a Uvicorn.

Ejemplo Nginx:
```nginx
server {
  listen 443 ssl;
  server_name tu-dominio.com;

  ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

  location /api/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $host;
  }
  location / {
    root /var/www/monitor/frontend;
    index index.html;
    try_files $uri /index.html;
  }
}
```

Requisitos: `nginx`, `openssl/certbot`, puertos `80/443` abiertos.
 
Sugerencia: usar los instaladores
- Backend: `./scripts/install_backend.sh` o `./scripts/install_backend.ps1` para crear venv y scripts de ejecución.
- Frontend: `./scripts/install_frontend.sh` o `./scripts/install_frontend.ps1` para copiar estáticos y generar config Nginx.

---

## 🧩 Flujo de Datos Real
1. `POST /api/register` con `server_id` + `token`
2. Ejecutar agente
3. Login en dashboard (`/api/login`)
4. Consultar historial y alertas

---

## 🛠️ Solución de Problemas
- 404 en `/api/*`: revisar Nginx y que Uvicorn esté activo.
- 403 en `/api/metrics`: token no coincide con registro.
- TLS: ajustar `--verify` con CA del sistema.
- Backend sin respuesta: verificar `/api/health` local (`http://127.0.0.1:8001/api/health`).
 - Diagnóstico backend: `python scripts/diagnose_backend.py --url http://127.0.0.1:8001`

---

## ℹ️ Nota
El proyecto no incluye ni soporta despliegue con Docker. Todos los pasos están pensados para entornos sin contenedores.