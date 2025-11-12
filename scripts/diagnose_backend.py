import sys
import requests


def main():
    url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001").rstrip("/") + "/api/health"
    print("Verificando:", url)
    try:
        r = requests.get(url, timeout=5)
        print("Status:", r.status_code)
        print("Body:", r.text)
        if r.status_code == 200 and (r.json() or {}).get("ok") is True:
            print("Backend OK")
        else:
            print("Backend con problemas o ruta incorrecta.")
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()