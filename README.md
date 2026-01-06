# Monitor Integral - Sistema de Monitoreo de Servidores

Este proyecto es una solución completa para el monitoreo de servidores en tiempo real. Consta de dos componentes principales: un **Servidor Central** (con Dashboard Web) y un **Agente** ligero que se instala en los servidores a monitorear.

## 🚀 Características Principales

*   **Monitoreo en Tiempo Real:** CPU, Memoria RAM, Disco y Contenedores Docker.
*   **Dashboard Web:** Interfaz moderna (React) servida directamente por el backend para visualizar métricas.
*   **Gestión de Usuarios:** Sistema de Login con roles (Admin/User).
*   **Seguridad Avanzada:**
    *   Protección contra fuerza bruta (Rate Limiting).
    *   Cabeceras de seguridad HTTP (HSTS, CSP, X-Frame-Options).
    *   Validación de Hosts de confianza.
*   **Alertas:** Configuración de umbrales para CPU, Memoria y Disco.
*   **Multi-servidor:** Soporte para registrar y monitorear múltiples nodos desde un solo panel.

---

## 📂 Estructura del Proyecto

```
monitoreo-Server-main/
├── agent/                  # Código del agente de monitoreo (se instala en los nodos)
│   └── python/             # Scripts Python del agente
├── deploy/                 # Archivos de configuración para despliegue
│   ├── nginx/              # Configuración de Nginx
│   └── systemd/            # Servicios Systemd (Linux)
├── frontend/               # Interfaz Web (Dashboard)
│   ├── assets/             # JS y CSS
│   └── index.html          # Entry point
├── scripts/                # Scripts de instalación y utilidades (Windows/Linux)
├── server/                 # Backend (API REST FastAPI)
│   ├── app/                # Código fuente de la aplicación
│   │   ├── config.py       # Configuración y credenciales
│   │   ├── email_utils.py  # Módulo de alertas por correo
│   │   ├── main.py         # Punto de entrada de la API
│   │   ├── models.py       # Modelos de base de datos
│   │   └── schemas.py      # Esquemas Pydantic
│   └── scripts/            # Scripts de gestión del servidor
└── setup_linux.sh          # Script maestro de instalación
```

---

## 📋 Requisitos del Sistema

### Para el Servidor Central (Backend + Web)
*   **Sistema Operativo:** Windows, Linux o macOS.
*   **Python:** Versión 3.10 o superior.
*   **Dependencias:** Listadas en `server/requirements.txt` (FastAPI, SQLAlchemy, Uvicorn, etc.).
*   **Puerto:** 8000 (por defecto) disponible.

### Para el Agente (Servidores a monitorear)
*   **Sistema Operativo:** Linux (Recomendado) o Windows.
*   **Python:** Versión 3.8 o superior.
*   **Dependencias:** `psutil`, `requests` (Listadas en `agent/python/requirements.txt`).
*   **Docker:** (Opcional) Si se desea monitorear contenedores, Docker debe estar instalado y el usuario debe tener permisos para acceder al socket de Docker.

---

## 🛠️ Instalación y Puesta en Marcha

### 1. Servidor Central (Backend + Web)

Hemos organizado la instalación en scripts numerados dentro de la carpeta `scripts/`.

**Opción A: Instalación Rápida (Linux)**
Ejecuta el script maestro desde la raíz:
```bash
./setup_linux.sh
```

**Opción B: Instalación Paso a Paso (Recomendado)**

1.  **Backend (API + Base de Datos):**
    *   **Linux/macOS:** `./scripts/00_install_backend.sh`
    *   **Windows:** `.\scripts\00_install_backend.ps1`
    *   *Acción:* Crea entorno virtual, instala dependencias y genera configuración `.env` (incluyendo correo).

2.  **Frontend y Servidor Web (Nginx):**
    *   **Linux:** `./scripts/02_setup_web.sh`
    *   *Acción:* Instala Nginx, despliega el frontend compilado y configura el proxy inverso.

**Opción C: Ejecución Manual (Desarrollo)**
1.  Crear entorno virtual: `python -m venv .venv`
2.  Activar entorno.
3.  Instalar dependencias: `pip install -r server/requirements.txt`
4.  Crear `.env` (ver `server/app/config.py` para variables).
5.  Ejecutar: `uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload`

**Usuarios Iniciales:**
El sistema crea usuarios por defecto al iniciar (ver `server/app/config.py`).
Scripts de utilidad se encuentran en `server/scripts/` (ej. `create_users_manual.py`).

### 2. Agente (En cada servidor a monitorear)

