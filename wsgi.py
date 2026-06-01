"""Production WSGI entrypoint for HORUS.

Served by Gunicorn, e.g.:
    gunicorn --workers 3 --bind 0.0.0.0:8050 --preload wsgi:app

`--preload` runs this module once in the master process, so init_db() executes
a single time before workers fork.
"""

import database as db
from app import app

# Respect X-Forwarded-* headers when running behind Nginx so url_for, the
# scheme, and client IP are correct. Trusts exactly one proxy hop.
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Ensure schema exists before serving. Idempotent (CREATE TABLE IF NOT EXISTS).
db.init_db()

if __name__ == "__main__":
    app.run()
