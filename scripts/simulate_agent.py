import requests
import json
import time
import random

BASE_URL = "http://127.0.0.1:8000/api"
SERVER_ID = "local-test-server"
SERVER_TOKEN = "secret-token-123456"

def register_server():
    print(f"Registering server {SERVER_ID}...")
    try:
        resp = requests.post(f"{BASE_URL}/register", json={
            "server_id": SERVER_ID,
            "token": SERVER_TOKEN
        })
        resp.raise_for_status()
        print("Server registered successfully.")
    except Exception as e:
        print(f"Error registering server: {e}")

def send_metrics():
    print("Sending metrics...")
    
    # Simulate Docker containers
    containers = [
        {"name": "nginx-proxy", "cpu": 0.5, "mem": 25.5},
        {"name": "postgres-db", "cpu": 1.2, "mem": 128.0},
        {"name": "redis-cache", "cpu": 0.1, "mem": 12.0},
        {"name": "my-app-backend", "cpu": 5.0, "mem": 256.0}
    ]
    
    payload = {
        "server_id": SERVER_ID,
        "memory": {
            "total": 16000,
            "used": random.uniform(4000, 8000),
            "free": random.uniform(8000, 12000),
            "cache": 2000
        },
        "cpu": {
            "total": random.uniform(5, 30),
            "per_core": [random.uniform(1, 10) for _ in range(8)]
        },
        "disk": {
            "total": 500,
            "used": 200,
            "free": 300,
            "percent": 40.0
        },
        "docker": {
            "running_containers": len(containers),
            "containers": containers
        }
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/metrics", json=payload, headers={
            "x-auth-token": SERVER_TOKEN
        })
        resp.raise_for_status()
        rj = resp.json()
        print(f"Metrics sent successfully. Interval from server: {rj.get('report_interval')}")
    except Exception as e:
        print(f"Error sending metrics: {e}")

if __name__ == "__main__":
    register_server()
    for i in range(3):
        send_metrics()
        time.sleep(1)
    print("\nSimulation complete. Open http://127.0.0.1:8000/ to view the dashboard.")
    print("Use credentials: jguajardo@wingsoft.com / Pombolita1")
