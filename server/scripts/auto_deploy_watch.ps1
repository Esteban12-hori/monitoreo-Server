# Vigía de auto-actualización del servidor (Windows).
#
# Pensado para ejecutarse periódicamente vía el Programador de Tareas: compara
# el HEAD local contra origin/main y, solo si hay commits nuevos, dispara
# update_prod.ps1 (git pull + dependencias + migraciones + reinicio).
# Si no hay cambios, no hace nada.

$ErrorActionPreference = "Stop"

$Branch = "main"
$RepoDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogFile = Join-Path $RepoDir "logs\auto_deploy.log"

New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null

function Write-Log($Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] $Message"
}

Set-Location $RepoDir

git fetch origin $Branch --quiet

$LocalRev = git rev-parse HEAD
$RemoteRev = git rev-parse "origin/$Branch"

if ($LocalRev -eq $RemoteRev) {
    exit 0
}

Write-Log "Cambios detectados en origin/$Branch ($LocalRev -> $RemoteRev). Ejecutando update_prod.ps1..."

try {
    & "$RepoDir\update_prod.ps1" *>> $LogFile
    Write-Log "✅ Auto-actualización completada correctamente."
} catch {
    Write-Log "⚠️  Falló la auto-actualización: $_"
    exit 1
}
