import argparse
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
import logging
from pathlib import Path

import psutil
import requests


def read_memory():
    vm = psutil.virtual_memory()
    return {
        "total": float(vm.total) / (1024 ** 2),
        "used": float(vm.used) / (1024 ** 2),
        "free": float(vm.available) / (1024 ** 2),
        "cache": float(getattr(vm, "cached", 0)) / (1024 ** 2),
    }


def read_cpu():
    total = psutil.cpu_percent(interval=1)
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    return {"total": total, "per_core": per_core}


def read_disk():
    # Seleccionar un punto de montaje válido (Linux: '/', Windows: primera partición)
    mountpoint = "/"
    try:
        parts = psutil.disk_partitions()
        if parts:
            mountpoint = parts[0].mountpoint or mountpoint
    except Exception:
        pass
    du = psutil.disk_usage(mountpoint)
    return {
        "total": float(du.total) / (1024 ** 3),
        "used": float(du.used) / (1024 ** 3),
        "free": float(du.free) / (1024 ** 3),
        "percent": du.percent,
    }


def read_docker():
    try:
        out = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True)
        names = [n for n in out.strip().split("\n") if n]
        return {"running_containers": len(names), "containers": [{"name": n} for n in names]}
    except Exception:
        return {"running_containers": 0, "containers": []}


def payload(server_id: str):
    return {
        "server_id": server_id,
        "memory": read_memory(),
        "cpu": read_cpu(),
        "disk": read_disk(),
        "docker": read_docker(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def loop(server_url: str, server_id: str, token: str, interval: int, verify_tls: str):
    while True:
        data = payload(server_id)
        try:
            resp = requests.post(
                f"{server_url}/api/metrics",
                json=data,
                headers={"X-Auth-Token": token},
                timeout=10,
                verify=verify_tls if verify_tls else True,
            )
            if resp.status_code != 200:
                logging.error("Error enviando métricas %s %s", resp.status_code, resp.text)
        except Exception as e:
            logging.exception("Excepción enviando métricas: %s", e)
        time.sleep(interval)


def load_config(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def setup_logging():
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "agent.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.info("Agente iniciado")


def main():
    parser = argparse.ArgumentParser(description="Agente de monitoreo ligero")
    parser.add_argument("--server", required=False, help="URL del backend (https://host:port)")
    parser.add_argument("--server-id", required=False, help="Identificador del servidor")
    parser.add_argument("--token", help="Token de autenticación", default="")
    parser.add_argument("--interval", help="Intervalo de envío (segundos)", type=int, default=2400)
    parser.add_argument("--verify", default="", help="Ruta a CA/cert para verificación TLS (opcional)")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "agent.config.json"), help="Ruta a archivo de configuración")
    args = parser.parse_args()

    setup_logging()
    logging.info("Sistema: %s", platform.platform())

    server = args.server
    server_id = args.server_id
    token = args.token
    interval = args.interval
    verify = args.verify

    if not (server and server_id and token):
        cfg = load_config(Path(args.config))
        server = server or cfg.get("server", "")
        server_id = server_id or cfg.get("server_id", "")
        token = token or cfg.get("token", "")
        
        # Intentar desofuscar token
        try:
            from security import reveal_token
            token = reveal_token(token)
        except ImportError:
            pass

        interval = cfg.get("interval", interval)
        verify = cfg.get("verify", verify)

    if not (server and server_id and token):
        print("Faltan parámetros obligatorios. Usa --config o pasa --server, --server-id y --token.")
        return

    loop(server, server_id, token, interval, verify)


if __name__ == "__main__":
    main()