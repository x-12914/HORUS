"""Database access layer for HORUS.

Thin wrapper around sqlite3 that gives every request its own connection,
returns rows as dict-like objects, and exposes a couple of helpers for
initialising the schema.
"""

import os
import sqlite3
from flask import g

# Database file lives next to this module by default, but the path can be
# overridden in production via the HORUS_DB environment variable.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("HORUS_DB") or os.path.join(BASE_DIR, "horus.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_db():
    """Return a per-request SQLite connection (created lazily)."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    """Close the request-scoped connection if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    """Run a SELECT and return rows (or a single row when one=True)."""
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE and return the last row id."""
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def init_db():
    """Create tables from schema.sql. Safe to call repeatedly."""
    conn = sqlite3.connect(DB_PATH)
    # WAL allows concurrent readers while one writer is active — important
    # once multiple Gunicorn workers are hitting the same SQLite file.
    conn.execute("PRAGMA journal_mode = WAL")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def init_app(app):
    """Register teardown so connections are always closed."""
    app.teardown_appcontext(close_db)
