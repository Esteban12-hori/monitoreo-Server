Param(
  [string]$PythonPath = "python"
)

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot = Join-Path $ScriptDir ".."

Write-Host "Instalando agente (Windows)" -ForegroundColor Cyan
& $PythonPath (Join-Path $RepoRoot "agent\python\install.py")