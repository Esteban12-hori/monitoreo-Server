#!/bin/bash
#
# Vigía de auto-actualización del servidor.
#
# Pensado para ejecutarse periódicamente (systemd timer o cron): compara el
# HEAD local contra origin/main y, solo si hay commits nuevos, dispara
# update_prod.sh (git pull + dependencias + migraciones + reinicio de
# servicios). Si no hay cambios, no hace nada ni reinicia el servicio.
#
# Ver deploy/systemd/monitoreo-autodeploy.service.example y
# deploy/systemd/monitoreo-autodeploy.timer.example para programarlo.

set -euo pipefail

BRANCH="main"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="$REPO_DIR/logs/auto_deploy.log"

cd "$REPO_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

git fetch origin "$BRANCH" --quiet

LOCAL_REV="$(git rev-parse HEAD)"
REMOTE_REV="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
    exit 0
fi

log "Cambios detectados en origin/$BRANCH ($LOCAL_REV -> $REMOTE_REV). Ejecutando update_prod.sh..."

if ./update_prod.sh >> "$LOG_FILE" 2>&1; then
    log "✅ Auto-actualización completada correctamente."
else
    log "⚠️  Falló la auto-actualización. Revisa el detalle arriba en este mismo log."
    exit 1
fi
