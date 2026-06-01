"""Seed Defense-LOG with a realistic (fictional) demo dataset.

Called automatically on first run via app.py. The data is invented for
demonstration only — codenames, names and locations are not real.
"""

import sqlite3


MISSIONS = [
    # codename, op_name, branch, classification, commander, location, objective,
    # start, end, status, outcome, summary
    ("IRON SENTINEL", "Northern Border Reinforcement", "Army", "RESTRICTED",
     "Col. A. Marwan", "Northern Frontier, Sector 4",
     "Establish a forward defensive line and deter cross-border incursions.",
     "2023-03-12", "2023-05-08", "COMPLETED", "SUCCESS",
     "Defensive line held for the full deployment. No territory lost. Two minor injuries during entrenchment."),

    ("SILENT HARBOR", "Coastal Anti-Smuggling Patrol", "Navy", "CONFIDENTIAL",
     "Cdr. R. Idris", "Eastern Coastal Waters",
     "Interdict maritime smuggling routes and secure the territorial sea.",
     "2023-06-01", "2023-09-30", "COMPLETED", "PARTIAL",
     "Three vessels intercepted; two evaded in poor visibility. Recommend additional fast-boat assets."),

    ("DESERT FALCON", "High-Value Target Extraction", "Special Forces", "TOP SECRET",
     "Maj. K. Selim", "Southern Desert Belt",
     "Locate and extract a high-value detainee from a fortified compound.",
     "2024-01-19", "2024-01-20", "COMPLETED", "SUCCESS",
     "Target extracted within 40 minutes. Clean exfil. One operator wounded by shrapnel."),

    ("STORM VIGIL", "Air Superiority Sweep", "Air Force", "SECRET",
     "Lt. Col. N. Haddad", "Western Airspace Corridor",
     "Achieve and maintain air superiority over the western corridor during the offensive.",
     "2024-02-03", "2024-02-17", "COMPLETED", "SUCCESS",
     "Corridor secured. No friendly aircraft losses. Sustained operations limited by spare-part shortages."),

    ("GRANITE SHIELD", "Mountain Pass Defense", "Army", "RESTRICTED",
     "Col. T. Bashir", "Highland Pass 9",
     "Deny enemy use of the highland pass through fortified positions.",
     "2024-04-10", None, "ONGOING", "PENDING",
     "Positions established and holding. Resupply remains the principal constraint."),

    ("BLUE LANTERN", "Joint Disaster Relief", "Joint", "UNCLASSIFIED",
     "Brig. S. Othman", "Flood Zone, River Delta",
     "Coordinate multi-branch humanitarian relief following severe flooding.",
     "2024-07-22", "2024-08-15", "COMPLETED", "SUCCESS",
     "12,000 civilians evacuated. Inter-branch coordination strong; civil-comms interoperability needs work."),

    ("NIGHT TALON", "Reconnaissance Insertion", "Special Forces", "SECRET",
     "Cpt. Y. Nasr", "Contested Valley, Sector 7",
     "Insert a recon team to confirm enemy troop concentrations.",
     "2024-09-05", "2024-09-06", "ABORTED", "FAILURE",
     "Insertion compromised by enemy patrol. Team extracted under fire. Intel objective not met."),

    ("EAGLE PROMISE", "Strategic Airlift", "Air Force", "CONFIDENTIAL",
     "Lt. Col. M. Qadir", "Central Logistics Hub",
     "Sustain a strategic airlift bridge to forward bases during the campaign.",
     "2025-01-08", None, "ONGOING", "PENDING",
     "Airlift bridge operational. Crew fatigue and airframe hours being monitored closely."),
]

# (mission_index, service_number, name, rank, unit, type, date, notes)
CASUALTIES = [
    (0, "1043221", "F. Aziz", "Corporal", "3rd Infantry", "WIA", "2023-04-02", "Sprain during entrenchment. Returned to duty."),
    (0, "1043884", "H. Omar", "Private", "3rd Infantry", "WIA", "2023-04-19", "Minor laceration."),
    (2, "2207733", "D. Karim", "Sergeant", "1st SF Sqn", "WIA", "2024-01-20", "Shrapnel wound, left arm. Evacuated, stable."),
    (3, "3300912", "—", "Flt. Lt.", "12 Sqn", "MIA", "2024-02-11", "Ejection over corridor; SAR ongoing at time of report."),
    (6, "2209981", "L. Sami", "Corporal", "2nd SF Sqn", "KIA", "2024-09-05", "Killed during contact on insertion."),
    (6, "2209982", "B. Nadir", "Private", "2nd SF Sqn", "WIA", "2024-09-05", "Gunshot wound, leg. Extracted."),
    (4, "1109221", "R. Tariq", "Lance Cpl.", "8th Mountain", "WIA", "2024-05-30", "Frostbite, two fingers."),
]

