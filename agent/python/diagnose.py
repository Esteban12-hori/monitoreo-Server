import json
import platform
import sys
from pathlib import Path
import time

import requests


AGENT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = AGENT_DIR / "agent.config.json"


def read_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check_health(server: str):
    url = server.rstrip("/") + "/api/health"
    try:
        r = requests.get(url, timeout=5)
        ok = r.status_code == 200 and (r.json() or {}).get("ok") is True
        return ok, r.status_code, r.text
    except Exception as e:
        return False, 0, str(e)


def send_probe(server: str, server_id: str, token: str):
    url = server.rstrip("/") + "/api/metrics"
    payload = {
        "server_id": server_id,
        "memory": {"total": 1024.0, "used": 512.0, "free": 512.0, "cache": 128.0},
        "cpu": {"total": 1.0, "per_core": [1.0]},
        "disk": {"total": 10.0, "used": 5.0, "free": 5.0, "percent": 50.0},
        "docker": {"running_containers": 0, "containers": []},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        r = requests.post(url, json=payload, headers={"X-Auth-Token": token}, timeout=10)
        return r.status_code == 200, r.status_code, r.text
    except Exception as e:
        return False, 0, str(e)


def main():
    print("Diagnóstico del Agente")
    print("Sistema:", platform.platform())
    cfg = read_config()
    server = cfg.get("server", "")
    server_id = cfg.get("server_id", "")
    token = cfg.get("token", "")
    if not (server and server_id and token):
        print("Config incompleta. Asegúrate de ejecutar install.py y tener agent.config.json")
        sys.exit(1)

    print("Verificando /api/health en:", server)
    ok, code, text = check_health(server)
    print("  Salud:", ok, code)
    if not ok:
        print("  Respuesta:", text)

    print("Enviando métrica de prueba...")
    ok2, code2, text2 = send_probe(server, server_id, token)
    print("  Métrica:", ok2, code2)
    if not ok2:
        print("  Respuesta:", text2)

    if ok and ok2:
        print("Diagnóstico OK: conectividad y token válidos.")
    else:
        print("Diagnóstico detectó problemas. Revisa URL, proxy/Nginx y token/registro.")


if __name__ == "__main__":
    main()