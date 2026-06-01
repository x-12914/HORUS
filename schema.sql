-- Defense-LOG :: Operation Recording System
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

CREATE INDEX IF NOT EXISTS idx_casualties_mission ON casualties(mission_id);
CREATE INDEX IF NOT EXISTS idx_challenges_mission ON challenges(mission_id);
CREATE INDEX IF NOT EXISTS idx_reports_mission    ON reports(mission_id);