# (mission_index, category, severity, description, resolution)
CHALLENGES = [
    (0, "Logistics", "MEDIUM", "Delayed delivery of fortification materials slowed line construction.", "Local procurement arranged; 4-day delay absorbed."),
    (1, "Weather", "HIGH", "Persistent fog reduced radar and visual interdiction effectiveness.", "Added night-vision boat crews mid-deployment."),
    (1, "Equipment", "MEDIUM", "Two patrol boats grounded for engine repair.", "Rotated reserve craft from adjacent command."),
    (2, "Intelligence", "HIGH", "Compound layout differed from pre-mission imagery.", "Team adapted entry plan on contact; objective still met."),
    (3, "Logistics", "CRITICAL", "Critical shortage of avionics spare parts limited sortie generation.", "Cannibalised non-mission airframes; emergency order placed."),
    (4, "Terrain", "HIGH", "Steep approach routes restricted vehicle resupply to mule/porter only.", "Established porter relay; air-drop requested."),
    (4, "Communication", "MEDIUM", "Line-of-sight radio gaps between forward positions.", "Relay station deployed on Ridge 4."),
    (5, "Communication", "HIGH", "Civil and military radio nets were not interoperable.", "Liaison officers embedded with civil agencies."),
    (6, "Enemy", "CRITICAL", "Insertion point under unexpected enemy patrol coverage.", "Mission aborted to preserve the team."),
    (7, "Equipment", "HIGH", "Accumulating airframe hours raising maintenance risk.", "Maintenance surge scheduled; flight hours capped."),
]

# (mission_index, title, type, author, content)
REPORTS = [
    (0, "After-Action Review — IRON SENTINEL", "AAR", "Col. A. Marwan",
     "Objective achieved. Defensive line constructed and held for the full 57-day deployment.\n\nLessons: pre-position fortification materials; integrate engineering assets earlier in planning."),
    (2, "Extraction Debrief — DESERT FALCON", "DEBRIEF", "Maj. K. Selim",
     "HVT secured and extracted in 38 minutes against an initial 60-minute estimate.\n\nIntel imagery was 3 weeks stale — recommend tighter ISR-to-execution timelines for time-sensitive targets."),
    (3, "Situation Report 07 — STORM VIGIL", "SITREP", "Lt. Col. N. Haddad",
     "Air superiority maintained over the corridor. One aircraft lost (pilot MIA, SAR ongoing). Spare-parts pipeline is the limiting factor for sustained tempo."),
    (6, "Intelligence Summary — NIGHT TALON", "INTEL", "Cpt. Y. Nasr",
     "Insertion compromised; primary intel objective not achieved. Contact suggests enemy patrol density in Sector 7 is higher than assessed. Re-evaluate insertion corridors before any re-attempt."),
    (5, "After-Action Review — BLUE LANTERN", "AAR", "Brig. S. Othman",
     "Relief operation successful: 12,000 civilians evacuated, zero relief-force casualties.\n\nPrimary friction was civil-military radio interoperability — recommend a standing joint comms SOP."),
]


def seed_if_empty(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    existing = cur.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
    if existing:
        conn.close()
        return  # Already populated — never duplicate.

    mission_ids = []
    for m in MISSIONS:
        cur.execute(
            """INSERT INTO missions
               (codename, operation_name, branch, classification, commander, location,
                objective, start_date, end_date, status, outcome, summary)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", m)
        mission_ids.append(cur.lastrowid)

    for idx, *rest in CASUALTIES:
        cur.execute(
            """INSERT INTO casualties
               (mission_id, service_number, name, rank, unit, casualty_type, date, notes)
               VALUES (?,?,?,?,?,?,?,?)""", (mission_ids[idx], *rest))

    for idx, *rest in CHALLENGES:
        cur.execute(
            """INSERT INTO challenges (mission_id, category, severity, description, resolution)
               VALUES (?,?,?,?,?)""", (mission_ids[idx], *rest))

    for idx, *rest in REPORTS:
        cur.execute(
            """INSERT INTO reports (mission_id, title, report_type, author, content)
               VALUES (?,?,?,?,?)""", (mission_ids[idx], *rest))

    conn.commit()
    conn.close()
    print(f"  Seeded {len(MISSIONS)} missions + linked records.")
