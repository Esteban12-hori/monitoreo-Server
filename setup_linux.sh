#!/bin/bash
set -e

# Obtener directorio del script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Configuración Automática para Linux ==="

# 1. Asegurar permisos de ejecución
echo "[+] Dando permisos de ejecución a los scripts..."
chmod +x scripts/*.sh

# 2. Verificar python3-venv
echo "[+] Verificando dependencias del sistema..."
if command -v apt-get >/dev/null; then
    if ! dpkg -s python3-venv >/dev/null 2>&1; then
        echo "    python3-venv no encontrado. Instalando..."
        sudo apt-get update
        sudo apt-get install -y python3-venv
    else
        echo "    python3-venv ya está instalado."
    fi
else
    echo "    No es un sistema basado en apt. Asegúrate de tener python3-venv instalado manualmente."
fi

# 3. Ejecutar instalación del backend
echo "[+] Iniciando instalación del Backend..."
# Usamos 'source' o ejecutamos directamente. Mejor ejecutar.
# Pasamos argumentos si los hubiera, o dejamos interactivo.
./scripts/00_install_backend.sh

echo ""
echo "=== Instalación finalizada ==="
echo "Para iniciar el servidor, usa el script generado en scripts/run_backend.sh"
