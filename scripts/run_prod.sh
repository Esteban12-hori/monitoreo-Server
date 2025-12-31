#!/usr/bin/env bash
set -euo pipefail

# Obtener directorio del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$REPO_ROOT/.venv"

# Configuración
HOST="127.0.0.1"
PORT="8001"
WORKERS=4

# Detectar venv
if [ -d "$VENV_DIR" ]; then
    PYTHON="$VENV_DIR/bin/python"
    GUNICORN="$VENV_DIR/bin/gunicorn"
else
    echo "No se encontró .venv en $VENV_DIR"
    exit 1
fi

# Variables de entorno (puedes ajustarlas o cargarlas de un .env)
export DASHBOARD_TOKEN="${DASHBOARD_TOKEN:-}"
export CACHE_MAX_ITEMS="${CACHE_MAX_ITEMS:-500}"

echo "Iniciando Backend con Gunicorn ($WORKERS workers) en $HOST:$PORT..."

# Ejecutar Gunicorn
# -w: número de workers
# -k: tipo de worker (uvicorn)
# --chdir: cambiar al directorio server
# --access-logfile: logs de acceso (- para stdout)
exec "$GUNICORN" \
    -k uvicorn.workers.UvicornWorker \
    -w "$WORKERS" \
    -b "$HOST:$PORT" \
    --chdir "$REPO_ROOT/server" \
    --access-logfile - \
    app.main:app
