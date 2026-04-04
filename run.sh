#!/usr/bin/env bash
# AlchemyPOS 2 — Launch Script
# Usage:
#   bash run.sh              → dev mode, port 5000
#   bash run.sh prod         → prod mode, port 8000
#   bash run.sh prod 9090    → prod on custom port
#   bash run.sh stop         → kill any running instance

MODE=${1:-dev}
PORT=${2:-}

# ── STOP command ──────────────────────────────────────────
if [ "$MODE" = "stop" ]; then
  echo "[*] Stopping all AlchemyPOS processes..."
  pkill -f "gunicorn.*app:app" 2>/dev/null && echo "[OK] Gunicorn stopped" || echo "[INFO] No gunicorn running"
  pkill -f "python3 app.py"    2>/dev/null && echo "[OK] Dev server stopped" || true
  exit 0
fi

# ── Activate venv ─────────────────────────────────────────
if [ -d "venv" ]; then
  source venv/bin/activate
else
  echo "[ERROR] venv not found. Run: bash setup.sh first"
  exit 1
fi

# ── Kill anything already on the target port ──────────────
if [ "$MODE" = "prod" ]; then
  PORT=${PORT:-8000}
else
  PORT=${PORT:-5000}
fi

EXISTING=$(lsof -ti tcp:$PORT 2>/dev/null)
if [ -n "$EXISTING" ]; then
  echo "[*] Port $PORT in use (PID $EXISTING) — killing..."
  kill -9 $EXISTING 2>/dev/null
  sleep 1
  echo "[OK] Port $PORT cleared"
fi

# ── Start ─────────────────────────────────────────────────
if [ "$MODE" = "prod" ]; then
  echo "AlchemyPOS 2 [PRODUCTION] → http://0.0.0.0:$PORT"
  echo "Share with staff: http://$(hostname -I | awk '{print $1}'):$PORT"
  export FLASK_ENV=production
  exec gunicorn \
    --workers 4 \
    --bind "0.0.0.0:$PORT" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    "app:app"
else
  echo "AlchemyPOS 2 [DEVELOPMENT] → http://localhost:$PORT"
  export FLASK_ENV=development FLASK_DEBUG=1
  exec python3 app.py
fi
