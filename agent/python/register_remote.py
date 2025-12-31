import requests
import json
import platform
import uuid
from pathlib import Path

SERVER_URL = "http://20.153.165.55"
CONFIG_PATH = Path(__file__).resolve().parent / "agent.config.json"

def register_and_configure():
    # Generar ID y Token únicos
    hostname = platform.node()
    server_id = f"{hostname}-{uuid.uuid4().hex[:6]}"
    token = uuid.uuid4().hex

    print(f"Intentando registrar en {SERVER_URL}...")
    print(f"  Server ID: {server_id}")
    print(f"  Token:     {token}")

    try:
        resp = requests.post(f"{SERVER_URL}/api/register", json={
            "server_id": server_id,
            "token": token
        }, timeout=10)
        
        if resp.status_code == 200:
            print("\n✅ Registro exitoso!")
            
            config = {
                "server": SERVER_URL,
                "server_id": server_id,
                "token": token,
                "interval": 5,
                "verify": ""
            }
            
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            print(f"📄 Configuración guardada en: {CONFIG_PATH}")
            print("\nAhora puedes iniciar el agente con:")
            print(f"python3 agent/python/agent.py")
        else:
            print(f"\n❌ Falló el registro. Código: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"\n❌ Error de conexión: {e}")

if __name__ == "__main__":
    # Asegurar dependencias básicas (aunque install.py ya lo hace, esto es standalone)
    try:
        import requests
    except ImportError:
        print("Instalando requests...")
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "pip", "install", "requests"]
        try:
            subprocess.check_call(cmd)
        except:
            cmd.append("--break-system-packages")
            subprocess.check_call(cmd)
        import requests

    register_and_configure()
