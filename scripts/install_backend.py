#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "server"


def print_step(msg):
    print(f"\n==> {msg}")


def run(cmd, env=None):
    print("$", " ".join(cmd))
    subprocess.check_call(cmd, env=env)


def detect_default_venv():
    return REPO_ROOT / ".venv"


def uvicorn_path(venv: Path):
    if os.name == "nt":
        return str(venv / "Scripts" / "uvicorn.exe")
    return str(venv / "bin" / "uvicorn")


def python_path(venv: Path):
    if os.name == "nt":
        return str(venv / "Scripts" / "python.exe")
    return str(venv / "bin" / "python")


def main():
    print("Instalador del Backend (FastAPI) - sin Docker")
    print_step("Seleccionando ruta de entorno virtual")
    default_venv = detect_default_venv()
    venv_input = input(f"Ruta del venv [{default_venv}]: ").strip()
    venv_path = Path(venv_input) if venv_input else default_venv

    print_step("Creando entorno virtual (si no existe)")
    if not venv_path.exists():
        run([sys.executable, "-m", "venv", str(venv_path)])
    else:
        print("Venv ya existe:", venv_path)

    pip = python_path(venv_path)
    print_step("Instalando dependencias del backend")
    run([pip, "-m", "pip", "install", "--upgrade", "pip"])
    run([pip, "-m", "pip", "install", "-r", str(SERVER_DIR / "requirements.txt")])

    print_step("Configuración básica")
    host = input("Host de escucha [127.0.0.1]: ").strip() or "127.0.0.1"
    port = input("Puerto [8000]: ").strip() or "8000"
    dashboard_token = input("DASHBOARD_TOKEN (opcional) []: ").strip()
    cache_max = input("CACHE_MAX_ITEMS [500]: ").strip() or "500"
    use_tls = (input("¿TLS directo en Uvicorn? (y/N): ").strip().lower() == "y")
    ssl_key = ""
    ssl_cert = ""
    if use_tls:
        ssl_key = input("Ruta ssl keyfile: ").strip()
        ssl_cert = input("Ruta ssl certfile: ").strip()

    run_sh = REPO_ROOT / "scripts" / "run_backend.sh"
    run_ps = REPO_ROOT / "scripts" / "run_backend.ps1"

    print_step("Creando scripts de ejecución")
    # Bash
    run_sh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
export DASHBOARD_TOKEN=""" + dashboard_token + """
export CACHE_MAX_ITEMS=""" + cache_max + """
""" + (f"{uvicorn_path(venv_path)} app.main:app --host {host} --port {port} --app-dir server --ssl-keyfile {ssl_key} --ssl-certfile {ssl_cert}\n" if use_tls else f"{uvicorn_path(venv_path)} app.main:app --host {host} --port {port} --app-dir server\n"),
        encoding="utf-8",
    )
    os.chmod(run_sh, 0o755)

    # PowerShell
    run_ps.write_text(
        """
$env:DASHBOARD_TOKEN = '""" + dashboard_token + """'
$env:CACHE_MAX_ITEMS = '""" + cache_max + """'
""" + (f"& '{uvicorn_path(venv_path)}' app.main:app --host {host} --port {port} --app-dir server --ssl-keyfile '{ssl_key}' --ssl-certfile '{ssl_cert}'\n" if use_tls else f"& '{uvicorn_path(venv_path)}' app.main:app --host {host} --port {port} --app-dir server\n"),
        encoding="utf-8",
    )

    print_step("Instalación completada")
    print("Para iniciar el backend:")
    if os.name == "nt":
        print(f"  .\\scripts\\run_backend.ps1")
    else:
        print(f"  ./scripts/run_backend.sh")
    print("Luego verifica salud:")
    print(f"  curl 'http://{host}:{port}/api/health'")


if __name__ == "__main__":
    main()