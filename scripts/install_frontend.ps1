Param(
  [string]$PythonPath = "python"
)

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot = Join-Path $ScriptDir ".."

& $PythonPath (Join-Path $RepoRoot "scripts\install_frontend.py")