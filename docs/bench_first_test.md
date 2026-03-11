# First Bench Test: Pi 5 + CP2102 + Matek F405-WING V2

**Upcoming: Matek F405-WING V2.** Use TELEM1 or TELEM2 with `SERIALx_PROTOCOL=2`, `SERIALx_BAUD=921`. FC UART TX→CP2102 RX, RX→CP2102 TX, GND→GND.

## 1. Confirm device

- [ ] `ls /dev/ttyUSB*` shows device (e.g. /dev/ttyUSB0) for CP2102
- [ ] `groups` includes dialout; if not: `sudo usermod -a -G dialout $USER` then re-login

## 2. Env

- [ ] TELEMETRY_BACKEND=serial
- [ ] SERIAL_PORT=/dev/ttyUSB0  # CP2102; use /dev/ttyACM0 for native USB
- [ ] SERIAL_BAUD=921600       # match FC

## 3. Run

- [ ] Start app; logs show "Serial telemetry: port=... baud=..."
- [ ] Within ~10s: "Heartbeat from system X component Y" and "Requested MAVLink message rates..."

## 4. Verify /health

- [ ] curl localhost:8000/health
- [ ] telemetry_backend=serial, telemetry_status=connected, connected=true
- [ ] persistence_enabled, session_id present

## 5. Verify /state

- [ ] curl localhost:8000/state
- [ ] state has lat, lon, mode, voltage, etc.

## 6. Session + SQLite

- [ ] sqlite3 ~/.airautomatica/airautomatica.db "SELECT id, started_at, ended_at FROM flight_sessions ORDER BY id DESC LIMIT 3"
- [ ] system_events has telemetry_status_transition rows

## 7. Unplug/replug

- [ ] Unplug CP2102; poll /health until telemetry_status in (disconnected, backoff)
- [ ] Replug; poll until telemetry_status=connected
- [ ] Ctrl+C; verify session ended_at in DB