1.  **Copiar la carpeta `agent/` al servidor destino.**
2.  **Navegar a la carpeta `agent/python`.**
3.  **Ejecutar el script de instalación:**
    *   Este script interactivo te guiará para configurar la URL del servidor central y registrar el nodo.
    ```bash
    python install.py
    ```
    *   O instalación manual:
        1.  Instalar dependencias: `pip install -r requirements.txt`
        2.  Registrar el agente: `python register_remote.py`
        3.  Ejecutar el agente: `python agent.py`
4.  **Ejecución en segundo plano:**
    *   En Linux, se recomienda crear un servicio `systemd` (el script de instalación puede generar uno).
    *   En Windows, se puede usar el Programador de Tareas.

---

## ⚙️ Configuración del Intervalo de Monitoreo

Por defecto, el agente envía métricas cada **2400 segundos** (40 minutos). Para un monitoreo más frecuente (ej. cada 60 segundos), puedes configurar este valor durante la instalación o editando el archivo `agent.config.json` generado en la carpeta del agente:

```json
{
  "server": "...",
  "server_id": "...",
  "token": "...",
  "interval": 60,
  "verify": ""
}
```

---

## 🔔 Sistema de Alertas por Correo

El sistema incluye un módulo robusto de notificaciones por correo electrónico utilizando la API de **Mailjet**.

### 1. Características
*   **Diseño Moderno:** Correos con formato HTML responsivo, encabezados de alerta claros y tablas detalladas de uso de recursos.
*   **Información Detallada:** Incluye porcentajes de uso de CPU, RAM (MB usados/totales) y Disco (GB usados/totales).
*   **Control de Spam:** Implementa un **"Cooldown" de 1 hora**. Si se envía una alerta de "CPU Alto" para el "Servidor-01", no se enviará otra alerta igual hasta que pase 1 hora, evitando saturar la bandeja de entrada.
*   **Destinatarios Múltiples:** Soporta envío a una lista configurable de administradores y usuarios adicionales gestionados en base de datos.

### 2. Configuración (.env)
Las credenciales se configuran en el archivo `.env` o en las variables de entorno del sistema:

```env
# Mailjet API Credentials
EMAIL_API_KEY=tu_api_key
EMAIL_SECRET_KEY=tu_secret_key
EMAIL_SENDER_EMAIL=remitente@dominio.com
EMAIL_SENDER_NAME="Nombre del Remitente"
# Correos base (separados por coma)
EMAIL_RECEIVER_EMAILS=["admin1@dominio.com","admin2@dominio.com"]
```

### 3. Gestión de Destinatarios
Además de los correos configurados en las variables de entorno, el sistema permite añadir destinatarios dinámicamente a través de la base de datos (Tabla `alert_recipients`). Esto permite que otros interesados reciban notificaciones sin reiniciar el servidor.

---

## 🔒 Seguridad

El sistema implementa varias capas de seguridad para proteger la infraestructura:

*   **Autenticación JWT:** Todas las comunicaciones entre el frontend, backend y agentes están firmadas y validadas con tokens JWT.
*   **Rate Limiting:** Protección contra ataques de fuerza bruta en el login y endpoints críticos.
*   **Trusted Hosts:** Middleware que asegura que el servidor solo responda a peticiones desde dominios permitidos.
*   **Validación de Datos:** Uso de Pydantic para asegurar que todos los datos entrantes cumplan con los esquemas esperados.

---

## 🖥️ Ejecución en Segundo Plano (Como Servicio)

### 1. Backend (Servidor Central) - Linux

Se incluye un archivo de ejemplo en `deploy/systemd/monitoreo-backend.service.example`.

1.  **Editar:** Ajusta las rutas (`WorkingDirectory`, `ExecStart`) y el usuario en el archivo.
2.  **Instalar:**
    ```bash
    sudo cp deploy/systemd/monitoreo-backend.service.example /etc/systemd/system/monitoreo-backend.service
    sudo systemctl daemon-reload
    sudo systemctl enable monitoreo-backend
    sudo systemctl start monitoreo-backend
    ```

### 2. Agente - Linux (Systemd)

Para que el agente se ejecute automáticamente al iniciar el sistema y funcione en segundo plano, sigue estos pasos:

