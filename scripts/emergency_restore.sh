#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$ROOT_DIR/server"
DB_DIR="$SERVER_DIR/data"
DB_FILE="$DB_DIR/monitor.db"

if [ ! -d "$DB_DIR" ]; then
  echo "No se encontró el directorio de base de datos: $DB_DIR"
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "No se encontró el archivo de base actual: $DB_FILE"
  exit 1
fi

LATEST_BACKUP="$(ls -1t "$DB_DIR"/monitor*.db 2>/dev/null | grep -v 'monitor.db$' | head -n 1 || true)"

if [ -z "$LATEST_BACKUP" ]; then
  echo "No se encontró ningún backup de monitor.db en $DB_DIR"
  exit 1
fi

echo "Directorio de base: $DB_DIR"
echo "Base actual:        $DB_FILE"
echo "Último backup:      $LATEST_BACKUP"
echo
read -r -p "Restaurar este backup y reiniciar el backend? [Enter para continuar / Ctrl+C para cancelar] " _

TIMESTAMP="$(date +%F-%H%M%S)"
EMERGENCY_BACKUP="$DB_DIR/monitor.db.emergency_$TIMESTAMP"

echo "Creando backup de seguridad de la base actual en: $EMERGENCY_BACKUP"
cp "$DB_FILE" "$EMERGENCY_BACKUP"

echo "Deteniendo servicio monitoreo-backend.service"
sudo systemctl stop monitoreo-backend.service

echo "Restaurando backup como monitor.db"
cp "$LATEST_BACKUP" "$DB_FILE"

echo "Iniciando servicio monitoreo-backend.service"
sudo systemctl start monitoreo-backend.service

echo "Estado del servicio:"
sudo systemctl status monitoreo-backend.service --no-pager -n 5

