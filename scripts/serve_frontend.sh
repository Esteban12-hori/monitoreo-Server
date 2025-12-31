#!/bin/bash
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
PORT=8000

echo "Sirviendo frontend desde $FRONTEND_DIR en el puerto $PORT..."
nohup python3 -m http.server $PORT --directory "$FRONTEND_DIR" > frontend.log 2>&1 &
echo "Frontend ejecutándose en segundo plano (PID $!)."
echo "Log: frontend.log"
