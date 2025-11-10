import argparse
import json
import platform
import subprocess
import time
from datetime import datetime

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
                print("Error enviando métricas", resp.status_code, resp.text)
        except Exception as e:
            print("Excepción enviando métricas:", e)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Agente de monitoreo ligero")
    parser.add_argument("--server", required=True, help="URL del backend (https://host:port)")
    parser.add_argument("--server-id", required=True, help="Identificador del servidor")
    parser.add_argument("--token", required=True, help="Token de autenticación")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo de envío en segundos")
    parser.add_argument("--verify", default="", help="Ruta a CA/cert para verificación TLS (opcional)")
    args = parser.parse_args()

    print("Sistema:", platform.platform())
    loop(args.server, args.server_id, args.token, args.interval, args.verify)


if __name__ == "__main__":
    main()