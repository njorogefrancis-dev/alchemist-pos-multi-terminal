# AlchemyPOS 2

Browser-based point of sale for local retail networks. Runs on your LAN; staff use any modern browser on desktop or mobile.

**Contact:** njorogefrancis | njorogefrancis.dev@gmail.com | 0115634345

---

## Overview

- Multi-user POS with inventory, reports, settings, user management, backups, and audit log.
- Optional Claude (Anthropic) integration for natural-language product search, cart suggestions, and report summaries. Works without an API key using standard search.
- Responsive layout: compact navigation on small screens; POS uses Products / Cart tabs on phones; admin pages use card layouts where appropriate.

---

## Requirements

- Linux (e.g. Ubuntu 20+, Debian 11+, or similar)
- Python 3.9+
- PostgreSQL 14+
- About 500 MB disk for app and dependencies; more for backups and data

---

## Installation

### 1. Install PostgreSQL

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib libpq-dev -y
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create database role and database

```bash
sudo -u postgres psql
```

In `psql`:

```sql
CREATE USER alchemypos WITH PASSWORD 'alchemypos';
CREATE DATABASE alchemypos OWNER alchemypos;
GRANT ALL PRIVILEGES ON DATABASE alchemypos TO alchemypos;
\q
```

Adjust user, password, and database name if you prefer; then set `DATABASE_URL` in `.env` to match.

### 3. Install the application

From the project directory:

```bash
bash setup.sh
```

This installs system packages (may prompt for `sudo`), creates a Python virtual environment, installs Python dependencies, creates `.env` if missing (with a random `SECRET_KEY`), creates the `backups/` folder, and initializes database tables.

If `.env` already exists, it is left unchanged. Copy from `.env.example` if you need a template.

### 4. Start the server

Development (auto-reload, single process):

```bash
bash run.sh
```

Production-style (example on port 8000):

```bash
bash run.sh prod 8000
```

Open `http://localhost:5000` or `http://YOUR_SERVER_IP:PORT` on the LAN. Complete the first-run setup wizard to create the administrator account, then sign in and configure shop settings.

---

## Configuration

Variables are read from `.env` in the project root (see `.env.example`).

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session signing; must be random in production |
| `DATABASE_URL` | PostgreSQL connection string |
| `FLASK_ENV` | `development` or `production` |
| `SESSION_HOURS` | Session lifetime (hours) |
| `ANTHROPIC_API_KEY` | Optional; enables AI features |

Example:

```
SECRET_KEY=<random-hex-from-setup>
DATABASE_URL=postgresql://alchemypos:alchemypos@localhost/alchemypos
FLASK_ENV=development
SESSION_HOURS=8
```

---

## AI features (optional)

With an Anthropic API key: natural-language search on POS, optional cart suggestions, and AI summary on reports. Without a key, search and reporting use non-AI behavior.

---

## Importing products (CSV)

Use Inventory: Import CSV. Expected columns:

```
name,barcode,category,price,cost,unit,stock,low_stock_threshold
```

Create the file in Excel, LibreOffice, or any editor; categories are created as needed during import.

---

## User roles

| Permission | Cashier | Inventory Manager | Admin |
|------------|---------|---------------------|-------|
| POS / sales | Yes | Yes | Yes |
| Inventory | No | Yes | Yes |
| Reports | No | No | Yes |
| Users, Settings, Backups, Audit | No | No | Yes |

---

## Payment methods

Configure in Settings. Methods include cash, M-Pesa variants, card, credit, and others; enable or disable per method.

---

## Categories

Managed under Settings. You can add categories and delete them; products on a deleted category are moved to `General`. The `General` category cannot be deleted.

---

## Backups

Backup files are stored under `backups/` when you use the Backups page or optional auto-backup settings. For PostgreSQL, restore using your own `pg_restore` / `psql` workflow from the downloaded archive; treat SQLite restore notes in older docs as legacy.

---

## Security notes

- Passwords are hashed (PBKDF2-SHA256).
- Failed login lockout and security questions for recovery (see auth flow).
- CSRF on HTML forms; JSON APIs require an authenticated session.
- Sensitive actions are logged in the audit log.

---

## Clean reinstall (reset application data)

**Application database (all tables emptied and recreated, defaults re-seeded):**

```bash
cd /path/to/alchemypos2
source venv/bin/activate
python -c "
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), '.env'))
from app import app, db, _seed_defaults
with app.app_context():
    db.drop_all()
    db.create_all()
    _seed_defaults()
    print('Database reset complete.')
"
```

**Full PostgreSQL database drop** (removes the database object; requires superuser). Replace names if yours differ:

```bash
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'alchemypos' AND pid <> pg_backend_pid();"
sudo -u postgres dropdb alchemypos
sudo -u postgres createdb -O alchemypos alchemypos
```

Then run `bash setup.sh` again (or the `db.create_all()` path above) to recreate tables.

**Fresh virtual environment:**

```bash
rm -rf venv
bash setup.sh
```

**Remove local secrets and regenerate `.env`:** delete `.env`, then run `bash setup.sh` (it creates `.env` when missing).

---

## Troubleshooting

- **Cannot connect to PostgreSQL:** `sudo systemctl status postgresql`; verify `DATABASE_URL` and that the user/database exist.
- **psycopg2 build errors:** install `libpq-dev`, then recreate `venv` and reinstall requirements.
- **Stale UI after updates:** hard refresh the browser (e.g. Ctrl+Shift+R).
- **Products not on POS:** zero-stock items may be hidden; add stock or allow negative stock in Settings.

---

## Project layout

```
alchemypos2/
  app.py              Application factory and default seeding
  config.py           Configuration
  requirements.txt    Python dependencies
  setup.sh            Install script
  run.sh              Run dev or production server
  .env.example        Environment template
  models/             SQLAlchemy models
  routes/             Flask blueprints
  static/             CSS and JavaScript
  templates/          Jinja2 HTML
  backups/            Backup output directory
```

---

## License / attribution

Developed by njorogefrancis. Contact: njorogefrancis.dev@gmail.com | WhatsApp: 0115634345
