@echo off
set "REPO_ROOT=%~dp0.."
set "FRONTEND_DIR=%REPO_ROOT%\frontend"
set PORT=8000

echo Sirviendo frontend desde %FRONTEND_DIR% en el puerto %PORT%...
start /B python -m http.server %PORT% --directory "%FRONTEND_DIR%" > frontend.log 2>&1
echo Frontend ejecutandose en segundo plano.
echo Log: frontend.log
