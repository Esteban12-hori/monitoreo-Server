# Sistema de Monitoreo Integral para Servidores Linux

Este proyecto provee un sistema distribuido de monitoreo con:
- Agente ligero (Python) por servidor para recolectar métricas.
- Backend (FastAPI) con almacenamiento histórico (SQLite) y API segura.
- Dashboard web (React vía CDN + Chart.js) para visualización en tiempo real e histórico, gestión de alertas y múltiples servidores.

## Métricas soportadas
- Memoria RAM: total, usada, libre, caché.
- CPU: utilización total y por núcleo.
- Disco: disponible, usado, porcentaje.
- Docker: contenedores activos y métricas básicas.

## Arquitectura
- `agent/python/agent.py`: agente que recolecta y envía métricas.
- `server/app`: API con FastAPI, SQLite (SQLAlchemy) y endpoints.
- `frontend`: dashboard React (CDN), sin build, servido por HTTP simple.

Comunicación segura:
- TLS/HTTPS entre agente y backend. Soporta certificados autofirmados.
- Token de autenticación por servidor (header `X-Auth-Token`).
- Token de dashboard para lectura (header `X-Dashboard-Token`).

## Puesta en marcha (demo UI)
1. Abrir una terminal en `frontend/` y ejecutar:
   ```
   python -m http.server 8000
   ```
2. Navegar a `http://localhost:8000/index.html?demo=1` para ver datos simulados.

## Backend (FastAPI)
Requiere Python 3.10+.

1. Instalar dependencias:
   ```
   pip install -r server/requirements.txt
   ```
2. Generar certificados TLS (opcional pero recomendado):
   ```
   # Ejemplo con OpenSSL (autofirmado)
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout server/certs/server.key -out server/certs/server.crt \
     -subj "/CN=localhost"
   ```
3. Ejecutar el servidor:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile server/certs/server.key --ssl-certfile server/certs/server.crt --app-dir server
   ```

Protección de lectura (opcional):
- Establecer variable de entorno `DASHBOARD_TOKEN="<token>"` antes de arrancar.
- El frontend enviará el token en el header `X-Dashboard-Token` si se pasa `?token=<token>` en la URL o se guarda en `localStorage`.

Endpoints principales:
- `POST /api/register`: registra un servidor y devuelve/establece token.
- `POST /api/metrics`: ingesta de métricas (header `X-Auth-Token`).
- `GET /api/servers`: listado de servidores registrados.
- `GET /api/metrics/history?server_id=...&limit=...`: historial para gráficos.
- `GET/POST /api/alerts`: obtener/actualizar umbrales.

## Agente (Python)
1. Configurar variables (ver `agent/python/agent.py`).
2. Instalar dependencias:
   ```
   pip install -r agent/python/requirements.txt
   ```
3. Ejecutar en cada servidor Linux:
   ```
   python agent.py --server https://<dashboard-host>:8443 --server-id <ID> --token <TOKEN>
   ```

Notas:
- Bajo consumo: usa lecturas periódicas con psutil y llamadas a Docker minimalistas.
- Compatible con Ubuntu/CentOS/Debian.

Montaje de disco:
- El agente selecciona automáticamente un punto de montaje válido (en Linux `/`, en otros la primera partición) para medir uso de disco.

## Seguridad y almacenamiento
- SQLite para datos históricos (`server/data/monitor.db`). Se recomienda migrar a PostgreSQL en producción.
- TLS obligatorio en producción. Los agentes verifican el certificado del servidor.
- Tokens por servidor para autenticación de ingesta.
- Token opcional de dashboard para proteger endpoints de lectura.

## Integración
- API REST JSON para integraciones externas.
- Fácil de extender con webhooks o SSE/WebSockets.

## Flujo con datos reales
1. Registrar cada servidor: `POST /api/register` con `server_id` y `token`.
2. Ejecutar el agente con `--server`, `--server-id`, `--token`.
3. Configurar token de dashboard (opcional) y abrir el frontend sin `?demo=1`.
4. El dashboard consultará `/api/health`, `/api/servers`, `/api/metrics/history` y `/api/alerts` en vivo.

## Caché y rendimiento
- El backend mantiene una caché en memoria de métricas recientes por servidor (configurable con `CACHE_MAX_ITEMS`).
- Las consultas de historial intentan responder desde caché y caen a SQLite si es necesario.

## Próximos pasos sugeridos
- Reemplazar UI CDN por build con Vite/React.
- Añadir WebSockets/SSE para tiempo real sin polling.
- Exportación a Prometheus/OpenTelemetry.
 
## Despliegue en servidor (backend y dashboard)

Pasos para desplegar en un servidor Linux (Ubuntu/Debian/CentOS):

1. Requisitos
   - `python >= 3.10`, `nginx` (recomendado), `openssl` o `certbot`.
   - Puertos `80/443` accesibles si usas Nginx.

2. Preparar entorno backend
   ```bash
   python3 -m venv /opt/monitor/venv
   /opt/monitor/venv/bin/pip install -r server/requirements.txt
   ```

3. TLS
   - Opción A (recomendado): TLS en Nginx y Uvicorn sin TLS en `127.0.0.1:8001`:
     ```bash
     /opt/monitor/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir server
     ```
   - Opción B (pruebas): TLS directo en Uvicorn con certificados autofirmados:
     ```bash
     openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
       -keyout server/certs/server.key -out server/certs/server.crt \
       -subj "/CN=tu-dominio.com"
     /opt/monitor/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8443 \
       --ssl-keyfile server/certs/server.key --ssl-certfile server/certs/server.crt --app-dir server
     ```

4. Variables de entorno
   - `DASHBOARD_TOKEN="<token_dashboard>"` (opcional, protege lectura del dashboard)
   - `CACHE_MAX_ITEMS="1000"` (opcional)

5. Frontend (dashboard)
   - Copiar `frontend/` a `/var/www/monitor/frontend`.
   - Nginx (ejemplo):
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
       }
     }
     ```

