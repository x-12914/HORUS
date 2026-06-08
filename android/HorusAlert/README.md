# HORUS Alert — Android app

The phone client for HORUS **Defense Alert**. It enrols with the server, runs a
foreground service that polls for alerts every few seconds, and raises a
full-screen siren screen with a **looping alarm + vibration that does not stop
until the alert is acknowledged on the device**. The persistent notification
can't be swiped away and carries an **ACKNOWLEDGE** action; acknowledging from
the full-screen screen, the notification, or the in-app list stops the alarm
and reports the acknowledgement back to the dashboard.

Pure AndroidX + Kotlin coroutines + `HttpURLConnection`/`org.json` — no Retrofit
/ Firebase, so there's nothing external to configure.

## Build & run

1. In Android Studio: **File → Open** and select this folder
   (`android/HorusAlert`). Let it sync Gradle (it downloads the wrapper
   distribution automatically on first sync). Accept any AGP upgrade prompt.
2. Plug in an Android phone (USB debugging on) or start an emulator — **API 26+**.
3. Press **Run ▶**.

Requirements: Android Studio with JDK 17 (bundled in current versions), Android
SDK 34. `minSdk` is 26 (Android 8.0).

## Use it

The **server URL is built in** and the phone **identifies itself automatically**
by its Android ID — there's nothing to type but a label.

1. **Label / callsign** — how this phone shows up in the dashboard (e.g. `Alpha-1`).
2. Tap **ENROL THIS PHONE** → it registers using its Android ID and lands as
   **PENDING** in the dashboard.
3. An operator opens **Defense Alert → Manage Phones** and clicks **✓ Approve**
   for this phone (it shows the label and device id).
4. Tap **START MONITORING** → the foreground service begins polling. Grant the
   notification permission when prompted. (Before approval, logcat shows
   `awaiting approval`; once approved, alerts start arriving.)
5. Trigger an alert from the HORUS dashboard (**Defense Alert**). The phone's
   screen lights up with the full-screen siren and a looping alarm that **does
   not stop until you tap ACKNOWLEDGE**.

To point at a different server, change `Config.SERVER` and rebuild.

## How it talks to the server

| Action | Endpoint | Auth |
|---|---|---|
| Enrol | `POST /api/alerts/register` | body `device_token` (Android ID) — lands PENDING |
| Poll | `POST /api/alerts/poll` | body `device_token` (only approved phones) |
| Acknowledge | `POST /api/alerts/ack` | body `device_token` + `alert_id` |

## Notes & limitations

- **Delivery is poll-based** (every ~4s, see `AlertPollService.POLL_MS`). That's
  near-instant but not instantaneous and uses a persistent foreground service.
  For true push (screen lighting up instantly even with the app swiped away,
  better battery), the upgrade is **FCM**: keep these screens/endpoints, add a
  Firebase project + a `FirebaseMessagingService`, and have the server push via
  FCM instead of (or alongside) the poll. That's an additive change.
- **Battery optimisation**: Android may kill the background service. For a
  reliable receiver, exclude the app from battery optimisation
  (Settings → Apps → HORUS Alert → Battery → Unrestricted).
- **Android 14 foreground-service caps**: the service uses the `dataSync` type,
  which Android 14 limits to ~6h/day. Fine for trials; FCM removes the need for
  a long-running service.
- **Full-screen intents** on Android 14+ may require the "Full-screen
  notifications" special access for non-default apps — grant it if the siren
  screen doesn't appear over the lock screen.
- Uses the system **default alarm sound**; drop a custom sound into
  `res/raw/` and point the `airalert` channel at it to change the siren.

## Project structure

```
app/src/main/java/com/horus/alert/
  MainActivity.kt        config, enrol, start/stop, alert list + ack
  AlertPollService.kt    foreground poll loop + notifications
  AlertActivity.kt       full-screen AIR ALERT screen + alarm
  HorusApi.kt            register / poll / ack over HTTP
  AlertStore.kt          local persistence of received alerts
  Prefs.kt               settings + state
  BootReceiver.kt        resume monitoring after reboot
```
