#!/bin/bash
set -e

# Directorios
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_SRC="$REPO_ROOT/frontend"
WEB_ROOT="/var/www/monitoreo"
NGINX_CONF="/etc/nginx/sites-available/monitoreo"
NGINX_LINK="/etc/nginx/sites-enabled/monitoreo"

echo "=== Configuración del Servidor Web (Nginx) ==="

# 0. Verificar Backend (Facilitar instalación)
if [ ! -f "$REPO_ROOT/.env" ]; then
    echo "⚠️  No se detectó configuración del backend (archivo .env)."
    read -p "¿Deseas ejecutar el instalador del backend primero? (y/N): " RUN_BACKEND
    if [[ "$RUN_BACKEND" =~ ^[Yy]$ ]]; then
        echo "🚀 Iniciando instalador del backend..."
        "$REPO_ROOT/scripts/00_install_backend.sh"
    else
        echo "⚠️  Saltando instalación del backend. Asegúrate de configurarlo manualmente."
    fi
fi

# 1. Verificar Nginx
if ! command -v nginx >/dev/null; then
    echo "⚠️  Nginx no encontrado. Instalando..."
    sudo apt-get update
    sudo apt-get install -y nginx
fi

# 2. Copiar Frontend
echo "📂 Copiando archivos del frontend a $WEB_ROOT..."
sudo mkdir -p "$WEB_ROOT"
sudo cp -r "$FRONTEND_SRC/"* "$WEB_ROOT/"
# Asegurar permisos correctos
sudo chown -R www-data:www-data "$WEB_ROOT"
sudo chmod -R 755 "$WEB_ROOT"

# 3. Configurar Nginx
echo "⚙️  Generando configuración de Nginx..."

# Preguntar por dominio o IP
read -p "Ingresa tu Dominio o IP pública (ej: 20.153.165.55): " SERVER_NAME
if [ -z "$SERVER_NAME" ]; then
    SERVER_NAME="_"
fi

# Crear archivo de configuración
sudo bash -c "cat > $NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    root $WEB_ROOT;
    index index.html;

    # Frontend
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Backend API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# 4. Habilitar sitio
echo "🔗 Habilitando sitio..."
if [ -f "$NGINX_LINK" ]; then
    sudo rm "$NGINX_LINK"
fi
sudo ln -s "$NGINX_CONF" "$NGINX_LINK"

# Remover default si existe (opcional, para evitar conflictos en puerto 80)
if [ -f "/etc/nginx/sites-enabled/default" ]; then
    echo "⚠️  Deshabilitando sitio 'default' de Nginx para evitar conflictos..."
    sudo rm "/etc/nginx/sites-enabled/default"
fi

# 5. Reiniciar Nginx
echo "🔄 Reiniciando Nginx..."
sudo systemctl restart nginx

echo ""
echo "=== ¡Listo! ==="
echo "Ahora puedes acceder a tu panel en: http://$SERVER_NAME"
