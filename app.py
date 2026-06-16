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
import secrets
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
# Endpoints reachable without a session. These are machine endpoints (BLE
# gateway, phone apps) guarded by their own tokens instead of a login.
PUBLIC_ENDPOINTS = {
    "login", "static", "track_ingest",
    "api_alert_register", "api_alert_poll", "api_alert_ack",
}


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
FEED_STATUSES = ["ONLINE", "OFFLINE", "STANDBY", "LOST"]
ASSET_CATEGORIES = [
    "Weapon", "Ammunition", "Comms", "Medical", "Optics",
    "Power", "Vehicle Part", "General",
]
TRACKING_STATUSES = ["AWAITING HARDWARE", "LIVE", "LOST", "DISABLED"]
PRESENCE_STATES = ["UNKNOWN", "IN FACILITY", "LEFT FACILITY"]
ALERT_SEVERITIES = ["INFO", "WARNING", "AIR ALERT", "ALL CLEAR"]

# An asset that hasn't reported within this many seconds is shown OFFLINE.
# The gateway re-affirms presence every ~30s, so ~90s = ~3 missed cycles.
STALE_AFTER_SECONDS = 90

VOCAB = dict(
    branches=BRANCHES, classifications=CLASSIFICATIONS, statuses=STATUSES,
    outcomes=OUTCOMES, casualty_types=CASUALTY_TYPES,
    challenge_categories=CHALLENGE_CATEGORIES, severities=SEVERITIES,
    report_types=REPORT_TYPES, feed_statuses=FEED_STATUSES,
    asset_categories=ASSET_CATEGORIES, tracking_statuses=TRACKING_STATUSES,
    presence_states=PRESENCE_STATES, alert_severities=ALERT_SEVERITIES,
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
    feeds = db.query(
        "SELECT * FROM drone_feeds WHERE mission_id = ? ORDER BY callsign, id",
        (mission_id,),
    )
    return render_template(
        "mission_detail.html", mission=mission, casualties=casualties,
        challenges=challenges, reports=reports, feeds=feeds,
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
# Drone feeds (many per mission)
# ===========================================================================
@app.route("/missions/<int:mission_id>/feeds", methods=["POST"])
def feed_add(mission_id):
    if not db.query("SELECT id FROM missions WHERE id=?", (mission_id,), one=True):
        abort(404)
    url = _form("feed_url") or None
    # Default status: ONLINE if a URL is supplied, otherwise OFFLINE.
    status = _form("status") or ("ONLINE" if url else "OFFLINE")
    db.execute(
        """INSERT INTO drone_feeds (mission_id, callsign, model, feed_url, status, notes)
           VALUES (?,?,?,?,?,?)""",
        (mission_id, _form("callsign", "UAV"), _form("model"), url, status, _form("notes")),
    )
    flash("Drone feed assigned.", "success")
    return redirect(url_for("mission_detail", mission_id=mission_id) + "#dronefeed")


@app.route("/feeds/<int:fid>/edit", methods=["POST"])
def feed_edit(fid):
    row = db.query("SELECT mission_id FROM drone_feeds WHERE id=?", (fid,), one=True)
    if not row:
        abort(404)
    db.execute(
        """UPDATE drone_feeds SET callsign=?, model=?, feed_url=?, status=?, notes=?
           WHERE id=?""",
        (
            _form("callsign", "UAV"), _form("model"), _form("feed_url") or None,
            _form("status", "OFFLINE"), _form("notes"), fid,
        ),
    )
    flash("Drone feed updated.", "success")
    return redirect(url_for("mission_detail", mission_id=row["mission_id"]) + "#dronefeed")


@app.route("/feeds/<int:fid>/delete", methods=["POST"])
def feed_delete(fid):
    row = db.query("SELECT mission_id FROM drone_feeds WHERE id=?", (fid,), one=True)
    if not row:
        abort(404)
    db.execute("DELETE FROM drone_feeds WHERE id=?", (fid,))
    flash("Drone feed removed.", "warning")
    return redirect(url_for("mission_detail", mission_id=row["mission_id"]) + "#dronefeed")


@app.route("/feeds")
def feeds_wall():
    """Aggregate video wall — every drone feed across every mission."""
    status = request.args.get("status", "")
    sql = (
        "SELECT d.*, m.codename, m.operation_name, m.status AS mission_status "
        "FROM drone_feeds d JOIN missions m ON m.id = d.mission_id WHERE 1=1"
    )
    params = []
    if status:
        sql += " AND d.status = ?"
        params.append(status)
    sql += " ORDER BY (d.feed_url IS NULL), m.codename, d.callsign"
    feeds = db.query(sql, params)

    counts = db.query(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN status='ONLINE'  THEN 1 ELSE 0 END) AS online,
             SUM(CASE WHEN status='OFFLINE' THEN 1 ELSE 0 END) AS offline,
             SUM(CASE WHEN feed_url IS NOT NULL AND feed_url!='' THEN 1 ELSE 0 END) AS with_url
           FROM drone_feeds""",
        one=True,
    )
    return render_template("feeds.html", feeds=feeds, counts=counts, f_status=status)


# ===========================================================================
# Device tracking — BLE asset location within the facility
# ===========================================================================
def _rooms():
    return db.query("SELECT * FROM rooms ORDER BY name")


# Asset SELECT that also computes seconds since last report (age_secs).
ASSET_SELECT = (
    "SELECT a.*, r.name AS room_name, "
    "CAST(strftime('%s','now') - strftime('%s', a.last_seen) AS INTEGER) AS age_secs "
    "FROM assets a LEFT JOIN rooms r ON r.id = a.current_room_id"
)


def _annotate_assets(rows):
    """Convert asset rows to dicts and add an `online` flag based on age_secs.

    An asset is online only if it has reported recently; once it stops (gateway
    powered off, out of range), age_secs grows past the threshold and it is
    treated as OFFLINE even though its stored tracking_status is still LIVE.
    """
    out = []
    for r in rows:
        d = dict(r)
        age = d.get("age_secs")
        d["online"] = (
            d.get("last_seen") is not None
            and age is not None
            and age <= STALE_AFTER_SECONDS
        )
        out.append(d)
    return out


@app.route("/tracking")
def tracking_dashboard():
    counts = db.query(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN presence='IN FACILITY'   THEN 1 ELSE 0 END) AS in_facility,
             SUM(CASE WHEN presence='LEFT FACILITY' THEN 1 ELSE 0 END) AS left_facility,
             SUM(CASE WHEN last_seen IS NULL        THEN 1 ELSE 0 END) AS untracked
           FROM assets""",
        one=True,
    )
    # Has any asset ever reported a position? Drives the "awaiting hardware" banner.
    live = db.query(
        "SELECT COUNT(*) AS c FROM assets WHERE last_seen IS NOT NULL", one=True
    )["c"]

    rooms = _rooms()
    assets = _annotate_assets(db.query(ASSET_SELECT + " ORDER BY a.asset_tag"))
    # Assets that reported before but have since gone quiet (gateway down, etc.).
    offline = sum(1 for a in assets if a["last_seen"] and not a["online"])

    # Bucket assets by room id; None bucket holds unlocated assets.
    by_room = {}
    for a in assets:
        by_room.setdefault(a["current_room_id"], []).append(a)
    unlocated = [a for a in assets if a["presence"] != "LEFT FACILITY"
                 and a["current_room_id"] is None]
    departed = [a for a in assets if a["presence"] == "LEFT FACILITY"]

    return render_template(
        "tracking.html", counts=counts, live=live, rooms=rooms,
        by_room=by_room, unlocated=unlocated, departed=departed, offline=offline,
    )


@app.route("/tracking/assets")
def assets_list():
    room = request.args.get("room", "")
    category = request.args.get("category", "")
    presence = request.args.get("presence", "")
    search = request.args.get("q", "").strip()

    sql = ASSET_SELECT + " WHERE 1=1"
    params = []
    if room:
        sql += " AND a.current_room_id = ?"
        params.append(room)
    if category:
        sql += " AND a.category = ?"
        params.append(category)
    if presence:
        sql += " AND a.presence = ?"
        params.append(presence)
    if search:
        sql += " AND (a.asset_tag LIKE ? OR a.name LIKE ? OR a.device_id LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    sql += " ORDER BY a.asset_tag"

    assets = _annotate_assets(db.query(sql, params))
    return render_template(
        "assets.html", assets=assets, rooms=_rooms(),
        f_room=room, f_category=category, f_presence=presence, f_search=search,
    )


@app.route("/tracking/assets/new", methods=["GET", "POST"])
def asset_new():
    if request.method == "POST":
        try:
            aid = db.execute(
                """INSERT INTO assets
                   (asset_tag, name, category, serial, device_id, tracking_status, notes)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    _form("asset_tag"), _form("name"), _form("category", "General"),
                    _form("serial"), _form("device_id") or None,
                    _form("tracking_status", "AWAITING HARDWARE"), _form("notes"),
                ),
            )
        except db.sqlite3.IntegrityError:
            flash("Asset tag already exists — tags must be unique.", "warning")
            return render_template("asset_form.html", asset=None, rooms=_rooms(), action="new")
        flash(f"Asset {_form('asset_tag')} registered.", "success")
        return redirect(url_for("assets_list"))
    return render_template("asset_form.html", asset=None, rooms=_rooms(), action="new")


@app.route("/tracking/assets/<int:asset_id>/edit", methods=["GET", "POST"])
def asset_edit(asset_id):
    asset = db.query("SELECT * FROM assets WHERE id=?", (asset_id,), one=True)
    if not asset:
        abort(404)
    if request.method == "POST":
        room_id = _form("current_room_id") or None
        presence = _form("presence", "UNKNOWN")
        # Stamp last_seen when a manual location is set (normally hardware-driven).
        located = bool(room_id) or presence != "UNKNOWN"
        last_seen_sql = "datetime('now')" if located else "NULL"
        try:
            db.execute(
                f"""UPDATE assets SET
                    asset_tag=?, name=?, category=?, serial=?, device_id=?,
                    tracking_status=?, current_room_id=?, presence=?,
                    last_seen={last_seen_sql}, notes=? WHERE id=?""",
                (
                    _form("asset_tag"), _form("name"), _form("category", "General"),
                    _form("serial"), _form("device_id") or None,
                    _form("tracking_status", "AWAITING HARDWARE"),
                    room_id, presence, _form("notes"), asset_id,
                ),
            )
        except db.sqlite3.IntegrityError:
            flash("Asset tag already exists — tags must be unique.", "warning")
            return render_template("asset_form.html", asset=asset, rooms=_rooms(), action="edit")
        flash("Asset updated.", "success")
        return redirect(url_for("assets_list"))
    return render_template("asset_form.html", asset=asset, rooms=_rooms(), action="edit")


@app.route("/tracking/assets/<int:asset_id>/delete", methods=["POST"])
def asset_delete(asset_id):
    db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
    flash("Asset removed from register.", "warning")
    return redirect(url_for("assets_list"))


@app.route("/tracking/rooms", methods=["GET", "POST"])
def rooms_list():
    if request.method == "POST":
        db.execute(
            "INSERT INTO rooms (name, code, zone, description) VALUES (?,?,?,?)",
            (_form("name"), _form("code") or None, _form("zone"), _form("description")),
        )
        flash("Room added.", "success")
        return redirect(url_for("rooms_list"))
    rooms = db.query(
        """SELECT r.*, (SELECT COUNT(*) FROM assets a WHERE a.current_room_id=r.id) AS asset_count
           FROM rooms r ORDER BY r.name"""
    )
    return render_template("rooms.html", rooms=rooms)


@app.route("/tracking/rooms/<int:room_id>/edit", methods=["POST"])
def room_edit(room_id):
    db.execute(
        "UPDATE rooms SET name=?, code=?, zone=?, description=? WHERE id=?",
        (_form("name"), _form("code") or None, _form("zone"), _form("description"), room_id),
    )
    flash("Room updated.", "success")
    return redirect(url_for("rooms_list"))


@app.route("/tracking/rooms/<int:room_id>/delete", methods=["POST"])
def room_delete(room_id):
    # ON DELETE SET NULL clears current_room_id on any assets that were here.
    db.execute("DELETE FROM rooms WHERE id=?", (room_id,))
    flash("Room removed; affected assets reset to UNKNOWN location.", "warning")
    return redirect(url_for("rooms_list"))


# --- BLE gateway ingestion endpoint ---------------------------------------
# The future BLE hardware/gateway POSTs here to update an asset's location.
# Login-exempt (a gateway can't sign in) but guarded by a shared token set in
# the HORUS_INGEST_TOKEN environment variable. Disabled until that is set.
@app.route("/api/track", methods=["POST"])
def track_ingest():
    token = os.environ.get("HORUS_INGEST_TOKEN")
    if not token:
        return {"error": "ingestion disabled — set HORUS_INGEST_TOKEN"}, 503
    if request.headers.get("X-HORUS-TOKEN") != token:
        return {"error": "unauthorized"}, 401

    data = request.get_json(silent=True) or request.form
    device_id = (data.get("device_id") or "").strip()
    if not device_id:
        return {"error": "device_id required"}, 400

    asset = db.query("SELECT * FROM assets WHERE device_id=?", (device_id,), one=True)
    if not asset:
        return {"error": "unknown device_id"}, 404

    room_ref = (data.get("room") or "").strip()
    presence = (data.get("presence") or "").strip().upper()
    room_id = None
    if room_ref:
        room = db.query(
            "SELECT id FROM rooms WHERE code=? OR name=?", (room_ref, room_ref), one=True
        )
        room_id = room["id"] if room else None
    if presence not in PRESENCE_STATES:
        presence = "IN FACILITY" if room_id else "LEFT FACILITY"

    db.execute(
        "UPDATE assets SET current_room_id=?, presence=?, tracking_status='LIVE', "
        "last_seen=datetime('now') WHERE id=?",
        (room_id, presence, asset["id"]),
    )
    return {
        "ok": True, "asset_tag": asset["asset_tag"],
        "room_id": room_id, "presence": presence,
    }


# ===========================================================================
# Defense Alert — push messages from the dashboard to phones
# ===========================================================================
@app.route("/alerts")
def alerts_console():
    phones = db.query("SELECT * FROM phones ORDER BY label")
    active = [p for p in phones if p["active"]]
    recent = db.query(
        """SELECT a.*,
             (SELECT COUNT(*) FROM alert_deliveries d WHERE d.alert_id=a.id) AS total,
             (SELECT COUNT(*) FROM alert_deliveries d WHERE d.alert_id=a.id AND d.status!='PENDING') AS delivered,
             (SELECT COUNT(*) FROM alert_deliveries d WHERE d.alert_id=a.id AND d.status='ACKNOWLEDGED') AS acked
           FROM alerts a ORDER BY datetime(a.created_at) DESC, a.id DESC LIMIT 25"""
    )
    return render_template(
        "alerts.html", phones=phones, active=active, recent=recent,
    )


@app.route("/alerts/send", methods=["POST"])
def alert_send():
    message = _form("message")
    if not message:
        flash("Alert message is required.", "warning")
        return redirect(url_for("alerts_console"))

    severity = _form("severity", "AIR ALERT")
    target = _form("target", "ALL")
    title = _form("title")

    if target == "SELECTED":
        ids = [i for i in request.form.getlist("phone_ids") if i.isdigit()]
        if not ids:
            flash("Select at least one phone, or choose ALL.", "warning")
            return redirect(url_for("alerts_console"))
        placeholders = ",".join("?" * len(ids))
        phones = db.query(
            f"SELECT id FROM phones WHERE active=1 AND id IN ({placeholders})", ids
        )
    else:
        phones = db.query("SELECT id FROM phones WHERE active=1")

    if not phones:
        flash("No active phones to alert.", "warning")
        return redirect(url_for("alerts_console"))

    alert_id = db.execute(
        "INSERT INTO alerts (title, message, severity, target, created_by) VALUES (?,?,?,?,?)",
        (title, message, severity, target, session.get("user")),
    )
    for p in phones:
        db.execute(
            "INSERT INTO alert_deliveries (alert_id, phone_id) VALUES (?,?)",
            (alert_id, p["id"]),
        )
    flash(f"{severity} dispatched to {len(phones)} phone(s).", "success")
    return redirect(url_for("alert_detail", alert_id=alert_id))


@app.route("/alerts/<int:alert_id>")
def alert_detail(alert_id):
    alert = db.query("SELECT * FROM alerts WHERE id=?", (alert_id,), one=True)
    if not alert:
        abort(404)
    deliveries = db.query(
        """SELECT d.*, p.label, p.platform
           FROM alert_deliveries d JOIN phones p ON p.id=d.phone_id
           WHERE d.alert_id=? ORDER BY p.label""",
        (alert_id,),
    )
    return render_template("alert_detail.html", alert=alert, deliveries=deliveries)


@app.route("/alerts/<int:alert_id>/delete", methods=["POST"])
def alert_delete(alert_id):
    db.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    flash("Alert record deleted.", "warning")
    return redirect(url_for("alerts_console"))


# --- Phones management (dashboard) ----------------------------------------
@app.route("/alerts/phones", methods=["GET", "POST"])
def phones_list():
    if request.method == "POST":
        db.execute(
            "INSERT INTO phones (label, device_token, platform) VALUES (?,?,?)",
            (_form("label", "Unnamed phone"), secrets.token_hex(16), _form("platform")),
        )
        flash("Phone enrolled. Share its device token with the app.", "success")
        return redirect(url_for("phones_list"))
    phones = db.query(
        """SELECT p.*,
             (SELECT COUNT(*) FROM alert_deliveries d WHERE d.phone_id=p.id) AS alerts_received
           FROM phones p ORDER BY p.label"""
    )
    return render_template("phones.html", phones=phones)


@app.route("/alerts/phones/<int:phone_id>/toggle", methods=["POST"])
def phone_toggle(phone_id):
    row = db.query("SELECT active FROM phones WHERE id=?", (phone_id,), one=True)
    if not row:
        abort(404)
    db.execute("UPDATE phones SET active=? WHERE id=?", (0 if row["active"] else 1, phone_id))
    flash("Phone status updated.", "success")
    return redirect(url_for("phones_list"))


@app.route("/alerts/phones/<int:phone_id>/delete", methods=["POST"])
def phone_delete(phone_id):
    db.execute("DELETE FROM phones WHERE id=?", (phone_id,))
    flash("Phone removed.", "warning")
    return redirect(url_for("phones_list"))


# --- Phone-app API (login-exempt) -----------------------------------------
# register: gated by the shared HORUS_ALERT_TOKEN enrolment token.
# poll / ack: authenticated by the phone's own device_token.
@app.route("/api/alerts/register", methods=["POST"])
def api_alert_register():
    # A phone may self-enrol with its own device id (e.g. Android ID). Without
    # the optional shared token it lands as PENDING (active=0) and any operator
    # must approve it in the dashboard before it receives alerts. Supplying the
    # correct HORUS_ALERT_TOKEN auto-approves the phone (active=1).
    token = os.environ.get("HORUS_ALERT_TOKEN")
    trusted = bool(token) and request.headers.get("X-HORUS-ENROLL") == token

    data = request.get_json(silent=True) or request.form
    device_token = (data.get("device_token") or "").strip() or secrets.token_hex(16)
    label = (data.get("label") or "Unnamed phone").strip()
    platform = (data.get("platform") or "").strip()

    existing = db.query(
        "SELECT id, active FROM phones WHERE device_token=?", (device_token,), one=True
    )
    if existing:
        if trusted:
            db.execute(
                "UPDATE phones SET label=?, platform=?, active=1 WHERE id=?",
                (label, platform, existing["id"]),
            )
            active = 1
        else:
            # Update details but never silently re-disable or auto-approve.
            db.execute(
                "UPDATE phones SET label=?, platform=? WHERE id=?",
                (label, platform, existing["id"]),
            )
            active = existing["active"]
    else:
        active = 1 if trusted else 0
        db.execute(
            "INSERT INTO phones (label, device_token, platform, active) VALUES (?,?,?,?)",
            (label, device_token, platform, active),
        )

    return {"ok": True, "device_token": device_token, "pending": active == 0}


def _phone_from_token():
    data = request.get_json(silent=True) or request.values
    token = (data.get("device_token") or request.headers.get("X-HORUS-DEVICE") or "").strip()
    if not token:
        return None
    return db.query(
        "SELECT * FROM phones WHERE device_token=? AND active=1", (token,), one=True
    )


@app.route("/api/alerts/poll", methods=["GET", "POST"])
def api_alert_poll():
    phone = _phone_from_token()
    if not phone:
        return {"error": "unknown or inactive device"}, 401
    db.execute("UPDATE phones SET last_seen=datetime('now') WHERE id=?", (phone["id"],))
    pending = db.query(
        """SELECT d.id AS did, a.id AS alert_id, a.title, a.message, a.severity, a.created_at
           FROM alert_deliveries d JOIN alerts a ON a.id=d.alert_id
           WHERE d.phone_id=? AND d.status='PENDING' ORDER BY a.id""",
        (phone["id"],),
    )
    for r in pending:
        db.execute(
            "UPDATE alert_deliveries SET status='DELIVERED', delivered_at=datetime('now') WHERE id=?",
            (r["did"],),
        )
    return {
        "alerts": [
            {
                "id": r["alert_id"], "title": r["title"], "message": r["message"],
                "severity": r["severity"], "sent": r["created_at"],
            }
            for r in pending
        ]
    }


@app.route("/api/alerts/ack", methods=["POST"])
def api_alert_ack():
    phone = _phone_from_token()
    if not phone:
        return {"error": "unknown or inactive device"}, 401
    data = request.get_json(silent=True) or request.form
    alert_id = data.get("alert_id")
    db.execute(
        "UPDATE alert_deliveries SET status='ACKNOWLEDGED', acknowledged_at=datetime('now') "
        "WHERE alert_id=? AND phone_id=?",
        (alert_id, phone["id"]),
    )
    return {"ok": True}


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
