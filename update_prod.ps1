# Script de actualización para Windows (PowerShell)
# Uso: .\update_prod.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 Iniciando actualización del Servidor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Descargar cambios
Write-Host "📥 1. Descargando código fuente (git pull)..." -ForegroundColor Yellow
git pull origin main

# 2. Dependencias
Write-Host "📦 2. Verificando dependencias Python..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    . .venv\Scripts\Activate.ps1
}
pip install -r server/requirements.txt

# 3. Migraciones
Write-Host "🗄️  3. Aplicando migraciones de base de datos..." -ForegroundColor Yellow
$env:PYTHONPATH = "."
python server/scripts/migrate_v3.py

# 4. Reiniciar
Write-Host "🔄 4. Reiniciando servicios..." -ForegroundColor Yellow
Write-Host "⚠️  Si estás ejecutando el servidor en una terminal, presiona Ctrl+C y vuelve a ejecutar 'python server/app/main.py' o el script de inicio." -ForegroundColor Magenta
Write-Host "⚠️  Si usas NSSM o un servicio de Windows, ejecuta: Restart-Service nombre-del-servicio" -ForegroundColor Magenta

Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Actualización completada." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
