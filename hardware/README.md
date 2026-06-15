# HORUS Asset Tracking — hardware (BLE)

Real-time, room-level asset tracking that feeds the HORUS **Asset Tracking**
module. It uses the standard beacon + gateway model:

```
  ESP32 (asset tag)            Raspberry Pi (room gateway)         HORUS server
  advertises BLE name   ─►     scans, matches HORUS- beacons   ─►  POST /api/track
  "HORUS-AST-0001"             reports which room it's in          asset shows in room
```

- **ESP32 = asset tag** — attach to an asset; advertises a fixed BLE name.
- **Raspberry Pi = room gateway** — one per room; scans for tags and reports
  sightings. Set its `HORUS_ROOM` to that room's code.
- Move a tag out of range → after a short timeout the gateway reports it
  **LEFT FACILITY**.

## Bill of materials (this starter)
- 1 × ESP32 dev board (the asset tag)
- 1 × Raspberry Pi with Bluetooth (Pi 3/4/5/Zero 2 W) on Wi-Fi (the gateway)
- USB power for each

---

## 1. Prepare HORUS (server, once)

**a) Enable the ingestion endpoint** — `/api/track` is disabled until a token is set:
```bash
# generate a token
python3 -c 'import secrets; print(secrets.token_hex(24))'

# add it to the service, then restart
sudo nano /etc/systemd/system/horus.service
#   under [Service]:  Environment="HORUS_INGEST_TOKEN=<paste token>"
sudo systemctl daemon-reload && sudo systemctl restart horus
```

**b) Create a Room and an Asset** in the dashboard:
- **Asset Tracking → Manage Rooms** → add a room, e.g. name `Armoury A`, **code `ARM-A`**.
- **Asset Tracking → Asset register → New** → set **BLE Device (device_id)** to the
  beacon name, e.g. `HORUS-AST-0001` (must match the ESP32 exactly).

> The gateway's `HORUS_ROOM` must equal the room **code** (or name), and the
> beacon name must equal the asset's **device_id** — those two matches are what
> make the asset appear in the right room.

**c) (Optional) Test the server with no hardware** — simulate a sighting:
```bash
curl -X POST https://horus.157.250.205.174.nip.io/api/track \
  -H "X-HORUS-TOKEN: <token>" -H "Content-Type: application/json" \
  -d '{"device_id":"HORUS-AST-0001","room":"ARM-A"}'
# → {"ok":true,...,"presence":"IN FACILITY"}   and the asset shows in ARM-A
```

---

## 2. Flash the ESP32 (asset tag)

1. In **Arduino IDE**, install the **“esp32” by Espressif Systems** boards
   package (Boards Manager). No extra libraries needed.
2. Open `esp32-beacon/esp32-beacon.ino`.
3. Set `BEACON_ID` to match the asset's `device_id` (e.g. `HORUS-AST-0001`).
   Keep the `HORUS-` prefix.
4. Board = **ESP32 Dev Module**, select the port, **Upload**.
5. Open Serial Monitor @ 115200 — you should see `advertising "HORUS-AST-0001"`.

One ESP32 per asset; give each a unique `BEACON_ID` and a matching HORUS asset.

---

## 3. Run the Raspberry Pi gateway (room)

```bash
# get the code onto the Pi (clone the repo, or just copy hardware/rpi-gateway/)
git clone https://github.com/x-12914/HORUS.git
cd HORUS/hardware/rpi-gateway

# make sure Bluetooth is on
sudo systemctl enable --now bluetooth

# install deps (a venv is fine too)
pip install -r requirements.txt

# run it — set the token and the room this Pi covers
HORUS_INGEST_TOKEN=<token> HORUS_ROOM=ARM-A python3 gateway.py
```

You should see scan output and `-> /api/track HORUS-AST-0001 room=ARM-A : 200 …`.

**Run it as a service (starts on boot):**
```bash
sudo cp horus-gateway.service /etc/systemd/system/horus-gateway.service
sudo nano /etc/systemd/system/horus-gateway.service     # set User, paths, token, room
sudo systemctl daemon-reload && sudo systemctl enable --now horus-gateway
journalctl -u horus-gateway -f
```

---

## 4. End-to-end test
1. Power the ESP32 near the Pi.
2. Start the gateway (step 3).
3. In HORUS → **Asset Tracking**, the asset moves into the room (presence
   **IN FACILITY**, status **LIVE**, last-seen updating).
4. Take the ESP32 far away / power it off → after ~20 s the gateway reports
   **LEFT FACILITY** and the asset updates.

---

## Configuration (gateway env vars)

| Variable | Meaning | Default |
|---|---|---|
| `HORUS_URL` | HORUS base URL | `https://horus.157.250.205.174.nip.io` |
| `HORUS_INGEST_TOKEN` | must equal server's `HORUS_INGEST_TOKEN` | `CHANGE_ME` |
| `HORUS_ROOM` | this gateway's room **code** in HORUS | `ARM-A` |
| `HORUS_PREFIX` | only track beacons whose name starts with this | `HORUS-` |
| `HORUS_RSSI_MIN` | ignore signals weaker than this (dBm) — raise toward `-70` to shrink the room | `-85` |
| `HORUS_SEEN_TIMEOUT` | seconds without a sighting before reporting LEFT | `20` |
| `HORUS_HEARTBEAT` | re-affirm presence every N seconds while seen | `30` |

---

## Scaling up
- **More assets:** flash more ESP32s, each with a unique `BEACON_ID`, and create a
  matching asset in HORUS.
- **More rooms:** add a gateway per room. Each can be another Raspberry Pi **or an
  ESP32 acting as a Wi-Fi gateway** (cheaper per room) — set each gateway's
  `HORUS_ROOM` to that room's code. The asset appears in whichever room's gateway
  sees it strongest; tune `HORUS_RSSI_MIN` so adjacent rooms don't overlap.
- **Battery tags:** add deep-sleep/advertising duty-cycling to the ESP32 sketch
  for long battery life.

## Troubleshooting
| Symptom | Fix |
|---|---|
| gateway prints `503` | set `HORUS_INGEST_TOKEN` on the **server** and restart horus |
| gateway prints `401` | the token on the Pi ≠ the token on the server |
| gateway prints `404 unknown device_id` | create an Asset whose `device_id` == the beacon name |
| asset never appears | beacon name must start with `HORUS_PREFIX`; check Serial Monitor; lower `HORUS_RSSI_MIN` |
| `scan error / Bluetooth` | `sudo systemctl enable --now bluetooth`; run the Pi gateway with adequate permissions |
| asset flips LEFT too quickly | increase `HORUS_SEEN_TIMEOUT` |