1.  Crear un archivo de servicio: `sudo nano /etc/systemd/system/monitor-agent.service`
2.  Pegar el siguiente contenido (ajustando las rutas):

    ```ini
    [Unit]
    Description=Agente de Monitoreo
    After=network.target

    [Service]
    Type=simple
    User=root
    WorkingDirectory=/ruta/a/monitoreo-Server-main/agent/python
    ExecStart=/usr/bin/python3 /ruta/a/monitoreo-Server-main/agent/python/agent.py
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```
3.  Recargar systemd y activar el servicio:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable monitor-agent
    sudo systemctl start monitor-agent
    ```

### 🪟 Windows (Programador de Tareas)

1.  Abrir el **Programador de Tareas** (Task Scheduler).
2.  Crear una **Tarea Básica**.
3.  **Nombre:** "Agente Monitoreo".
4.  **Desencadenador:** "Al iniciar el sistema" (When the computer starts).
5.  **Acción:** "Iniciar un programa".
6.  **Programa/Script:** Ruta a tu ejecutable de Python (ej: `C:\Windows\py.exe` o `python.exe`).
7.  **Argumentos:** La ruta completa al script `agent.py`. Ejemplo:
    ```text
    "C:\Users\Usuario\Desktop\monitoreo-Server-main\agent\python\agent.py"
    ```
8.  **Iniciar en:** La carpeta donde está el script. Ejemplo:
    ```text
    C:\Users\Usuario\Desktop\monitoreo-Server-main\agent\python\
    ```
9.  Finalizar y luego abrir las **Propiedades** de la tarea:
    *   Marcar "Ejecutar tanto si el usuario inició sesión como si no" (Run whether user is logged on or not).
    *   Marcar "No iniciar una nueva instancia si la tarea ya se está ejecutando".

---

### 🔄 Actualización sin Caídas (Zero-Downtime Deployment)

Si estás ejecutando el servidor en producción con **Linux y Systemd** (usando la configuración recomendada con Gunicorn), puedes actualizar el código sin detener el servicio ni desconectar a los usuarios activos.

1.  **Descargar los cambios:**
    ```bash
    cd /ruta/a/monitoreo-Server-main
    git pull origin main
    ```

2.  **Actualizar dependencias (si es necesario):**
    ```bash
    source .venv/bin/activate
    pip install -r server/requirements.txt
    ```

3.  **Recargar el servicio suavemente:**
    ```bash
    sudo systemctl reload monitoreo-backend
    ```

*Este comando envía una señal `HUP` a Gunicorn, que iniciará nuevos trabajadores con el código actualizado y detendrá los antiguos solo cuando terminen sus tareas pendientes.*

---

## 🔐 Detalles de Seguridad

El sistema implementa varias capas de seguridad para proteger el panel de control y la API:

1.  **Rate Limiting (Límite de Velocidad):**
    *   El endpoint de Login (`/api/login`) está limitado a **5 intentos por minuto** por dirección IP para prevenir ataques de fuerza bruta.
2.  **Cabeceras de Seguridad (Security Headers):**
    *   `X-Frame-Options: DENY`: Previene ataques de Clickjacking.
    *   `X-Content-Type-Options: nosniff`: Evita sniffing de tipos MIME.
    *   `Content-Security-Policy (CSP)`: Mitiga ataques XSS restringiendo las fuentes de scripts y estilos.
3.  **Trusted Hosts:**
    *   El servidor solo procesa peticiones dirigidas a hosts permitidos (configurado en `main.py`).
4.  **Autenticación:**
    *   Uso de Tokens para sesiones de usuario y comunicación Agente-Servidor.
    *   Contraseñas almacenadas con hashing seguro (Bcrypt).

---

## 📂 Estructura del Proyecto

```text
monitoreo-Server-main/
├── agent/                  # Código del Agente de monitoreo
│   ├── python/             # Scripts Python del agente
│   └── ...
├── frontend/               # Archivos estáticos del Dashboard (HTML, JS, CSS)
├── server/                 # Backend FastAPI
│   ├── app/
│   │   ├── config.py       # Configuración global y usuarios por defecto
│   │   ├── main.py         # Punto de entrada de la aplicación
│   │   ├── models.py       # Modelos de Base de Datos (SQLAlchemy)
│   │   ├── schemas.py      # Esquemas Pydantic
│   │   └── ...
│   └── requirements.txt    # Dependencias del servidor
├── data/                   # Base de datos SQLite (generada automáticamente)
└── README.md               # Este archivo
```

## ❓ Solución de Problemas Frecuentes

*   **Error "NameError: name 'limiter' is not defined":** Asegúrate de haber instalado `slowapi` y reiniciado el servidor.
*   **El Dashboard no carga:** Verifica que la carpeta `frontend` exista en la raíz y que el servidor tenga permisos de lectura.
*   **El Agente no conecta:** Verifica que la URL del servidor sea accesible desde el nodo del agente y que no haya firewalls bloqueando el puerto 8000.
