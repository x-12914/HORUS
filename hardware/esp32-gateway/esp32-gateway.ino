/*
 * HORUS room gateway — ESP32 (all-in-one, no Raspberry Pi needed)
 * =================================================================
 * The ESP32 sits in a room (on USB power), scans for HORUS asset-tag beacons
 * over Bluetooth LE, and reports sightings to HORUS over WiFi:
 *
 *     beacon (phone / Pico W / 2nd ESP32)  ->  THIS ESP32 scans + WiFi  ->  HORUS /api/track
 *
 *   - Sees a tag  -> reports it present in this room (presence IN FACILITY).
 *   - Tag gone for SEEN_TIMEOUT seconds -> reports it LEFT FACILITY once.
 *
 * REQUIREMENTS (Arduino IDE 2.x)
 *   - Boards: "esp32 by Espressif Systems"  (Boards Manager)
 *   - Library: "NimBLE-Arduino" by h2zero   (Library Manager)  <-- IMPORTANT
 *       NimBLE is used instead of the built-in BLE library because it leaves
 *       enough RAM to also run WiFi + TLS.
 *   - Board must have Bluetooth LE (classic ESP32, ESP32-C3, ESP32-C6, S3...).
 *     NOT an ESP32-S2 (no BT).
 *
 *   ESP32-C6 / C3 / S3 (newer chips):
 *     - use esp32 boards core 3.x  AND  NimBLE-Arduino 2.x
 *     - Board = e.g. "ESP32C6 Dev Module";  Tools -> "USB CDC On Boot" = Enabled
 *       (otherwise the Serial Monitor stays blank on native-USB boards)
 *
 * Fill in CONFIG / secrets.h, pick your board, Upload, open Serial Monitor @ 115200.
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <NimBLEDevice.h>

// WiFi creds + ingest token live in secrets.h (git-ignored).
// Copy secrets.h.example -> secrets.h and fill in your values.
#include "secrets.h"

// =================== CONFIG ===================
const char* WIFI_SSID    = SECRET_WIFI_SSID;
const char* WIFI_PASS    = SECRET_WIFI_PASS;
const char* INGEST_TOKEN = SECRET_INGEST_TOKEN;

const char* HORUS_URL   = "https://horus.157.250.205.174.nip.io/api/track";
const char* ROOM_CODE   = "ARM-A";        // this gateway's room code in HORUS
const char* NAME_PREFIX = "HORUS-";       // only track beacons whose name starts with this

const int   RSSI_MIN      = -85;          // ignore weaker (farther) signals; raise toward -70 to shrink the room
const int   SCAN_SECONDS  = 5;            // length of each BLE scan
const unsigned long SEEN_TIMEOUT = 20000; // ms without a sighting -> report LEFT
const unsigned long HEARTBEAT    = 30000; // ms: re-affirm presence while seen
// ==============================================

#define MAX_TAGS 16
struct Tag {
  String name;
  unsigned long lastSeen;
  unsigned long lastPost;
  bool departed;
  bool used;
};
Tag tags[MAX_TAGS];

NimBLEScan* pScan;

Tag* getTag(const String& name) {
  for (int i = 0; i < MAX_TAGS; i++) if (tags[i].used && tags[i].name == name) return &tags[i];
  for (int i = 0; i < MAX_TAGS; i++) if (!tags[i].used) {
    tags[i] = {name, 0, 0, false, true};
    return &tags[i];
  }
  return nullptr; // table full
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("WiFi connecting to %s ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) { delay(400); Serial.print("."); }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) Serial.printf("WiFi OK, IP %s\n", WiFi.localIP().toString().c_str());
  else Serial.println("WiFi FAILED (will retry)");
}

void postTrack(const String& deviceId, const char* room, const char* presence) {
  ensureWifi();
  if (WiFi.status() != WL_CONNECTED) return;

  String body = "{\"device_id\":\"" + deviceId + "\"";
  if (room)     body += ",\"room\":\"" + String(room) + "\"";
  if (presence) body += ",\"presence\":\"" + String(presence) + "\"";
  body += "}";

  WiFiClientSecure client;
  client.setInsecure();              // prototype: skip cert check. Pin the cert for production.
  HTTPClient http;
  if (!http.begin(client, HORUS_URL)) { Serial.println("http begin failed"); return; }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-HORUS-TOKEN", INGEST_TOKEN);
  int code = http.POST(body);
  String resp = http.getString();
  Serial.printf("  -> /api/track %s : %d %s\n", body.c_str(), code, resp.substring(0, 120).c_str());
  if (code == 404) Serial.printf("     (create an Asset in HORUS with device_id '%s')\n", deviceId.c_str());
  else if (code == 503) Serial.println("     (set HORUS_INGEST_TOKEN on the server and restart horus)");
  else if (code == 401) Serial.println("     (INGEST_TOKEN here does not match the server)");
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\nHORUS gateway | room=%s | tracking '%s*' (RSSI >= %d)\n", ROOM_CODE, NAME_PREFIX, RSSI_MIN);

  ensureWifi();

  NimBLEDevice::init("");
  pScan = NimBLEDevice::getScan();
  pScan->setActiveScan(true);          // request names (scan response)
  pScan->setInterval(100);
  pScan->setWindow(99);
}

void loop() {
  // NimBLE 2.x: blocking scan, duration in milliseconds.
  // (On NimBLE 1.4.x use:  pScan->start(SCAN_SECONDS, false)  instead.)
  NimBLEScanResults results = pScan->getResults(SCAN_SECONDS * 1000, false);
  unsigned long now = millis();

  for (int i = 0; i < results.getCount(); i++) {
    const NimBLEAdvertisedDevice* dev = results.getDevice(i);
    String name = String(dev->getName().c_str());
    if (name.length() == 0 || !name.startsWith(NAME_PREFIX)) continue;
    if (dev->getRSSI() < RSSI_MIN) continue;

    Tag* t = getTag(name);
    if (!t) continue;
    t->lastSeen = now;
    t->departed = false;
    if (t->lastPost == 0 || (now - t->lastPost) >= HEARTBEAT) {
      Serial.printf("[seen] %s rssi=%d\n", name.c_str(), dev->getRSSI());
      postTrack(name, ROOM_CODE, nullptr);   // presence defaults to IN FACILITY
      t->lastPost = now;
    }
  }
  pScan->clearResults();

  // departure detection
  for (int i = 0; i < MAX_TAGS; i++) {
    if (tags[i].used && !tags[i].departed && tags[i].lastSeen != 0 &&
        (now - tags[i].lastSeen) > SEEN_TIMEOUT) {
      Serial.printf("[gone] %s\n", tags[i].name.c_str());
      postTrack(tags[i].name, nullptr, "LEFT FACILITY");
      tags[i].departed = true;
      tags[i].lastPost = 0;
    }
  }
}
