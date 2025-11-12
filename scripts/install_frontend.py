import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
NGINX_TEMPLATE = REPO_ROOT / "deploy" / "nginx" / "host.conf.template"


def print_step(msg):
    print(f"\n==> {msg}")


def default_web_root():
    if os.name == "nt":
        return Path.home() / "monitor" / "frontend"
    return Path("/var/www/monitor/frontend")


def main():
    print("Instalador del Frontend (estático) - sin Docker")
    print_step("Destino de archivos del frontend")
    webroot_input = input(f"Ruta destino [{default_web_root()}]: ").strip()
    webroot = Path(webroot_input) if webroot_input else default_web_root()
    webroot.mkdir(parents=True, exist_ok=True)

    print_step("Copiando archivos del frontend")
    # Copiar contenido manteniendo estructura
    for item in FRONTEND_DIR.iterdir():
        dest = webroot / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    print("Frontend copiado en:", webroot)

    if os.name != "nt":
        print_step("Generando configuración Nginx (opcional)")
        gen = (input("¿Crear conf de Nginx? (Y/n): ").strip().lower() or "y") == "y"
        if gen:
            server_name = input("server_name (dominio): ").strip() or "tu-dominio.com"
            upstream = input("Backend upstream [http://127.0.0.1:8001]: ").strip() or "http://127.0.0.1:8001"
            conf_path_input = input("Ruta conf Nginx [/etc/nginx/sites-available/monitor.conf]: ").strip() or "/etc/nginx/sites-available/monitor.conf"
            conf_path = Path(conf_path_input)
            tpl = NGINX_TEMPLATE.read_text(encoding="utf-8")
            tpl = tpl.replace("{{SERVER_NAME}}", server_name)
            tpl = tpl.replace("{{BACKEND_UPSTREAM}}", upstream)
            tpl = tpl.replace("{{WEB_ROOT}}", str(webroot))
            conf_path.parent.mkdir(parents=True, exist_ok=True)
            conf_path.write_text(tpl, encoding="utf-8")
            print("Conf escrita en:", conf_path)
            print("Recuerda habilitar el sitio y recargar Nginx:")
            print("  sudo ln -sf /etc/nginx/sites-available/monitor.conf /etc/nginx/sites-enabled/monitor.conf")
            print("  sudo nginx -t && sudo systemctl reload nginx")

    print_step("Instalación del frontend completada")


if __name__ == "__main__":
    main()