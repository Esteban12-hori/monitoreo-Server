import sys
import os
import platform
import json
import re
import time
import subprocess
from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
CONFIG_PATH = AGENT_DIR / "agent.config.json"
LOG_DIR = AGENT_DIR / "logs"


def print_step(title):
    print("\n==> " + title)


def ensure_packages(packages):
    missing = []
    for p in packages:
        try:
            __import__(p)
        except Exception:
            missing.append(p)
    if not missing:
        return True
    print_step(f"Instalando dependencias: {', '.join(missing)}")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + missing
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        print("Error instalando paquetes. Ejecuta manualmente:")
        print(" ", " ".join(cmd))
        return False


def default_verify_path():
    # CA bundle por sistema
    if platform.system() == "Windows":
        return ""
    if platform.system() == "Darwin":
        return "/etc/ssl/cert.pem"
    # Linux comunes
    for candidate in [
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
    ]:
        if Path(candidate).exists():
            return candidate
    return ""


def validate_url(url):
    return bool(re.match(r"^https?://[\w\.-]+(?::\d+)?(?:/.*)?$", url.strip()))


def prompt_with_default(prompt, default):
    val = input(f"{prompt} [{default}]: ").strip()
    return val or default


def choose_preset():
    print("\nSelecciona un caso de uso:")
    print("  1) Desarrollo local (Nginx + backend en 8080): http://localhost:8080")
    print("  2) Producción con Nginx y dominio (HTTPS): https://monitoreo.tu-dominio.com")
    print("  3) Uvicorn con TLS directo (8443): https://host:8443")
    choice = input("Opción [1/2/3]: ").strip() or "1"
    if choice == "1":
        return {"server": "http://localhost:8080", "verify": ""}
    if choice == "2":
        return {"server": "https://monitoreo.tu-dominio.com", "verify": default_verify_path()}
    if choice == "3":
        return {"server": "https://localhost:8443", "verify": default_verify_path()}
    print("Opción no válida, usando 1.")
    return {"server": "http://localhost:8080", "verify": ""}


def check_backend_health(server):
    import requests
    url = server.rstrip("/") + "/api/health"
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200 and (r.json() or {}).get("ok") is True
    except Exception:
        return False


def register_server(server, server_id, token):
    import requests
    url = server.rstrip("/") + "/api/register"
    try:
        r = requests.post(url, json={"server_id": server_id, "token": token}, timeout=10)
        if r.status_code == 200:
            return True, r.json()
        return False, {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        return False, {"error": str(e)}


def write_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print_step(f"Configuración guardada en: {CONFIG_PATH}")


def main():
    print("Instalador del Agente de Monitoreo")
    print("Sistema:", platform.platform())

    print_step("Verificando Python y pip")
    if sys.version_info < (3, 8):
        print("Se requiere Python >= 3.8")
        sys.exit(1)

    ok = ensure_packages(["requests", "psutil"])
    if not ok:
        sys.exit(1)

    preset = choose_preset()
    server = prompt_with_default("URL del backend", preset["server"]) 
    while not validate_url(server):
        print("URL inválida. Ej: https://monitoreo.tu-dominio.com")
        server = input("URL del backend: ").strip()

    server_id = prompt_with_default("Identificador del servidor", "srv-01")
    token = prompt_with_default("Token de autenticación", "TOKEN_SRV_01")
    interval_str = prompt_with_default("Intervalo de envío (seg)", "5")
    try:
        interval = max(1, int(interval_str))
    except Exception:
        interval = 5
    verify_default = preset.get("verify") or default_verify_path()
    verify = prompt_with_default("Ruta CA/cert para TLS (vacío para por defecto)", verify_default)

    print_step("Comprobando salud del backend")
    if check_backend_health(server):
        print("Backend OK")
    else:
        print("No se pudo verificar /api/health. Continúo, pero revisa tu proxy/Nginx.")

    print_step("Registrando servidor (si no existe)")
    ok, info = register_server(server, server_id, token)
    if ok:
        print("Registro actualizado:", info)
    else:
        print("No se pudo registrar automáticamente:", info)

    cfg = {
        "server": server,
        "server_id": server_id,
        "token": token,
        "interval": interval,
        "verify": verify,
    }
    write_config(cfg)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print_step("Instalación completada")
    print("Puedes iniciar el agente con:")
    print(f"  {sys.executable} {AGENT_DIR / 'agent.py'} --config {CONFIG_PATH}")
    print("Para diagnóstico:")
    print(f"  {sys.executable} {AGENT_DIR / 'diagnose.py'}")


if __name__ == "__main__":
    main()