import sys
import os
import platform
import json
import re
import time
import subprocess
import argparse
import socket
import uuid
import random
import string
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
        print("Instalación estándar fallida. Intentando con --break-system-packages (necesario en sistemas Linux modernos)...")
        try:
            cmd_force = cmd + ["--break-system-packages"]
            subprocess.check_call(cmd_force)
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


def generate_token(length=32):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Instalador del Agente de Monitoreo")
    parser.add_argument("--server", help="URL del servidor (ej: http://20.153.165.55)")
    parser.add_argument("--server-id", help="ID del servidor (defecto: hostname)")
    parser.add_argument("--token", help="Token de autenticación (defecto: autogenerado)")
    parser.add_argument("--interval", type=int, default=2400, help="Intervalo en segundos (defecto: 2400)")
    parser.add_argument("--verify", help="Ruta CA para TLS")
    parser.add_argument("--auto", action="store_true", help="Modo automático (sin preguntas)")
    args = parser.parse_args()

    print("Instalador del Agente de Monitoreo")
    print("Sistema:", platform.platform())

    print_step("Verificando Python y pip")
    if sys.version_info < (3, 8):
        print("Se requiere Python >= 3.8")
        sys.exit(1)

    ok = ensure_packages(["requests", "psutil"])
    if not ok:
        sys.exit(1)

    # Valores por defecto
    default_id = args.server_id or socket.gethostname()
    default_token = args.token or generate_token()
    default_verify = args.verify or default_verify_path()

    if args.auto:
        print_step("Modo Automático activado")
        server = args.server
        if not server:
            print("Error: En modo --auto debes especificar --server")
            sys.exit(1)
        server_id = default_id
        token = default_token
        interval = args.interval
        verify = default_verify
    else:
        # Modo interactivo
        if args.server:
            # Si ya pasaron servidor, usamos ese como base
            preset_server = args.server
            preset_verify = default_verify
        else:
            preset = choose_preset()
            preset_server = preset["server"]
            preset_verify = preset["verify"] or default_verify

        server = prompt_with_default("URL del servidor de monitoreo (donde se envían los datos)", preset_server) 
        while not validate_url(server):
            print("URL inválida. Debe comenzar con http:// o https://")
            print("Ejemplo: http://20.153.165.55 o https://monitoreo.tu-dominio.com")
            server = input("URL del servidor: ").strip()

        server_id = prompt_with_default("Nombre/ID de este servidor (ej: servidor-produccion)", default_id)
        token = prompt_with_default("Token de autenticación", default_token)
        interval_str = prompt_with_default("Intervalo de envío (seg)", str(args.interval))
        try:
            interval = max(1, int(interval_str))
        except Exception:
            interval = 2400
        verify = prompt_with_default("Ruta CA/cert para TLS (vacío para por defecto)", preset_verify)

    print_step("Comprobando salud del backend")
    if check_backend_health(server):
        print("Backend OK")
    else:
        print("No se pudo verificar /api/health. Continúo, pero revisa tu proxy/Nginx.")

    print_step(f"Registrando servidor (ID: {server_id})")
    ok, info = register_server(server, server_id, token)
    if ok:
        print("Registro exitoso/actualizado:", info)
    else:
        print("Error en registro:", info)
        if args.auto:
            print("Abortando por error de registro en modo auto.")
            sys.exit(1)

    try:
        from security import protect_token
        token_to_save = protect_token(token)
    except ImportError:
        token_to_save = token

    cfg = {
        "server": server,
        "server_id": server_id,
        "token": token_to_save,
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