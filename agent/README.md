# Instalación y Configuración del Agente

Objetivo: instalar y configurar el agente en menos de 5 minutos.

## Requisitos
- Python 3.8 o superior
- Acceso al backend (FastAPI) vía `http` o `https`

## Guía Rápida
- Windows:
  - `./scripts/install_agent.ps1`
- Linux/macOS:
  - `./scripts/install_agent.sh`

El asistente:
- Verifica dependencias (psutil, requests)
- Pide URL del backend, `server_id`, `token`, `interval` y `verify`
- Valida `/api/health` y registra el servidor en `/api/register`
- Guarda `agent/python/agent.config.json`

## Ejecutar el agente
```
python agent/python/agent.py --config agent/python/agent.config.json
```
O con parámetros:
```
python agent/python/agent.py --server https://mi-dominio --server-id srv-01 --token TOKEN --interval 5 --verify /ruta/a/ca.crt
```

## Ejecución como Servicio (Producción)

Para mantener el agente corriendo en segundo plano y que se inicie automáticamente con el sistema, recomendamos usar **Systemd** (en Linux) o el **Programador de Tareas** (en Windows).

### 🐧 Linux (Systemd)

Hemos incluido un script automático para configurar el servicio:

1.  Navega a la carpeta del agente:
    ```bash
    cd agent/python
    ```
2.  Ejecuta el script de instalación del servicio:
    ```bash
    chmod +x setup_service.sh
    ./setup_service.sh
    ```
    *Este script creará un servicio llamado `monitoreo-agent.service`, lo habilitará y lo iniciará.*

**Comandos útiles:**
*   Ver estado: `sudo systemctl status monitoreo-agent`
*   Ver logs: `journalctl -u monitoreo-agent -f`
*   Reiniciar: `sudo systemctl restart monitoreo-agent`
*   Parar: `sudo systemctl stop monitoreo-agent`

### 🪟 Windows (Servicio)

En Windows, recomendamos usar el **Programador de Tareas** para iniciar el script al arrancar el sistema:

1.  Abre el "Programador de Tareas".
2.  Crea una nueva tarea básica "Monitoreo Agent".
3.  Desencadenador: "Al iniciar el sistema".
4.  Acción: "Iniciar un programa".
    *   Programa: `pythonw.exe` (Usa `pythonw` en lugar de `python` para evitar la ventana de consola).
    *   Argumentos: `C:\ruta\completa\a\agent\python\agent.py`

## Ejecución Manual en Segundo Plano (Sin Systemd)

Si no puedes o no quieres usar Systemd, puedes usar `nohup` en Linux para dejar el proceso corriendo:

```bash
cd agent/python
nohup python agent.py > agent.log 2>&1 &
```

*   `nohup`: Evita que el proceso muera al cerrar la terminal.
*   `> agent.log 2>&1`: Guarda la salida en `agent.log`.
*   `&`: Ejecuta en segundo plano.

Para detenerlo:
```bash
pkill -f agent.py
```

## Diagnóstico
```
python agent/python/diagnose.py
```
Comprueba `/api/health` y envía una métrica de prueba.

## Opciones avanzadas
- `verify`: ruta al certificado de CA para TLS.
- `interval`: segundos entre envíos.
- Logs: `agent/python/logs/agent.log`.

## Problemas comunes
- 404 en `/api/*`: revisar proxy/Nginx y rutas.
- 403 en `/api/metrics`: token no coincide con `server_id` registrado.
- TLS fallido: verificar `verify` apunta a la CA correcta.