6. Verificación
   - `GET https://tu-dominio.com/api/health` → `{ "ok": true }`.
   - UI LIVE: `https://tu-dominio.com/index.html` o `?token=<DASHBOARD_TOKEN>` si activaste token.

## Uso del agente en servidores Linux (paso a paso)

1. Preparar entorno
   ```bash
   python3 -m venv ~/monitor-agent
   ~/monitor-agent/bin/pip install -r agent/python/requirements.txt
   ```

2. Registrar servidor
   ```bash
   curl -X POST "https://tu-dominio.com/api/register" \
     -H "Content-Type: application/json" \
     -d '{"server_id":"srv-01","token":"TOKEN_SRV_01"}'
   ```

3. Ejecutar agente
   ```bash
   ~/monitor-agent/bin/python /ruta/a/agent/python/agent.py \
     --server https://tu-dominio.com --server-id srv-01 --token TOKEN_SRV_01 \
     --interval 5 --verify /etc/ssl/certs/ca-certificates.crt
   ```
   - `--verify` debe apuntar a la CA del sistema (p. ej. `/etc/ssl/certs/ca-certificates.crt`).

4. Opcional: servicio systemd
   - `/etc/systemd/system/monitor-agent.service`:
     ```ini
     [Unit]
     Description=Monitor Agent
     After=network.target

     [Service]
     Type=simple
     ExecStart=/home/ubuntu/monitor-agent/bin/python /opt/monitor/agent/python/agent.py \
       --server https://tu-dominio.com --server-id srv-01 --token TOKEN_SRV_01 \
       --interval 5 --verify /etc/ssl/certs/ca-certificates.crt
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
   - Activar: `sudo systemctl daemon-reload && sudo systemctl enable --now monitor-agent`

## Gestión de alertas (`GET/POST /api/alerts`)

Consultar alertas:
```bash
curl -s "https://tu-dominio.com/api/alerts" \
  -H "X-Dashboard-Token: <DASHBOARD_TOKEN>"
```

Actualizar umbrales:
```bash
curl -X POST "https://tu-dominio.com/api/alerts" \
  -H "Content-Type: application/json" \
  -H "X-Dashboard-Token: <DASHBOARD_TOKEN>" \
  -d '{
    "cpu_total_percent": 85,
    "memory_used_percent": 80,
    "disk_used_percent": 90
  }'
```

Notas:
- Si no configuras `DASHBOARD_TOKEN`, los endpoints de lectura son públicos.
- El frontend envía el token automáticamente si abres `index.html?token=<DASHBOARD_TOKEN>`.

## Resolución de problemas
- Banner rojo en el dashboard: indica backend no disponible o falta de token; revisa `/api/health` y el parámetro `?token=`.
- Agente sin ingesta: valida `server_id` registrado y el `X-Auth-Token` del agente.
- TLS: si hay errores de certificado, confirma que `--verify` apunte a la CA correcta o usa Nginx con Let’s Encrypt.#   m o n i t o r e o - S e r v e r  
 