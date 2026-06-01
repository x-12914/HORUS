"""HORUS management CLI.

Operational tasks that run outside the web server — initialise the database,
seed demo data, and manage operator accounts. Uses sqlite3 directly so it does
not require a Flask application context.

Examples:
    python manage.py init-db
    python manage.py create-user admin --role admin
    python manage.py create-user jdoe --password "S3cret!"     # non-interactive
    python manage.py set-password admin
    python manage.py list-users
    python manage.py seed
"""

import argparse
import getpass
import sqlite3
import sys

from werkzeug.security import generate_password_hash

import database as db


def _connect():
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _prompt_password():
    while True:
        p1 = getpass.getpass("New passphrase: ")
        if len(p1) < 6:
            print("  Passphrase must be at least 6 characters.")
            continue
        p2 = getpass.getpass("Confirm passphrase: ")
        if p1 != p2:
            print("  Passphrases do not match — try again.")
            continue
        return p1


# --- commands --------------------------------------------------------------
def cmd_init_db(args):
    db.init_db()
    print(f"  Schema applied -> {db.DB_PATH}")


def cmd_seed(args):
    db.init_db()
    import seed
    seed.seed_if_empty(DB_PATH=db.DB_PATH)
    print("  Seed complete (skipped if data already present).")


def cmd_create_user(args):
    db.init_db()
    password = args.password or _prompt_password()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            (args.username, generate_password_hash(password), args.role),
        )
        conn.commit()
        print(f"  Operator '{args.username}' created with role '{args.role}'.")
    except sqlite3.IntegrityError:
        print(f"  ERROR: operator '{args.username}' already exists.")
        sys.exit(1)
    finally:
        conn.close()


def cmd_set_password(args):
    password = args.password or _prompt_password()
    conn = _connect()
    cur = conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (generate_password_hash(password), args.username),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        print(f"  ERROR: no operator named '{args.username}'.")
        sys.exit(1)
    print(f"  Passphrase updated for '{args.username}'.")


def cmd_delete_user(args):
    conn = _connect()
    cur = conn.execute("DELETE FROM users WHERE username = ?", (args.username,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        print(f"  ERROR: no operator named '{args.username}'.")
        sys.exit(1)
    print(f"  Operator '{args.username}' removed.")


def cmd_list_users(args):
    db.init_db()
    conn = _connect()
    rows = conn.execute(
        "SELECT username, role, created_at FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    if not rows:
        print("  No operators provisioned. Create one with: create-user <name>")
        return
    print(f"  {'USERNAME':<20} {'ROLE':<10} CREATED")
    for r in rows:
        print(f"  {r['username']:<20} {r['role']:<10} {r['created_at']}")


def main():
    parser = argparse.ArgumentParser(prog="manage.py", description="HORUS admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create database tables").set_defaults(func=cmd_init_db)
    sub.add_parser("seed", help="load fictional demo data").set_defaults(func=cmd_seed)
    sub.add_parser("list-users", help="list operator accounts").set_defaults(func=cmd_list_users)

    p = sub.add_parser("create-user", help="create an operator account")
    p.add_argument("username")
    p.add_argument("--password", help="set non-interactively (otherwise prompted)")
    p.add_argument("--role", default="operator", choices=["operator", "admin"])
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("set-password", help="reset an operator passphrase")
    p.add_argument("username")
    p.add_argument("--password", help="set non-interactively (otherwise prompted)")
    p.set_defaults(func=cmd_set_password)

    p = sub.add_parser("delete-user", help="remove an operator account")
    p.add_argument("username")
    p.set_defaults(func=cmd_delete_user)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
