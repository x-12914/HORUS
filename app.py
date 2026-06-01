"""HORUS :: Historical Operations Record & Unified Storage
=================================================

A historical recording system for military operations. It records every
mission, stores outcomes and reports, documents casualties and operational
challenges, and turns the accumulated record into analytics that support
strategic decision-making, transparency and accountability.

Run:
    python app.py
Then open http://127.0.0.1:5000
"""

import os
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort, session
)
from werkzeug.security import check_password_hash

import database as db

app = Flask(__name__)

# --- Configuration (environment-driven for production) ---------------------
# In production set HORUS_SECRET_KEY to a long random value. The fallback
# below only exists so local development works out of the box.
app.config["SECRET_KEY"] = os.environ.get(
    "HORUS_SECRET_KEY", "dev-insecure-key-change-me"
)
# Session cookie hardening. SECURE is enabled when served over HTTPS (set
# HORUS_HTTPS=1 once you have TLS / proxy in front of it).
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("HORUS_HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)
db.init_app(app)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# Endpoints reachable without a session.
PUBLIC_ENDPOINTS = {"login", "static"}


@app.before_request
def require_login():
    """Global guard: every page requires an authenticated operator."""
    if request.endpoint in PUBLIC_ENDPOINTS:
        return
    if not session.get("user"):
        return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    # If already signed in, go straight to the deck.
    if session.get("user"):
        return redirect(url_for("dashboard"))

    operator_count = db.query("SELECT COUNT(*) AS c FROM users", one=True)["c"]

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        row = db.query(
            "SELECT * FROM users WHERE username = ?", (username,), one=True
        )
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user"] = row["username"]
            session["role"] = row["role"]
            session.permanent = True
            dest = request.args.get("next")
            # Only allow internal redirects.
            if not dest or not dest.startswith("/"):
                dest = url_for("dashboard")
            return redirect(dest)
        flash("Authentication failed — invalid credentials.", "warning")

    return render_template("login.html", operator_count=operator_count)


@app.route("/logout")
def logout():
    session.clear()
    flash("Session terminated.", "success")
    return redirect(url_for("login"))

# ---------------------------------------------------------------------------
# Controlled vocabularies (shared with the forms/templates)
# ---------------------------------------------------------------------------
BRANCHES = ["Army", "Navy", "Air Force", "Joint", "Special Forces"]
CLASSIFICATIONS = ["UNCLASSIFIED", "RESTRICTED", "CONFIDENTIAL", "SECRET", "TOP SECRET"]
STATUSES = ["PLANNED", "ONGOING", "COMPLETED", "ABORTED", "COMPROMISED"]
OUTCOMES = ["PENDING", "SUCCESS", "PARTIAL", "FAILURE"]
CASUALTY_TYPES = ["KIA", "WIA", "MIA", "POW"]
CHALLENGE_CATEGORIES = [
    "Logistics", "Intelligence", "Weather", "Equipment",
    "Communication", "Terrain", "Enemy", "Other",
]
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
REPORT_TYPES = ["AAR", "SITREP", "INTEL", "DEBRIEF"]

VOCAB = dict(
    branches=BRANCHES, classifications=CLASSIFICATIONS, statuses=STATUSES,
    outcomes=OUTCOMES, casualty_types=CASUALTY_TYPES,
    challenge_categories=CHALLENGE_CATEGORIES, severities=SEVERITIES,
    report_types=REPORT_TYPES,
)


@app.context_processor
def inject_globals():
    """Make vocab, current time and the signed-in operator available."""
    return dict(
        vocab=VOCAB,
        now=datetime.now(),
        current_user=session.get("user"),
        current_role=session.get("role"),
    )


def _form(name, default=""):
    """Trimmed form value helper."""
    return (request.form.get(name) or default).strip()


# ===========================================================================
# Dashboard
# ===========================================================================
@app.route("/")
def dashboard():
    totals = db.query(
        """
        SELECT
            (SELECT COUNT(*) FROM missions)                              AS missions,
            (SELECT COUNT(*) FROM missions WHERE status='ONGOING')       AS ongoing,
            (SELECT COUNT(*) FROM missions WHERE outcome='SUCCESS')      AS successes,
            (SELECT COUNT(*) FROM casualties)                           AS casualties,
            (SELECT COUNT(*) FROM casualties WHERE casualty_type='KIA') AS kia,
            (SELECT COUNT(*) FROM challenges WHERE severity='CRITICAL') AS critical_challenges,
            (SELECT COUNT(*) FROM reports)                              AS reports
        """,
        one=True,
    )

    completed = db.query(
        "SELECT COUNT(*) AS c FROM missions WHERE status='COMPLETED'", one=True
    )["c"]
    success_rate = round(100 * totals["successes"] / completed) if completed else 0

    recent = db.query(
        "SELECT * FROM missions ORDER BY datetime(created_at) DESC, id DESC LIMIT 6"
    )
    by_branch = db.query(
        "SELECT branch, COUNT(*) AS c FROM missions GROUP BY branch ORDER BY c DESC"
    )
    return render_template(
        "dashboard.html", totals=totals, success_rate=success_rate,
        recent=recent, by_branch=by_branch,
    )


# ===========================================================================
# Missions
# ===========================================================================
@app.route("/missions")
def missions():
    status = request.args.get("status", "")
    branch = request.args.get("branch", "")
    search = request.args.get("q", "").strip()

    sql = "SELECT * FROM missions WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if branch:
        sql += " AND branch = ?"
        params.append(branch)
    if search:
        sql += " AND (codename LIKE ? OR operation_name LIKE ? OR location LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    sql += " ORDER BY datetime(start_date) DESC, id DESC"

    rows = db.query(sql, params)
    return render_template(
        "missions.html", missions=rows,
        f_status=status, f_branch=branch, f_search=search,
    )


@app.route("/missions/new", methods=["GET", "POST"])
def mission_new():
    if request.method == "POST":
        mid = db.execute(
            """INSERT INTO missions
               (codename, operation_name, branch, classification, commander,
                location, objective, start_date, end_date, status, outcome, summary)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _form("codename"), _form("operation_name"), _form("branch", "Army"),
                _form("classification", "RESTRICTED"), _form("commander"),
                _form("location"), _form("objective"),
                _form("start_date") or None, _form("end_date") or None,
                _form("status", "PLANNED"), _form("outcome", "PENDING"),
                _form("summary"),
            ),
        )
        flash(f"Mission record created — ID #{mid:04d}.", "success")
        return redirect(url_for("mission_detail", mission_id=mid))
    return render_template("mission_form.html", mission=None, action="new")


@app.route("/missions/<int:mission_id>")
def mission_detail(mission_id):
    mission = db.query("SELECT * FROM missions WHERE id = ?", (mission_id,), one=True)
    if not mission:
        abort(404)
    casualties = db.query(
        "SELECT * FROM casualties WHERE mission_id = ? ORDER BY date", (mission_id,)
    )
    challenges = db.query(
        "SELECT * FROM challenges WHERE mission_id = ? ORDER BY severity DESC, id",
        (mission_id,),
    )
    reports = db.query(
        "SELECT * FROM reports WHERE mission_id = ? ORDER BY datetime(created_at) DESC",
        (mission_id,),
    )
    return render_template(
        "mission_detail.html", mission=mission, casualties=casualties,
        challenges=challenges, reports=reports,
    )


@app.route("/missions/<int:mission_id>/edit", methods=["GET", "POST"])
def mission_edit(mission_id):
    mission = db.query("SELECT * FROM missions WHERE id = ?", (mission_id,), one=True)
    if not mission:
        abort(404)
    if request.method == "POST":
        db.execute(
            """UPDATE missions SET
               codename=?, operation_name=?, branch=?, classification=?, commander=?,
               location=?, objective=?, start_date=?, end_date=?, status=?,
               outcome=?, summary=? WHERE id=?""",
            (
                _form("codename"), _form("operation_name"), _form("branch", "Army"),
                _form("classification", "RESTRICTED"), _form("commander"),
                _form("location"), _form("objective"),
                _form("start_date") or None, _form("end_date") or None,
                _form("status", "PLANNED"), _form("outcome", "PENDING"),
                _form("summary"), mission_id,
            ),
        )
        flash("Mission record updated.", "success")
        return redirect(url_for("mission_detail", mission_id=mission_id))
    return render_template("mission_form.html", mission=mission, action="edit")


@app.route("/missions/<int:mission_id>/delete", methods=["POST"])
def mission_delete(mission_id):
    db.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
    flash(f"Mission #{mission_id:04d} and all linked records purged.", "warning")
    return redirect(url_for("missions"))


# ===========================================================================
# Casualties (logged against a mission)
# ===========================================================================
@app.route("/missions/<int:mission_id>/casualties", methods=["POST"])
def casualty_add(mission_id):
    if not db.query("SELECT id FROM missions WHERE id=?", (mission_id,), one=True):
        abort(404)
    db.execute(
        """INSERT INTO casualties
           (mission_id, service_number, name, rank, unit, casualty_type, date, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            mission_id, _form("service_number"), _form("name"), _form("rank"),
            _form("unit"), _form("casualty_type", "WIA"),
            _form("date") or None, _form("notes"),
        ),
    )
    flash("Casualty recorded.", "success")
    return redirect(url_for("mission_detail", mission_id=mission_id) + "#casualties")


@app.route("/casualties/<int:cid>/delete", methods=["POST"])
def casualty_delete(cid):
    row = db.query("SELECT mission_id FROM casualties WHERE id=?", (cid,), one=True)
    if not row:
        abort(404)
    db.execute("DELETE FROM casualties WHERE id=?", (cid,))
    flash("Casualty record removed.", "warning")
    return redirect(url_for("mission_detail", mission_id=row["mission_id"]) + "#casualties")


# ===========================================================================
# Operational challenges
# ===========================================================================
@app.route("/missions/<int:mission_id>/challenges", methods=["POST"])
def challenge_add(mission_id):
    if not db.query("SELECT id FROM missions WHERE id=?", (mission_id,), one=True):
        abort(404)
    db.execute(
        """INSERT INTO challenges (mission_id, category, severity, description, resolution)
           VALUES (?,?,?,?,?)""",
        (
            mission_id, _form("category", "Other"), _form("severity", "MEDIUM"),
            _form("description"), _form("resolution"),
        ),
    )
    flash("Operational challenge logged.", "success")
    return redirect(url_for("mission_detail", mission_id=mission_id) + "#challenges")


@app.route("/challenges/<int:cid>/delete", methods=["POST"])
def challenge_delete(cid):
    row = db.query("SELECT mission_id FROM challenges WHERE id=?", (cid,), one=True)
    if not row:
        abort(404)
    db.execute("DELETE FROM challenges WHERE id=?", (cid,))
    flash("Challenge record removed.", "warning")
    return redirect(url_for("mission_detail", mission_id=row["mission_id"]) + "#challenges")


# ===========================================================================
# Reports
# ===========================================================================
@app.route("/reports")
def reports():
    rtype = request.args.get("type", "")
    sql = (
        "SELECT r.*, m.codename, m.operation_name "
        "FROM reports r JOIN missions m ON m.id = r.mission_id WHERE 1=1"
    )
    params = []
    if rtype:
        sql += " AND r.report_type = ?"
        params.append(rtype)
    sql += " ORDER BY datetime(r.created_at) DESC"
    rows = db.query(sql, params)
    return render_template("reports.html", reports=rows, f_type=rtype)


@app.route("/missions/<int:mission_id>/reports", methods=["POST"])
def report_add(mission_id):
    if not db.query("SELECT id FROM missions WHERE id=?", (mission_id,), one=True):
        abort(404)
    db.execute(
        """INSERT INTO reports (mission_id, title, report_type, author, content)
           VALUES (?,?,?,?,?)""",
        (
            mission_id, _form("title"), _form("report_type", "AAR"),
            _form("author"), _form("content"),
        ),
    )
    flash("Report filed.", "success")
    return redirect(url_for("mission_detail", mission_id=mission_id) + "#reports")


@app.route("/reports/<int:rid>/delete", methods=["POST"])
def report_delete(rid):
    row = db.query("SELECT mission_id FROM reports WHERE id=?", (rid,), one=True)
    if not row:
        abort(404)
    db.execute("DELETE FROM reports WHERE id=?", (rid,))
    flash("Report removed.", "warning")
    return redirect(url_for("mission_detail", mission_id=row["mission_id"]) + "#reports")


# ===========================================================================
# Casualties register (cross-mission view)
# ===========================================================================
@app.route("/casualties")
def casualties_register():
    ctype = request.args.get("type", "")
    sql = (
        "SELECT c.*, m.codename, m.operation_name "
        "FROM casualties c JOIN missions m ON m.id = c.mission_id WHERE 1=1"
    )
    params = []
    if ctype:
        sql += " AND c.casualty_type = ?"
        params.append(ctype)
    sql += " ORDER BY date DESC, c.id DESC"
    rows = db.query(sql, params)
    return render_template("casualties.html", casualties=rows, f_type=ctype)


# ===========================================================================
# Analytics — the strategic decision-making layer
# ===========================================================================
@app.route("/analytics")
def analytics():
    by_branch = db.query(
        "SELECT branch, COUNT(*) c FROM missions GROUP BY branch ORDER BY c DESC"
    )
    by_outcome = db.query(
        "SELECT outcome, COUNT(*) c FROM missions GROUP BY outcome ORDER BY c DESC"
    )
    by_status = db.query(
        "SELECT status, COUNT(*) c FROM missions GROUP BY status ORDER BY c DESC"
    )
    casualties_by_type = db.query(
        "SELECT casualty_type, COUNT(*) c FROM casualties GROUP BY casualty_type ORDER BY c DESC"
    )
    challenges_by_cat = db.query(
        "SELECT category, COUNT(*) c FROM challenges GROUP BY category ORDER BY c DESC"
    )
    # Missions + casualties per year, the historical trend line.
    by_year = db.query(
        """
        SELECT y AS year,
               (SELECT COUNT(*) FROM missions   WHERE substr(start_date,1,4)=y) AS missions,
               (SELECT COUNT(*) FROM casualties WHERE substr(date,1,4)=y)       AS casualties
        FROM (SELECT DISTINCT substr(start_date,1,4) AS y FROM missions
              WHERE start_date IS NOT NULL AND start_date != '')
        ORDER BY y
        """
    )
    # Branches ranked by casualties — informs force-protection planning.
    casualties_by_branch = db.query(
        """SELECT m.branch, COUNT(c.id) c
           FROM casualties c JOIN missions m ON m.id=c.mission_id
           GROUP BY m.branch ORDER BY c DESC"""
    )

    def as_pairs(rows, key):
        return [(r[key], r["c"]) for r in rows]

    return render_template(
        "analytics.html",
        by_branch=as_pairs(by_branch, "branch"),
        by_outcome=as_pairs(by_outcome, "outcome"),
        by_status=as_pairs(by_status, "status"),
        casualties_by_type=as_pairs(casualties_by_type, "casualty_type"),
        challenges_by_cat=as_pairs(challenges_by_cat, "category"),
        casualties_by_branch=as_pairs(casualties_by_branch, "branch"),
        by_year=by_year,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


def _ensure_dev_admin():
    """For LOCAL development only: guarantee a login exists (admin/admin)."""
    from werkzeug.security import generate_password_hash
    if db.query("SELECT COUNT(*) AS c FROM users", one=True)["c"] == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("admin", generate_password_hash("admin"), "admin"),
        )
        print("  [dev] Created default operator  admin / admin  — change this!")


if __name__ == "__main__":
    # ---- LOCAL DEVELOPMENT SERVER ----
    # Production runs via Gunicorn against wsgi.py and manage.py — NOT this.
    db.init_db()
    import seed
    seed.seed_if_empty(DB_PATH=db.DB_PATH)
    with app.app_context():
        _ensure_dev_admin()

    host = os.environ.get("HORUS_HOST", "127.0.0.1")
    port = int(os.environ.get("HORUS_PORT", "5000"))
    debug = os.environ.get("HORUS_DEBUG", "1") == "1"
    print(f"\n  HORUS online  ->  http://{host}:{port}\n")
    app.run(debug=debug, host=host, port=port)
