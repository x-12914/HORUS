/*
 * HORUS asset tag — ESP32 BLE beacon
 * =================================================
 * Attach this ESP32 to an asset. It advertises a fixed BLE name; a HORUS
 * gateway (Raspberry Pi) in each room scans for it and reports sightings to
 * the HORUS /api/track endpoint, so the asset shows up in that room.
 *
 * SETUP
 *   1. In HORUS -> Asset Tracking -> Asset register, create an asset whose
 *      "BLE Device" (device_id) EXACTLY matches BEACON_ID below.
 *   2. Set BEACON_ID for this tag (one per asset). Keep the "HORUS-" prefix —
 *      the gateway only tracks beacons whose name starts with it.
 *   3. Flash with Arduino IDE: Board = "ESP32 Dev Module" (install the
 *      "esp32 by Espressif Systems" boards package first). No extra libraries.
 *
 * Open the Serial Monitor at 115200 baud to confirm it is advertising.
 */

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

// ---- CONFIG: must match the asset's device_id in HORUS ----
#define BEACON_ID "HORUS-AST-0001"

void setup() {
  Serial.begin(115200);
  delay(200);

  BLEDevice::init(BEACON_ID);
  BLEAdvertising *advertising = BLEDevice::getAdvertising();

  BLEAdvertisementData advData;
  advData.setFlags(0x06);            // general discoverable, BR/EDR not supported
  advData.setName(BEACON_ID);        // the gateway matches on this name
  advertising->setAdvertisementData(advData);
  advertising->setScanResponseData(advData);  // also expose name in scan response

  advertising->setMinInterval(0x100);  // ~160 ms
  advertising->setMaxInterval(0x200);  // ~320 ms

  BLEDevice::startAdvertising();
  Serial.printf("HORUS beacon advertising as \"%s\"\n", BEACON_ID);
}

void loop() {
  // The BLE radio advertises on its own; nothing to do here.
  delay(5000);
  Serial.printf("advertising \"%s\" ...\n", BEACON_ID);
}
