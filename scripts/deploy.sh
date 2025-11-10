#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso: ./scripts/deploy.sh [-t TOKEN] [-c CACHE] [-p PORT]

  -t TOKEN   Valor para DASHBOARD_TOKEN (opcional)
  -c CACHE   Tamaño de caché en memoria (por defecto 500)
  -p PORT    Puerto externo para Nginx/web (por defecto 80)
  -h         Mostrar esta ayuda

Despliega el backend FastAPI y el frontend con Nginx usando Docker Compose.
EOF
}

TOKEN=""
CACHE=500
PORT=80

while getopts ":t:c:p:h" opt; do
  case "$opt" in
    t) TOKEN="$OPTARG" ;;
    c) CACHE="$OPTARG" ;;
    p) PORT="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) echo "Opción inválida: -$OPTARG" >&2; usage; exit 1 ;;
  esac
done

echo "Verificando Docker..."
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker no está instalado o no está en PATH." >&2
  exit 1
fi

echo "Detectando Docker Compose..."
COMPOSE=""
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose no encontrado. Instale Docker Compose v2 (docker compose) o v1 (docker-compose)." >&2
  exit 1
fi

echo "Configurando variables de entorno..."
export DASHBOARD_TOKEN="$TOKEN"
export CACHE_MAX_ITEMS="$CACHE"
export WEB_PORT="$PORT"

echo "Iniciando despliegue con $COMPOSE..."
$COMPOSE up -d --build

echo "Despliegue completado."
echo "Frontend: http://localhost:$PORT"
echo "Backend Health: http://localhost:$PORT/api/health"