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