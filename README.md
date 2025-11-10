
# 🧩 Sistema de Monitoreo Integral para Servidores Linux

Un sistema **modular y distribuido** de monitoreo en tiempo real para entornos Linux.  
Incluye agente ligero, API segura y un panel web interactivo con gráficos y alertas.

---

## 🚀 Características Principales

- 🐍 **Agente ligero (Python)**: recolecta métricas del sistema.
- ⚙️ **Backend (FastAPI)**: gestiona almacenamiento, tokens y API segura.
- 📊 **Dashboard Web (React + Chart.js)**: visualiza métricas en tiempo real e histórico.
- 🧠 **Gestión de alertas**: define umbrales personalizados.
- 🔐 **Autenticación y TLS**: tokens únicos y soporte de certificados autofirmados.

---

## 📈 Métricas Soportadas

| Categoría | Métricas |
|------------|-----------|
| **Memoria RAM** | Total, usada, libre, caché |
| **CPU** | Uso total y por núcleo |
| **Disco** | Espacio disponible, usado y porcentaje |
| **Docker** | Contenedores activos, estado y uso básico |

---

## 🏗️ Arquitectura del Sistema

```

Agente (Python)  →  Backend (FastAPI + SQLite)  →  Dashboard (React + Chart.js)

```

**Estructura de carpetas:**
```

agent/python/agent.py      → Recolecta y envía métricas
server/app/                → Backend con FastAPI y SQLAlchemy
frontend/                  → Dashboard web vía CDN (sin build)

````

### 🔒 Comunicación Segura

- HTTPS / TLS entre agente y backend  
- Token único por servidor (`X-Auth-Token`)  
- Token de lectura opcional para dashboard (`X-Dashboard-Token`)

---

## 🧪 Demo del Dashboard

1. Iniciar un servidor HTTP simple:
 
   cd frontend/
   python -m http.server 8000


2. Abrir en el navegador:

   
   http://localhost:8000/index.html?demo=1
 
---

## ⚙️ Backend (FastAPI)

Requiere **Python 3.10+**

### Instalación

```bash
pip install -r server/requirements.txt
```

### Generar certificados TLS (recomendado)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server/certs/server.key -out server/certs/server.crt \
  -subj "/CN=localhost"
```

### Iniciar servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile server/certs/server.key \
  --ssl-certfile server/certs/server.crt \
  --app-dir server
```

**Variables opcionales:**

```bash
export DASHBOARD_TOKEN="<token>"
export CACHE_MAX_ITEMS=1000
```

---

## 🔌 Endpoints Principales

| Método       | Endpoint               | Descripción                              |
| ------------ | ---------------------- | ---------------------------------------- |
| `POST`       | `/api/register`        | Registra un servidor y devuelve token    |
| `POST`       | `/api/metrics`         | Envía métricas (requiere `X-Auth-Token`) |
| `GET`        | `/api/servers`         | Lista de servidores registrados          |
| `GET`        | `/api/metrics/history` | Historial por servidor                   |
| `GET / POST` | `/api/alerts`          | Obtiene o actualiza umbrales de alerta   |

---

## 🧠 Agente (Python)

1. Configurar variables en `agent/python/agent.py`
2. Instalar dependencias:

   ```bash
   pip install -r agent/python/requirements.txt
   ```
3. Ejecutar:

   ```bash
   python agent.py --server https://<host>:8443 --server-id <ID> --token <TOKEN>
   ```

**Notas:**

* Bajo consumo: usa `psutil` y llamadas ligeras a Docker.
* Compatible con Ubuntu / Debian / CentOS.

---

## 🧰 Seguridad y Almacenamiento

* Base de datos: **SQLite** (migrable a PostgreSQL en producción)
* Comunicación segura con **TLS obligatorio**
* Tokens individuales por servidor
* Token opcional de dashboard para acceso de solo lectura

---

## 🌐 Integraciones

* API REST JSON
* Extensible con **Webhooks**, **SSE** o **WebSockets**
* Exportación futura: **Prometheus / OpenTelemetry**

---

## ⚡ Flujo con Datos Reales

1. Registrar servidor vía `POST /api/register`
2. Ejecutar agente con su `server_id` y `token`
3. Configurar `DASHBOARD_TOKEN` (opcional)
4. Abrir dashboard sin `?demo=1`

---

## 🧩 Despliegue en Producción

### 🔧 Requisitos

* `python >= 3.10`, `nginx`, `openssl` o `certbot`
* Puertos `80` y `443` abiertos

### 🖥️ Configuración del Backend

```bash
python3 -m venv /opt/monitor/venv
/opt/monitor/venv/bin/pip install -r server/requirements.txt
```

#### Opción A — TLS en Nginx (recomendado)

```bash
/opt/monitor/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir server
```

#### Opción B — TLS directo en Uvicorn (autofirmado)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server/certs/server.key -out server/certs/server.crt \
  -subj "/CN=tu-dominio.com"
uvicorn app.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile server/certs/server.key \
  --ssl-certfile server/certs/server.crt \
  --app-dir server
```

### 🌍 Configuración de Nginx

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

---

## 🧾 Ejemplo de Servicio Systemd (Agente)

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

---

## 🚨 Gestión de Alertas

### Consultar alertas

```bash
curl -s "https://tu-dominio.com/api/alerts" \
  -H "X-Dashboard-Token: <DASHBOARD_TOKEN>"
```

### Actualizar umbrales

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

---

## 🧩 Resolución de Problemas

| Situación                     | Posible causa                     | Solución                                                          |
| ----------------------------- | --------------------------------- | ----------------------------------------------------------------- |
| 🔴 Banner rojo en dashboard   | Backend inactivo o token inválido | Revisa `/api/health` y el parámetro `?token=`                     |
| ⚠️ Agente sin enviar métricas | Token o `server_id` incorrectos   | Revisa configuración del agente                                   |
| 🔐 Error TLS                  | Certificado incorrecto            | Usa `--verify /etc/ssl/certs/ca-certificates.crt` o Let’s Encrypt |



## 📍 Próximos Pasos

* 🔧 Migrar UI a build con **Vite/React**
* 🔄 Añadir **WebSockets/SSE** para métricas en tiempo real
* 📤 Exportar métricas a **Prometheus / OpenTelemetry**



> 🛠️ Desarrollado con ❤️ para entornos Linux modernos.


✅ **Instrucciones:**  
1. Crea un archivo llamado `README.md` en la raíz de tu repositorio.  
2. Copia todo el texto de arriba y pégalo allí.  
3. GitHub lo renderizará automáticamente con íconos, tablas y formato completo.  


