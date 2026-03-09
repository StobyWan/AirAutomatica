# ArduPilot / MAVLink Setup for AirAutomatica

Companion computer setup for **Matek F405-WING V2** running **ArduPilot Plane**.

## References

- [ArduPilot Raspberry Pi MAVLink](https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html)
- [ArduPilot common-serial-options](https://ardupilot.org/plane/docs/common-serial-options.html)
- [ArduPilot common-telemetry-port-setup](https://ardupilot.org/plane/docs/common-telemetry-port-setup.html)
- [ArduPilot mavlink-requesting-data](https://ardupilot.org/dev/docs/mavlink-requesting-data.html)
- [mavlink.io](https://mavlink.io/en/)

---

## Flight Controller Parameters

### USB Connection (SERIAL0)

When the Pi connects via USB cable to the FC:

- **SERIAL0** = USB (always). No parameter change needed.
- Set baud on the companion side to match (921600 or 115200 typical for USB virtual serial).

### UART Connection (SERIAL1 or SERIAL2)

When the Pi connects via UART (TX/RX/GND) to TELEM1 or TELEM2:

| Parameter | Value | Notes |
|-----------|-------|-------|
| SERIAL2_PROTOCOL | 2 | MAVLink2 |
| SERIAL2_BAUD | 921 | 921600 baud (ArduPilot parameter code) |

For SERIAL1 (TELEM1), use SERIAL1_PROTOCOL and SERIAL1_BAUD.

### Matek F405-WING Serial Layout

| SERIALx | Default | Physical |
|---------|---------|----------|
| SERIAL0 | Console | USB |
| SERIAL1 | Telemetry1 | USART1 |
| SERIAL2 | Empty | - |
| SERIAL3 | GPS1 | USART3 |
| SERIAL4 | GPS2 | UART4 |
| SERIAL5/6/7 | USER | UART5/6/2 |

---

## Companion Computer (Raspberry Pi)

### Port Mapping

| Connection | Pi Device | Baud |
|------------|-----------|------|
| USB (native CDC) | `/dev/ttyACM0` | 921600 |
| USB-serial adapter (CP2102, FTDI) | `/dev/ttyUSB0` | 921600 or 115200 |
| UART | `/dev/serial0` | 921600 |

USB-serial adapters (e.g. CP2102) appear as `/dev/ttyUSB*`. Confirm with `ls /dev/ttyUSB*` after plugging in.

Enable UART via `raspi-config` → Interfacing Options → Serial (disable login shell, enable hardware).

### Environment Variables

```bash
TELEMETRY_BACKEND=serial
SERIAL_PORT=/dev/ttyACM0   # or /dev/ttyUSB0 for CP2102/FTDI; /dev/serial0 for UART
SERIAL_BAUD=921600         # default; use 57600 for telemetry radios
```

---

## Connection Lifecycle and Telemetry Status

The serial MAVLink backend tracks a derived `telemetry_status` with these states:

| Status | Meaning |
|--------|---------|
| `starting` | Before first connection attempt |
| `connecting` | Waiting for HEARTBEAT |
| `connected` | Heartbeat recent, reader active |
| `stale` | Heartbeat timeout exceeded |
| `disconnected` | Connection lost |
| `backoff` | In reconnect backoff |

- Tracks `reconnect_count` and `last_disconnect_reason`
- `heartbeat_age_s` is `null` in API when unknown
- Detects serial disconnects and parser failures
- Automatically reconnects with exponential backoff (1s → 60s max)
- Re-runs heartbeat wait and message rate requests after each reconnect
- Exposes status via `/state` and `/health`
- Keeps mission logic running when telemetry is unavailable

---

## Message Rate Request

AirAutomatica sends `MAV_CMD_SET_MESSAGE_INTERVAL` (511) after receiving HEARTBEAT to request:

- GLOBAL_POSITION_INT (33) @ 10 Hz
- ATTITUDE (30) @ 10 Hz
- SYS_STATUS (1) @ 10 Hz
- VFR_HUD (74) @ 10 Hz

Requires ArduPilot 4.0+. See [mavlink-requesting-data](https://ardupilot.org/dev/docs/mavlink-requesting-data.html).

---

## Validated Against Docs

- MAVLink field units and sentinels ([mavlink.io common](https://mavlink.io/en/messages/common.html))
- SERIALx_BAUD mapping (921 → 921600)
- Message IDs and SET_MESSAGE_INTERVAL usage
- MAVLink2 preference (MAVLINK20=1)

---

## First Bench Test

See [bench_first_test.md](bench_first_test.md) for a step-by-step checklist.

---

## Assumptions Requiring Bench Validation (Matek F405-WING V2)

1. **Serial layout** matches F405-WING (SERIAL0=USB, SERIAL1=Telem1, SERIAL2=empty). V2 variant may differ.
2. **USB virtual serial baud:** 115200 vs 921600 when Pi connects via USB.
3. **SERIALx usage:** Pi via USB uses SERIAL0; Pi via UART uses SERIAL1 or SERIAL2 (configure which port has MAVLink).
4. **Message rates:** Actual rates after SET_MESSAGE_INTERVAL on this board.
5. **MAVLink2:** Compatibility on all ports.
