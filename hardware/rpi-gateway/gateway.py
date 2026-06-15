#!/usr/bin/env python3
"""HORUS BLE room gateway (Raspberry Pi).

Scans for HORUS asset-tag beacons (ESP32s advertising names that start with
HORUS-) and reports sightings to the HORUS /api/track endpoint. One gateway =
one room: set HORUS_ROOM to that room's code in HORUS.

  - When a beacon is seen (and strong enough), the asset is reported present in
    this room (presence -> IN FACILITY).
  - When a beacon hasn't been seen for SEEN_TIMEOUT seconds, it is reported as
    LEFT FACILITY once.

Config via environment variables (see defaults below).

Run:
    pip install -r requirements.txt
    HORUS_INGEST_TOKEN=... HORUS_ROOM=ARM-A python3 gateway.py
"""

import asyncio
import os
import time

import requests
from bleak import BleakScanner

# ---- configuration (override with environment variables) ----
HORUS_URL = os.environ.get("HORUS_URL", "https://horus.157.250.205.174.nip.io").rstrip("/")
INGEST_TOKEN = os.environ.get("HORUS_INGEST_TOKEN", "CHANGE_ME")   # = server's HORUS_INGEST_TOKEN
ROOM_CODE = os.environ.get("HORUS_ROOM", "ARM-A")                  # this gateway's room code in HORUS
NAME_PREFIX = os.environ.get("HORUS_PREFIX", "HORUS-")             # only track these beacons
RSSI_MIN = int(os.environ.get("HORUS_RSSI_MIN", "-85"))           # ignore weaker (farther) signals
SCAN_SECONDS = float(os.environ.get("HORUS_SCAN_SECONDS", "5"))   # length of each scan window
HEARTBEAT = float(os.environ.get("HORUS_HEARTBEAT", "30"))        # re-affirm presence every N s while seen
SEEN_TIMEOUT = float(os.environ.get("HORUS_SEEN_TIMEOUT", "20"))  # no sighting for N s -> report LEFT

last_seen = {}    # device_id -> timestamp last seen this session
last_post = {}    # device_id -> timestamp we last reported "present"
departed = set()  # device_ids already reported as LEFT


def post_track(device_id, room=None, presence=None):
    body = {"device_id": device_id}
    if room:
        body["room"] = room
    if presence:
        body["presence"] = presence
    try:
        r = requests.post(
            f"{HORUS_URL}/api/track", json=body,
            headers={"X-HORUS-TOKEN": INGEST_TOKEN}, timeout=10,
        )
        tag = f"room={room}" if room else f"presence={presence}"
        print(f"  -> /api/track {device_id} {tag} : {r.status_code} {r.text.strip()[:140]}")
        if r.status_code == 404:
            print(f"     (create an Asset in HORUS with device_id '{device_id}')")
        elif r.status_code == 503:
            print("     (set HORUS_INGEST_TOKEN on the server and restart horus)")
        elif r.status_code == 401:
            print("     (HORUS_INGEST_TOKEN here does not match the server)")
    except Exception as e:
        print(f"  -> POST failed: {e}")


async def main():
    print(f"HORUS gateway | room='{ROOM_CODE}' | server={HORUS_URL}")
    print(f"tracking beacons named '{NAME_PREFIX}*' with RSSI >= {RSSI_MIN} dBm\n")
    while True:
        try:
            devices = await BleakScanner.discover(timeout=SCAN_SECONDS, return_adv=True)
        except Exception as e:
            print(f"scan error: {e} (is Bluetooth enabled?)")
            await asyncio.sleep(3)
            continue

        now = time.time()
        # discover(return_adv=True) returns {address: (BLEDevice, AdvertisementData)}
        for device, adv in devices.values():
            name = (adv.local_name or device.name or "")
            if not name.startswith(NAME_PREFIX):
                continue
            if adv.rssi is not None and adv.rssi < RSSI_MIN:
                continue
            last_seen[name] = now
            departed.discard(name)
            if name not in last_post or (now - last_post[name]) >= HEARTBEAT:
                print(f"[seen] {name} rssi={adv.rssi}")
                post_track(name, room=ROOM_CODE)
                last_post[name] = now

        # departure detection: seen before, but not lately
        for name, seen_at in list(last_seen.items()):
            if (now - seen_at) > SEEN_TIMEOUT and name not in departed:
                print(f"[gone] {name} (no sighting for {SEEN_TIMEOUT:.0f}s)")
                post_track(name, presence="LEFT FACILITY")
                departed.add(name)
                last_post.pop(name, None)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
