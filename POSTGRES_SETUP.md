# PostgreSQL setup (Kali Linux and similar)

Short reference for installing PostgreSQL and creating the `alchemypos` database used by AlchemyPOS 2. See `README.md` for full application setup.

---

## Step 1 — Install

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
```

---

## Step 2 — Start the service

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

Verify it's running:

```bash
sudo systemctl status postgresql
```

Look for: **active (running)**

---

## Step 3 — Create database and user

```bash
sudo -u postgres psql
```

You will see `postgres=#` — now run these:

```sql
CREATE USER alchemypos WITH PASSWORD 'alchemypos';
CREATE DATABASE alchemypos OWNER alchemypos;
GRANT ALL PRIVILEGES ON DATABASE alchemypos TO alchemypos;
\q
```

---

## Step 4 — Test the connection

```bash
psql -U alchemypos -d alchemypos -h localhost
```

Password: **alchemypos**

If you see `alchemypos=>` — you're in. Type `\q` to exit.

---

## Step 5 — Run AlchemyPOS setup

```bash
cd ~/Desktop/alchemypos2
bash setup.sh
bash run.sh prod 8000
```

Open: **http://localhost:8000**

Share with staff on same network: **http://YOUR_IP:8000**

Find your IP:
```bash
ip a | grep "inet " | grep -v 127
```

---

## Common errors

---

### Error: Connection refused

```bash
sudo systemctl restart postgresql
```

---

### Error: peer authentication failed

```bash
sudo nano /etc/postgresql/*/main/pg_hba.conf
```

Find this line:
```
local   all   all   peer
```

Change `peer` to `md5` — save with `Ctrl+O`, exit with `Ctrl+X`

Then restart:
```bash
sudo systemctl restart postgresql
```

---

### Error: password authentication failed

Reset the password:
```bash
sudo -u postgres psql -c "ALTER USER alchemypos WITH PASSWORD 'alchemypos';"
```

---

### Check PostgreSQL is listening on port 5432

```bash
sudo ss -tlnp | grep 5432
```

---

## QUICK REFERENCE

| What | Command |
|---|---|
| Start database | `sudo systemctl start postgresql` |
| Stop database | `sudo systemctl stop postgresql` |
| Restart database | `sudo systemctl restart postgresql` |
| Check status | `sudo systemctl status postgresql` |
| Open admin shell | `sudo -u postgres psql` |
| List all databases | `\l` (inside psql) |
| List all users | `\du` (inside psql) |
| Exit psql | `\q` |
