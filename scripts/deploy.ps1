Param(
  [string]$Token = "",
  [int]$CacheMaxItems = 500,
  [int]$WebPort = 80
)

Write-Host "Iniciando despliegue con Docker Compose..." -ForegroundColor Cyan

# Verificar Docker
try {
  docker --version | Out-Null
} catch {
  Write-Error "Docker no está instalado o no está en PATH. Instale Docker Desktop."
  exit 1
}

# Establecer variables de entorno para Compose
$env:DASHBOARD_TOKEN = $Token
$env:CACHE_MAX_ITEMS = $CacheMaxItems
$env:WEB_PORT = $WebPort

# Construir e iniciar
docker compose up -d --build

if ($LASTEXITCODE -ne 0) {
  Write-Error "Error durante docker compose up. Revise los logs."
  exit $LASTEXITCODE
}

Write-Host "Despliegue completado." -ForegroundColor Green
Write-Host "Frontend: http://localhost:$WebPort" -ForegroundColor Yellow
Write-Host "Backend Health: http://localhost:$WebPort/api/health" -ForegroundColor Yellow

# Mostrar estado
docker compose ps