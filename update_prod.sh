#!/bin/bash

# Script de actualización automática para el servidor de monitoreo
# Uso: ./update_prod.sh

set -e # Detener script si hay error

echo "========================================"
echo "🚀 Iniciando actualización del Servidor"
echo "========================================"

# 1. Descargar últimos cambios
echo "📥 1. Descargando código fuente (git pull)..."
git pull origin main

# 2. Activar entorno virtual y actualizar dependencias
echo "📦 2. Verificando dependencias Python..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "⚠️  No se encontró .venv, intentando usar python global o creando venv..."
    # Asumimos que el entorno ya está configurado en producción
fi
pip install -r server/requirements.txt

# 3. Aplicar migraciones de base de datos
echo "🗄️  3. Aplicando migraciones de base de datos..."
# Aseguramos que las tablas nuevas y columnas se creen
python server/scripts/migrate_v3.py

# 4. Reiniciar el servicio para aplicar cambios de código
# Detectar si usamos systemd o pm2
echo "🔄 4. Reiniciando servicios..."

if systemctl is-active --quiet monitoreo-backend; then
    echo "   - Reiniciando servicio Systemd 'monitoreo-backend'..."
    sudo systemctl restart monitoreo-backend
    echo "   ✅ Servicio backend reiniciado."
else
    echo "   ⚠️  No se detectó servicio systemd 'monitoreo-backend' activo."
    echo "   Si estás ejecutando manualmente, por favor reinicia el proceso de Python (Ctrl+C y volver a lanzar)."
fi

echo "========================================"
echo "✅ Actualización completada con éxito"
echo "========================================"
