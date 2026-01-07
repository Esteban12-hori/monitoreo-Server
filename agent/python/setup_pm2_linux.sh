#!/bin/bash

# Colores
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}==> Iniciando configuración del Agente para Linux con PM2...${NC}"

# 1. Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 no está instalado."
    exit 1
fi

# 2. Instalar pip dependencies
echo -e "${GREEN}==> Instalando dependencias de Python...${NC}"
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

# 3. Verificar/Instalar Node.js y PM2
if ! command -v npm &> /dev/null; then
    echo "Advertencia: npm no encontrado. Por favor instala Node.js y npm primero."
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y nodejs npm"
    echo "  CentOS/RHEL: sudo yum install -y nodejs npm"
    exit 1
fi

if ! command -v pm2 &> /dev/null; then
    echo -e "${GREEN}==> Instalando PM2 globalmente...${NC}"
    sudo npm install -g pm2
else
    echo "PM2 ya está instalado."
fi

# 4. Verificar configuración
if [ ! -f "agent.config.json" ]; then
    echo -e "${GREEN}==> Archivo de configuración no encontrado. Ejecutando instalador...${NC}"
    python3 install.py
fi

# 5. Iniciar PM2
echo -e "${GREEN}==> Iniciando agente con PM2...${NC}"
pm2 start ecosystem.config.js

# 6. Configurar persistencia
echo -e "${GREEN}==> Configurando inicio automático...${NC}"
pm2 save
echo "Para habilitar el inicio automático en boot, ejecuta el comando que te muestre:"
pm2 startup | tail -n 1

echo -e "${GREEN}==> ¡Listo! El agente está corriendo en segundo plano.${NC}"
echo "Comandos útiles:"
echo "  pm2 status"
echo "  pm2 logs monitoring-agent"
