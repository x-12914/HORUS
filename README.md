# HORUS — Historical Operations Record & Unified Storage

A historical recording system for military operations. It records every
mission, stores outcomes and reports, documents casualties and operational
challenges, and turns the accumulated record into analytics that support
**better future planning, transparency and accountability**.

> Demo data is entirely fictional and for demonstration only.

## Features

- **Command Deck** — at-a-glance KPIs: total missions, success rate, casualties, critical challenges.
- **Mission Registry** — record, search, filter, edit and purge operations. Tracks codename, branch, classification, commander, theatre, timeline, status and outcome.
- **Mission Dossier** — a full per-mission file with linked **casualties**, **operational challenges** and **reports** (AAR / SITREP / INTEL / DEBRIEF), each added inline.
- **Casualty Register** — cross-mission roll-up of KIA / WIA / MIA / POW.
- **Drone Feed** — assign multiple drones to each mission (callsign, model, status, live URL); a per-mission feed grid plus an aggregate **video wall** of every feed across all missions. Shows an OFFLINE placeholder until a live stream URL is connected.
- **Report Archive** — every filed report in one searchable place.
- **Strategic Analytics** — missions by branch/outcome/status, casualties by type/branch, challenges by category, and a year-over-year historical trend line.

## Tech

- **Python 3 + Flask** web app
- **SQLite** database (`horus.db`, created automatically) — the persistent historical database
- Server-rendered Jinja2 templates, tactical command-center dark theme, no build step

## Authentication

Every page requires an authenticated operator. Accounts are managed from the
CLI (`manage.py`) — there is no public sign-up.

- **Local dev:** a default operator `admin` / `admin` is created automatically on
  first `python app.py` (change it immediately).
- **Production:** create real operators with `manage.py create-user` (see below).

## Run it locally (Windows / dev)

```powershell
# from this folder
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000> and sign in as `admin` / `admin`.

On first launch the app creates `horus.db`, applies `schema.sql`, and
seeds a fictional dataset so the dashboards are populated. Delete
`horus.db` to start empty. Host/port/debug can be overridden with the
`HORUS_HOST`, `HORUS_PORT`, `HORUS_DEBUG` env vars.

---

## Deploy to the VPS (Linux + Nginx, run on a port)

Served by **Gunicorn**, managed by **systemd**, bound to a free port that won't
clash with your existing services (default `8050`). It does **not** require
Nginx to start — Nginx is optional (see `deploy/nginx-horus.conf`) for when
you want a clean URL/TLS later.

> Paths below use `/opt/horus` as a placeholder — change it to wherever your
> services live on the VPS.

```bash
# 1. Clone and create an isolated virtualenv
sudo mkdir -p /opt/horus && sudo chown $USER /opt/horus
git clone https://github.com/<you>/<repo>.git /opt/horus
cd /opt/horus
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 2. Generate a secret key and export the config
export HORUS_SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
export HORUS_DB=/opt/horus/horus.db

# 3. Initialise the database and create your first operator
./venv/bin/python manage.py init-db
./venv/bin/python manage.py create-user admin --role admin
./venv/bin/python manage.py seed         # optional: load demo data

# 4. Quick smoke test on the chosen port (check it's free: sudo ss -ltnp | grep 8050)
./venv/bin/gunicorn --bind 0.0.0.0:8050 --preload wsgi:app
#    visit http://YOUR_VPS_IP:8050  then Ctrl-C

# 5. Install as a service (edit the file first: User, paths, SECRET_KEY, port)
sudo cp deploy/horus.service /etc/systemd/system/horus.service
sudo systemctl daemon-reload
sudo systemctl enable --now horus
sudo systemctl status horus        # journalctl -u horus -f
```

**Open the port in the firewall** (only if exposing it directly):

```bash
sudo ufw allow 8050/tcp     # ufw
# or: firewall-cmd --add-port=8050/tcp --permanent && firewall-cmd --reload
```

> ⚠️ Exposing a raw port means **no HTTPS** — credentials travel in clear text.
> For anything beyond an internal trial, put it behind your existing Nginx and
> run certbot (`deploy/nginx-horus.conf` has the server block ready), then
> set `HORUS_HTTPS=1` so session cookies are marked Secure.

### Operator management (`manage.py`)

```bash
python manage.py create-user <name> [--role admin] [--password ...]
python manage.py set-password <name>
python manage.py delete-user <name>
python manage.py list-users
```

Omit `--password` to be prompted securely (recommended).

### Upgrades

```bash
cd /opt/horus && git pull
sudo systemctl restart horus
# run ./venv/bin/python manage.py init-db again if the schema changed (idempotent)
```

## Project layout

```
app.py          Flask routes + authentication
wsgi.py         Gunicorn entrypoint (ProxyFix, DB init)
manage.py       Admin CLI (init-db, seed, user management)
database.py     SQLite access layer (env-configurable path, WAL)
schema.sql      Database schema (users, missions, casualties, challenges, reports)
seed.py         Fictional demo data
templates/      Jinja2 pages (login, dashboard, missions, dossier, analytics, ...)
static/css/     Tactical dark theme
static/js/      Live clock + clickable rows
deploy/         systemd unit + optional Nginx server block
.env.example    Environment variable reference
```

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `HORUS_SECRET_KEY` | Flask session signing key — **set in production** | insecure dev key |
| `HORUS_DB` | Absolute path to the SQLite file | `./horus.db` |
| `HORUS_HTTPS` | `1` marks session cookies Secure (use with TLS) | `0` |
| `HORUS_HOST` / `HORUS_PORT` | Dev server bind (ignored under Gunicorn) | `127.0.0.1` / `5000` |
| `HORUS_DEBUG` | `1` enables the dev reloader/debugger | `1` (dev only) |
