# First Bench Test: Matek F405-WING V2 + CP2102 + Pi 5

## Pre-flight

- [ ] Pi 5 set up, Python 3.12+, deps installed
- [ ] User in dialout: `groups` shows dialout
- [ ] FC powered, ArduPilot loaded, SERIAL0 (or telem port) configured for MAVLink
- [ ] CP2102 connected: `ls /dev/ttyUSB*` shows device (e.g. /dev/ttyUSB0)
- [ ] Baud match: SERIAL_BAUD matches FC (921600 or 115200)

## Env

- [ ] TELEMETRY_BACKEND=serial
- [ ] SERIAL_PORT=/dev/ttyUSB0  # or ttyACM0 for native USB
- [ ] SERIAL_BAUD=921600        # match FC

## Run

- [ ] Start app; logs show "Serial telemetry: port=... baud=..."
- [ ] Logs show "Heartbeat from system X component Y" within ~10s
- [ ] Logs show "Requested MAVLink message rates..."

## Verify

- [ ] curl localhost:8000/health → telemetry_status=connected, connected=true
- [ ] curl localhost:8000/state → state has lat, lon, mode, voltage, etc.
- [ ] Unplug USB; /health shows disconnected then backoff; replug → reconnects
- [ ] system_events table has telemetry_status_transition rows (if DB enabled)
