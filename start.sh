#!/usr/bin/env bash
# Launch the FastAPI backend (port 8000) and the Vite React frontend (port 5173) together.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VENV="$ROOT/backend/.venv"

if [ -x "$VENV/bin/python" ]; then
  PY="$VENV/bin/python"
elif [ -x "$VENV/Scripts/python.exe" ]; then
  PY="$VENV/Scripts/python.exe"
else
  echo ">> Creating backend virtualenv"
  "${PYTHON:-python3}" -m venv "$VENV"
  if [ -x "$VENV/bin/python" ]; then PY="$VENV/bin/python"; else PY="$VENV/Scripts/python.exe"; fi
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r "$ROOT/backend/requirements.txt"
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo ">> Installing frontend dependencies"
  (cd "$ROOT/frontend" && npm install)
fi

cleanup() {
  echo ">> Shutting down"
  [ -n "${BACK_PID:-}" ] && kill "$BACK_PID" 2>/dev/null || true
  [ -n "${FRONT_PID:-}" ] && kill "$FRONT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ">> Starting FastAPI backend on http://localhost:$BACKEND_PORT"
(cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT") &
BACK_PID=$!

echo ">> Starting Vite frontend on http://localhost:$FRONTEND_PORT"
(cd "$ROOT/frontend" && VITE_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" npx vite --port "$FRONTEND_PORT" --host 0.0.0.0) &
FRONT_PID=$!

wait -n "$BACK_PID" "$FRONT_PID"
