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


def read_network():
    try:
        counters = psutil.net_io_counters(pernic=False)
        return {
            "bytes_sent": float(counters.bytes_sent),
            "bytes_recv": float(counters.bytes_recv),
            "packets_sent": float(getattr(counters, "packets_sent", 0.0)),
            "packets_recv": float(getattr(counters, "packets_recv", 0.0)),
        }
    except Exception:
        return {
            "bytes_sent": 0.0,
            "bytes_recv": 0.0,
            "packets_sent": 0.0,
            "packets_recv": 0.0,
        }

def read_docker():
    try:
        # 1. Obtener metadatos de contenedores (ID, Name, Image, Status)
        # Usamos docker ps para ver los activos.
        ps_out = subprocess.check_output(["docker", "ps", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"], text=True)
        containers_map = {}
        for line in ps_out.strip().split("\n"):
            if not line: continue
            parts = line.split("|")
            if len(parts) >= 4:
                cid = parts[0]
                containers_map[cid] = {
                    "id": cid,
                    "name": parts[1],
                    "image": parts[2],
                    "status": parts[3],
                    "cpu": 0.0,
                    "mem": 0.0
                }

        # 2. Obtener estadísticas (ID, CPU, Mem)
        stats_out = subprocess.check_output(["docker", "stats", "--no-stream", "--format", "{{.ID}}|{{.CPUPerc}}|{{.MemPerc}}"], text=True)
        for line in stats_out.strip().split("\n"):
            if not line: continue
            parts = line.split("|")
            if len(parts) >= 3:
                cid = parts[0]
                # A veces stats devuelve ID largo o corto, docker ps devuelve corto por defecto. 
                # Tratamos de coincidir.
                target = containers_map.get(cid)
                if not target:
                    # Intento de búsqueda parcial si los IDs difieren en longitud
                    for k in containers_map:
                        if k.startswith(cid) or cid.startswith(k):
                            target = containers_map[k]
                            break
                
                if target:
                    try:
                        target["cpu"] = float(parts[1].replace("%", ""))
                    except:
                        pass
                    try:
                        target["mem"] = float(parts[2].replace("%", ""))
                    except:
                        pass

        container_list = list(containers_map.values())
        return {"running_containers": len(container_list), "containers": container_list}
    except Exception:
        # Fallback simple
        try:
            out = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True)
            names = [n for n in out.strip().split("\n") if n]
            return {"running_containers": len(names), "containers": [{"name": n, "status": "running"} for n in names]}
        except Exception:
            return {"running_containers": 0, "containers": []}


def read_services():
    services = []
    system = platform.system().lower()
    try:
        if system == "windows":
            # Usar PowerShell para obtener servicios (top 100)
            # Quitamos el filtro de Status para ver también los detenidos
            cmd = ["powershell", "-Command", "Get-Service | Select-Object -First 100 Name, DisplayName, Status, RequiredServices | ConvertTo-Json"]
            out = subprocess.check_output(cmd, text=True)
            data = json.loads(out)
            if isinstance(data, dict): data = [data]
            for s in data:
                status_val = "running" if s.get("Status") == 4 else "stopped"
                raw_status = str(s.get("Status", "")).lower()
                if "run" in raw_status or raw_status == "4":
                    status_val = "running"
                else:
                    status_val = "stopped"
                
                reqs = s.get("RequiredServices", [])
                deps = []
                if isinstance(reqs, list):
                    deps = [r.get("Name") for r in reqs if isinstance(r, dict)]
                elif isinstance(reqs, dict):
                    deps = [reqs.get("Name")]
                    
                services.append({
                    "name": s.get("Name", ""),
                    "display_name": s.get("DisplayName", ""),
                    "status": status_val,
                    "dependencies": deps
                })
        elif system == "linux":
            # Systemctl list-units --all
            cmd = ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain", "--no-legend"]
            out = subprocess.check_output(cmd, text=True)
            count = 0
            for line in out.split("\n"):
                if count >= 100: break
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[0]
                    # parts[2] is active/inactive, parts[3] is substate (running/dead)
                    # Example: nginx.service loaded active running A high performance web server
                    status_val = "running" if parts[3] == "running" else "stopped"
                    services.append({
                        "name": name,
                        "display_name": "", 
                        "status": status_val,
                        "version": None # Placeholder
                    })
                    count += 1
    except Exception:
        pass
    return services


def payload(server_id: str):
    return {
        "server_id": server_id,
        "memory": read_memory(),
        "cpu": read_cpu(),
        "disk": read_disk(),
        "docker": read_docker(),
        "services": read_services(),
        "network": read_network(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def execute_command(command: dict):
    cmd_type = command.get("command")
    params = json.loads(command.get("params") or "{}")
    service_name = params.get("service")
    
    result = {"status": "executed", "output": {}}
    
    try:
        if cmd_type.startswith("service_"):
            action = cmd_type.split("_")[1] # start, stop, restart, update
            if platform.system().lower() == "windows":
                # Map 'update' to 'Restart-Service' (force) or just standard actions
                ps_action = {
                    "start": "Start-Service", 
                    "stop": "Stop-Service", 
                    "restart": "Restart-Service",
                    "update": "Restart-Service" 
                }.get(action)
                
                if ps_action:
                    cmd_str = f"{ps_action} -Name '{service_name}'"
                    if action == "update":
                        cmd_str += " -Force"
                    subprocess.check_call(["powershell", "-Command", cmd_str])
                    result["output"] = {"message": f"Service {service_name} {action}ed successfully"}
            elif platform.system().lower() == "linux":
                sys_action = action
                if action == "update":
                    sys_action = "reload-or-restart"
                
                subprocess.check_call(["sudo", "systemctl", sys_action, service_name])
                result["output"] = {"message": f"Service {service_name} {action}ed successfully"}
        else:
             result["status"] = "failed"
             result["output"] = {"error": f"Unknown command {cmd_type}"}
             
    except Exception as e:
        result["status"] = "failed"
        result["output"] = {"error": str(e)}
        
    return result

def check_commands(server_url, server_id, token, verify_tls):
    try:
        resp = requests.get(
            f"{server_url}/api/servers/{server_id}/commands/pending",
            headers={"X-Auth-Token": token},
            timeout=10,
            verify=verify_tls if verify_tls else True
        )
        if resp.status_code == 200:
            commands = resp.json()
            for cmd in commands:
                logging.info(f"Executing command: {cmd['command']}")
                res = execute_command(cmd)
                
                # Report result
                requests.post(
                    f"{server_url}/api/servers/{server_id}/commands/{cmd['id']}/result",
                    json=res,
                    headers={"X-Auth-Token": token},
                    timeout=10,
                    verify=verify_tls if verify_tls else True
                )
    except Exception as e:
        logging.error(f"Error checking commands: {e}")


def loop(server_url: str, server_id: str, token: str, interval: int, verify_tls: str):
    last_metrics_time = 0
    metrics_interval = interval
    command_interval = 10 # Check every 10 seconds
    last_command_time = 0

    logging.info(f"Iniciando bucle de agente. Intervalo métricas: {metrics_interval}s, Comandos: {command_interval}s")

    while True:
        now = time.time()
        
        # Check Commands
        if now - last_command_time >= command_interval:
            check_commands(server_url, server_id, token, verify_tls)
            last_command_time = now

        # Send Metrics
        if now - last_metrics_time >= metrics_interval:
            data = payload(server_id)
            try:
                resp = requests.post(
                    f"{server_url}/api/metrics",
                    json=data,
                    headers={"X-Auth-Token": token},
                    timeout=10,
                    verify=verify_tls if verify_tls else True,
                )
                if resp.status_code == 200:
                    try:
                        rj = resp.json()
                        new_interval = rj.get("report_interval")
                        if new_interval and isinstance(new_interval, int) and new_interval != metrics_interval:
                            logging.info("Actualizando intervalo de %ss a %ss", metrics_interval, new_interval)
                            metrics_interval = new_interval
                    except Exception:
                        pass
                else:
                    logging.error("Error enviando métricas %s %s", resp.status_code, resp.text)
            except Exception as e:
                logging.exception("Excepción enviando métricas: %s", e)
            
            last_metrics_time = now
            
        time.sleep(1)


def load_config(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def setup_logging():
    log_dir = Path(__file__).resolve().parent / "logs"
    log_path = log_dir / "agent.log"
    handlers = []
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        handlers.append(file_handler)
    except Exception as e:
        print(f"No se pudo escribir log en archivo {log_path}: {e}")
    handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
    logging.info("Agente iniciado")


def main():
    parser = argparse.ArgumentParser(description="Agente de monitoreo ligero")
    parser.add_argument("--server", required=False, help="URL del backend (https://host:port)")
    parser.add_argument("--server-id", required=False, help="Identificador del servidor")
    parser.add_argument("--token", help="Token de autenticación", default="")
    parser.add_argument("--interval", help="Intervalo de envío (segundos)", type=int, default=2400)
    parser.add_argument("--verify", default=None, help="Ruta a CA/cert para verificación TLS (o 'false' para desactivar)")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "agent.config.json"), help="Ruta a archivo de configuración")
    args = parser.parse_args()

    setup_logging()
    logging.info("Sistema: %s", platform.platform())

    server = args.server
    server_id = args.server_id
    token = args.token
    interval = args.interval
    verify = args.verify

    cfg = {}
    if not (server and server_id and token):
        cfg = load_config(Path(args.config))

    # Prioridad: Argumento > Config > Default
    server = server or cfg.get("server", "")
    server_id = server_id or cfg.get("server_id", "")
    token = token or cfg.get("token", "")
    
    # Intentar desofuscar token
    try:
        from security import reveal_token
        token = reveal_token(token)
    except ImportError:
        pass

    # Manejo de intervalo
    if args.interval == 2400 and "interval" in cfg:
        interval = cfg.get("interval")

    # Manejo de verify (SSL)
    # Lógica: Si es None (no pasado por arg), mirar config. Si no está en config, True.
    if verify is None:
        verify = cfg.get("verify", True)
    
    # Convertir string "false" a booleano False si viene de argumentos o json texto
    if isinstance(verify, str):
        if verify.lower() == "false":
            verify = False
        elif verify == "":
            verify = True

    if not (server and server_id and token):
        print("Faltan parámetros obligatorios. Usa --config o pasa --server, --server-id y --token.")
        return

    loop(server, server_id, token, interval, verify)


if __name__ == "__main__":
    main()
