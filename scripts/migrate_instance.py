#!/usr/bin/env python3
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "server"
DATA_DIR = SERVER_DIR / "data"
DB_PATH = DATA_DIR / "monitor.db"
AGENT_CONFIG_PATH = REPO_ROOT / "agent" / "python" / "agent.config.json"
DEFAULT_BACKEND_SERVICE = "monitoreo-backend.service"
DEFAULT_AGENT_SERVICE = "monitoreo-agent.service"
DEFAULT_PM2_NAME = "monitoring-agent"


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def print_step(message: str) -> None:
    print(f"\n==> {message}")


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise SystemExit(f"No se encontró {description}: {path}")


def validate_server_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"URL inválida: {url}")
    return url.rstrip("/")


def run_command(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, text=True)


def service_exists(service_name: str) -> bool:
    result = subprocess.run(
        ["systemctl", "status", service_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode in {0, 3}


def stop_service(service_name: str) -> bool:
    if not shutil.which("systemctl") or not service_exists(service_name):
        return False
    print_step(f"Deteniendo servicio {service_name}")
    run_command(["sudo", "systemctl", "stop", service_name])
    return True


def start_service(service_name: str) -> bool:
    if not shutil.which("systemctl") or not service_exists(service_name):
        return False
    print_step(f"Iniciando servicio {service_name}")
    run_command(["sudo", "systemctl", "start", service_name])
    return True


def restart_service(service_name: str) -> bool:
    if not shutil.which("systemctl") or not service_exists(service_name):
        return False
    print_step(f"Reiniciando servicio {service_name}")
    run_command(["sudo", "systemctl", "restart", service_name])
    return True


def pm2_process_exists(name: str) -> bool:
    if not shutil.which("pm2"):
        return False
    result = subprocess.run(
        ["pm2", "describe", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0


def reload_pm2(name: str) -> bool:
    if not pm2_process_exists(name):
        return False
    print_step(f"Recargando proceso PM2 {name}")
    run_command(["pm2", "reload", name])
    return True


def sqlite_online_backup(src: Path, dest: Path) -> None:
    ensure_exists(src, "la base de datos")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src) as source_conn:
        with sqlite3.connect(dest) as dest_conn:
            source_conn.backup(dest_conn)


def create_manifest(target_dir: Path, extra: dict) -> None:
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "db_source": str(DB_PATH),
    }
    manifest.update(extra)
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def copy_if_exists(src: Path, dest: Path) -> None:
    if src.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def cmd_backup(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve()
    db_path = repo_root / "server" / "data" / "monitor.db"
    ensure_exists(db_path, "la base de datos monitor.db")

    output = Path(args.output).expanduser().resolve()
    if output.is_dir():
        output = output / f"migration_bundle_{now_stamp()}.tar.gz"

    service_was_stopped = False
    if args.stop_backend:
        service_was_stopped = stop_service(args.backend_service)

    try:
        with tempfile.TemporaryDirectory(prefix="monitoreo-migrate-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            bundle_root = temp_dir / "bundle"
            bundle_root.mkdir(parents=True, exist_ok=True)

            print_step("Creando copia consistente de monitor.db")
            sqlite_online_backup(db_path, bundle_root / "monitor.db")

            print_step("Copiando configuración relevante")
            copy_if_exists(repo_root / "server" / ".env", bundle_root / "server.env")
            copy_if_exists(repo_root / ".env", bundle_root / "root.env")
            copy_if_exists(
                repo_root / "deploy" / "nginx" / "default.conf",
                bundle_root / "deploy" / "nginx" / "default.conf",
            )
            copy_if_exists(
                repo_root / "deploy" / "systemd" / "monitoreo-backend.service.example",
                bundle_root / "deploy" / "systemd" / "monitoreo-backend.service.example",
            )
            copy_if_exists(
                repo_root / "agent" / "python" / "agent.config.json",
                bundle_root / "agent.config.json",
            )

            create_manifest(
                bundle_root,
                {
                    "backend_service": args.backend_service,
                    "agent_service": args.agent_service,
                    "repo_root": str(repo_root),
                },
            )

            print_step(f"Empaquetando respaldo en {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(output, "w:gz") as tar:
                tar.add(bundle_root, arcname="migration_bundle")
    finally:
        if service_was_stopped:
            start_service(args.backend_service)

    print("\nRespaldo creado correctamente:")
    print(output)


def cmd_restore(args: argparse.Namespace) -> None:
    bundle = Path(args.bundle).expanduser().resolve()
    ensure_exists(bundle, "el bundle de migración")

    repo_root = Path(args.repo_root).resolve()
    db_path = repo_root / "server" / "data" / "monitor.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    service_was_stopped = False
    if args.stop_backend:
        service_was_stopped = stop_service(args.backend_service)

    try:
        with tempfile.TemporaryDirectory(prefix="monitoreo-restore-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            print_step("Extrayendo bundle")
            with tarfile.open(bundle, "r:gz") as tar:
                tar.extractall(temp_dir)

            root = temp_dir / "migration_bundle"
            ensure_exists(root / "monitor.db", "monitor.db dentro del bundle")

            if db_path.exists():
                backup_path = db_path.with_name(f"monitor.db.pre_restore_{now_stamp()}")
                print_step(f"Guardando respaldo local previo en {backup_path}")
                shutil.copy2(db_path, backup_path)

            print_step("Restaurando monitor.db")
            shutil.copy2(root / "monitor.db", db_path)

            if args.restore_env:
                copy_if_exists(root / "server.env", repo_root / "server" / ".env")
                copy_if_exists(root / "root.env", repo_root / ".env")
    finally:
        if args.restart_backend:
            restart_service(args.backend_service)
        elif service_was_stopped:
            start_service(args.backend_service)

    print("\nRestauración completada.")
    print(f"Base restaurada en: {db_path}")


def load_agent_config(config_path: Path) -> dict:
    ensure_exists(config_path, "agent.config.json")
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_agent_config(config_path: Path, cfg: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")


def cmd_retarget_agent(args: argparse.Namespace) -> None:
    config_path = Path(args.config).expanduser().resolve()
    cfg = load_agent_config(config_path)

    ensure_exists(config_path, "agent.config.json")
    new_url = validate_server_url(args.server_url)
    cfg["server"] = new_url
    if args.verify is not None:
        cfg["verify"] = args.verify

    for required in ("server_id", "token"):
        if not cfg.get(required):
            raise SystemExit(
                f"El archivo {config_path} no tiene '{required}'. No se puede migrar el agente sin esa identidad."
            )

    save_agent_config(config_path, cfg)
    print("\nagent.config.json actualizado correctamente:")
    print(json.dumps(cfg, indent=2))

    restarted = False
    if args.restart_agent:
        restarted = restart_service(args.agent_service)
        if not restarted:
            restarted = reload_pm2(args.pm2_name)
        if not restarted:
            print(
                "\nNo se detectó un servicio systemd ni PM2 para el agente. Reinícialo manualmente."
            )


def cmd_cutover(args: argparse.Namespace) -> None:
    backup_args = argparse.Namespace(
        repo_root=args.repo_root,
        output=args.output,
        stop_backend=args.stop_backend,
        backend_service=args.backend_service,
        agent_service=args.agent_service,
    )
    cmd_backup(backup_args)

    retarget_args = argparse.Namespace(
        config=args.config,
        server_url=args.server_url,
        verify=args.verify,
        restart_agent=args.restart_agent,
        agent_service=args.agent_service,
        pm2_name=args.pm2_name,
    )
    cmd_retarget_agent(retarget_args)

    print("\nCorte preparado.")
    print("Siguiente paso en el nuevo backend:")
    print(f"  python3 scripts/migrate_instance.py restore --bundle {Path(args.output).expanduser().resolve()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Herramienta para respaldar, restaurar y migrar agentes/instancias de monitoreo."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser(
        "backup", help="Crea un bundle con monitor.db y configuración útil."
    )
    backup.add_argument(
        "--repo-root", default=str(REPO_ROOT), help="Ruta raíz del proyecto."
    )
    backup.add_argument(
        "--output",
        default=str(REPO_ROOT / f"migration_bundle_{now_stamp()}.tar.gz"),
        help="Archivo .tar.gz de salida o directorio destino.",
    )
    backup.add_argument(
        "--backend-service",
        default=DEFAULT_BACKEND_SERVICE,
        help="Nombre del servicio backend para detener/reiniciar si hace falta.",
    )
    backup.add_argument(
        "--agent-service",
        default=DEFAULT_AGENT_SERVICE,
        help="Nombre del servicio del agente guardado en el manifest.",
    )
    backup.add_argument(
        "--stop-backend",
        action="store_true",
        help="Detiene el backend durante el backup.",
    )
    backup.set_defaults(func=cmd_backup)

    restore = subparsers.add_parser(
        "restore", help="Restaura monitor.db desde un bundle previamente generado."
    )
    restore.add_argument("--bundle", required=True, help="Ruta al bundle .tar.gz.")
    restore.add_argument(
        "--repo-root", default=str(REPO_ROOT), help="Ruta raíz del proyecto destino."
    )
    restore.add_argument(
        "--backend-service",
        default=DEFAULT_BACKEND_SERVICE,
        help="Nombre del servicio backend.",
    )
    restore.add_argument(
        "--stop-backend",
        action="store_true",
        help="Detiene el backend antes de restaurar.",
    )
    restore.add_argument(
        "--restart-backend",
        action="store_true",
        help="Reinicia el backend al finalizar la restauración.",
    )
    restore.add_argument(
        "--restore-env",
        action="store_true",
        help="Restaura también server/.env y .env si vienen en el bundle.",
    )
    restore.set_defaults(func=cmd_restore)

    retarget = subparsers.add_parser(
        "retarget-agent",
        help="Actualiza agent.config.json para apuntar a otro backend conservando identidad y token.",
    )
    retarget.add_argument("--server-url", required=True, help="Nueva URL/IP del backend.")
    retarget.add_argument(
        "--config",
        default=str(AGENT_CONFIG_PATH),
        help="Ruta al agent.config.json.",
    )
    retarget.add_argument(
        "--verify",
        help="Nuevo valor para verify (ruta CA, cadena vacía o false). Si no se indica, se conserva el actual.",
    )
    retarget.add_argument(
        "--restart-agent",
        action="store_true",
        help="Reinicia el agente tras actualizar la configuración.",
    )
    retarget.add_argument(
        "--agent-service",
        default=DEFAULT_AGENT_SERVICE,
        help="Nombre del servicio systemd del agente.",
    )
    retarget.add_argument(
        "--pm2-name",
        default=DEFAULT_PM2_NAME,
        help="Nombre del proceso PM2 si no hay servicio systemd.",
    )
    retarget.set_defaults(func=cmd_retarget_agent)

    cutover = subparsers.add_parser(
        "cutover",
        help="Crea el backup y reconfigura el agente local para enviar métricas al nuevo backend.",
    )
    cutover.add_argument("--server-url", required=True, help="Nueva URL/IP del backend.")
    cutover.add_argument(
        "--repo-root", default=str(REPO_ROOT), help="Ruta raíz del proyecto."
    )
    cutover.add_argument(
        "--output",
        default=str(REPO_ROOT / f"migration_bundle_{now_stamp()}.tar.gz"),
        help="Archivo .tar.gz del bundle.",
    )
    cutover.add_argument(
        "--backend-service",
        default=DEFAULT_BACKEND_SERVICE,
        help="Nombre del servicio backend.",
    )
    cutover.add_argument(
        "--agent-service",
        default=DEFAULT_AGENT_SERVICE,
        help="Nombre del servicio del agente.",
    )
    cutover.add_argument(
        "--config",
        default=str(AGENT_CONFIG_PATH),
        help="Ruta al agent.config.json.",
    )
    cutover.add_argument(
        "--verify",
        help="Nuevo valor para verify del agente.",
    )
    cutover.add_argument(
        "--restart-agent",
        action="store_true",
        help="Reinicia el agente tras cambiar la URL.",
    )
    cutover.add_argument(
        "--pm2-name",
        default=DEFAULT_PM2_NAME,
        help="Nombre del proceso PM2 del agente.",
    )
    cutover.add_argument(
        "--stop-backend",
        action="store_true",
        help="Detiene el backend durante el backup.",
    )
    cutover.set_defaults(func=cmd_cutover)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
