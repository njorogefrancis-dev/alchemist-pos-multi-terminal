#!/usr/bin/env bash
set -e
echo "╔══════════════════════════════════════════╗"
echo "║   AlchemyPOS 2 — Point of Sale System    ║"
echo "║   Setup Script                           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Python check
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  echo "[ERROR] Python 3.9+ required. Found: $PY_MAJOR.$PY_MINOR"; exit 1
fi
echo "[OK] Python $PY_MAJOR.$PY_MINOR"

# Install system dependencies needed to build psycopg2
echo "[*] Installing system dependencies (requires sudo)..."
sudo apt-get install -y \
  libpq-dev \
  python3-dev \
  build-essential \
  gcc \
  -q 2>/dev/null || {
    echo "[WARN] apt-get failed — trying without sudo (may already be installed)"
  }
echo "[OK] System dependencies ready"

# Venv
[ -d "venv" ] && rm -rf venv
echo "[*] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "[OK] Virtual environment ready"

# Deps
echo "[*] Installing Python dependencies (this may take 1-2 minutes)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "[OK] Dependencies installed"

# .env
if [ ! -f ".env" ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > .env <<ENVEOF
SECRET_KEY=$SECRET
FLASK_ENV=development
DATABASE_URL=postgresql://alchemypos:alchemypos@localhost/alchemypos
# ANTHROPIC_API_KEY=sk-ant-...
ENVEOF
  echo "[OK] .env created"
else
  echo "[OK] .env already exists"
fi

mkdir -p backups
echo "[OK] Backup directory ready"

echo ""
echo "═══════════════════════════════════════════"
echo " Make sure PostgreSQL is running and the"
echo " database exists before continuing:"
echo ""
echo "   sudo systemctl start postgresql"
echo "   sudo -u postgres psql"
echo "   CREATE USER alchemypos WITH PASSWORD 'alchemypos';"
echo "   CREATE DATABASE alchemypos OWNER alchemypos;"
echo "   \\q"
echo "═══════════════════════════════════════════"
echo ""

# DB init
echo "[*] Initialising database..."
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('  Tables created successfully')
" && echo "[OK] Database ready" || echo "[WARN] DB init failed — check PostgreSQL is running and DATABASE_URL in .env"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Setup complete!                         ║"
echo "║  Run:  bash run.sh prod 8000             ║"
echo "║  Open: http://localhost:8000             ║"
echo "╚══════════════════════════════════════════╝"
