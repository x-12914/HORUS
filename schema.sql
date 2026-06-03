-- HORUS :: Historical Operations Record & Unified Storage
-- SQLite schema. All operational data is stored here and forms the
-- historical database used for strategic decision-making.

PRAGMA foreign_keys = ON;

-- Operator accounts that may access the system.
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'operator', -- operator / admin
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Core record of every mission / operation.
CREATE TABLE IF NOT EXISTS missions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codename        TEXT    NOT NULL,
    operation_name  TEXT    NOT NULL,
    branch          TEXT    NOT NULL,   -- Army / Navy / Air Force / Joint / Special Forces
    classification  TEXT    NOT NULL DEFAULT 'RESTRICTED',
    commander       TEXT,
    location        TEXT,
    objective       TEXT,
    start_date      TEXT,               -- ISO date
    end_date        TEXT,               -- ISO date (nullable while ongoing)
    status          TEXT    NOT NULL DEFAULT 'PLANNED', -- PLANNED/ONGOING/COMPLETED/ABORTED/COMPROMISED
    outcome         TEXT    NOT NULL DEFAULT 'PENDING',  -- SUCCESS/PARTIAL/FAILURE/PENDING
    summary         TEXT,               -- outcome narrative
    drone_feed_url  TEXT,               -- live drone feed source (added later; placeholder for now)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Drone feeds assigned to a mission. A mission may have many drones; each
-- feed carries its own callsign and (eventually) a live stream URL. Until a
-- URL is supplied the dossier/wall renders an OFFLINE placeholder.
CREATE TABLE IF NOT EXISTS drone_feeds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id      INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    callsign        TEXT    NOT NULL DEFAULT 'UAV',  -- e.g. UAV-01, REAPER-3
    model           TEXT,                            -- e.g. MQ-9, Quadcopter
    feed_url        TEXT,                            -- live stream URL (nullable)
    status          TEXT    NOT NULL DEFAULT 'OFFLINE', -- ONLINE/OFFLINE/STANDBY/LOST
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Personnel casualties documented per mission.
CREATE TABLE IF NOT EXISTS casualties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id      INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    service_number  TEXT,
    name            TEXT,
    rank            TEXT,
    unit            TEXT,
    casualty_type   TEXT    NOT NULL DEFAULT 'WIA', -- KIA/WIA/MIA/POW
    date            TEXT,
    notes           TEXT
);

-- Operational challenges / obstacles encountered.
CREATE TABLE IF NOT EXISTS challenges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id      INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    category        TEXT    NOT NULL DEFAULT 'Other', -- Logistics/Intelligence/Weather/Equipment/Communication/Terrain/Enemy/Other
    severity        TEXT    NOT NULL DEFAULT 'MEDIUM', -- LOW/MEDIUM/HIGH/CRITICAL
    description     TEXT    NOT NULL,
    resolution      TEXT
);

-- Facility rooms / zones. A BLE gateway in each room reports which tagged
-- assets it can currently see; `code` is the identifier the gateway maps to.
CREATE TABLE IF NOT EXISTS rooms (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    code            TEXT,                 -- gateway/zone code, e.g. ARM-A
    zone            TEXT,                 -- building / block
    description     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Trackable inventory assets. Each is a unique item carrying its own BLE tag
-- (device_id). Location is hardware-driven: current_room_id / presence /
-- last_seen stay UNKNOWN until the BLE tracking hardware is connected.
CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_tag       TEXT    NOT NULL UNIQUE,  -- inventory tag, e.g. AST-0001
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'General',
    serial          TEXT,
    device_id       TEXT,                 -- BLE beacon/tag id (nullable)
    tracking_status TEXT    NOT NULL DEFAULT 'AWAITING HARDWARE', -- AWAITING HARDWARE/LIVE/LOST/DISABLED
    current_room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL,
    presence        TEXT    NOT NULL DEFAULT 'UNKNOWN', -- UNKNOWN/IN FACILITY/LEFT FACILITY
    last_seen       TEXT,                 -- timestamp of last BLE fix (nullable)
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- After-action reports, situation reports, intel debriefs, etc.
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id      INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    title           TEXT    NOT NULL,
    report_type     TEXT    NOT NULL DEFAULT 'AAR', -- AAR/SITREP/INTEL/DEBRIEF
    author          TEXT,
    content         TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_casualties_mission  ON casualties(mission_id);
CREATE INDEX IF NOT EXISTS idx_challenges_mission  ON challenges(mission_id);
CREATE INDEX IF NOT EXISTS idx_reports_mission     ON reports(mission_id);
CREATE INDEX IF NOT EXISTS idx_drone_feeds_mission ON drone_feeds(mission_id);
CREATE INDEX IF NOT EXISTS idx_assets_room          ON assets(current_room_id);
CREATE INDEX IF NOT EXISTS idx_assets_device        ON assets(device_id);
