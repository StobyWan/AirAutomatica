# Example Hardware / Bench Setup

This document describes one concrete companion-computer bench setup used with AIRAUTOMATICA. It is a **reference example**, not a requirement. The software is designed around MAVLink companion-computer patterns and works with other ArduPilot flight controllers and serial adapters.

---

## A. Example Flight Controller

**Matek F405-WING V2** — Fixed-wing flight controller running ArduPilot.

- Provides MAVLink telemetry over a UART (typically TELEM1 or TELEM2).
- AIRAUTOMATICA does not require this exact FC; any ArduPilot target with MAVLink over serial is compatible.

---

## B. Example Pi 5 Companion Setup

**Raspberry Pi 5** — Companion computer running AIRAUTOMATICA.

**Raspberry Pi AI HAT+** (Hailo-8L) — Optional onboard perception hardware.

- The AI HAT+ provides one-shot object detection via Hailo. See [ai_hat.md](ai_hat.md).
- AI HAT is optional; the app runs without it. Companion-side perception only; not flight-critical.

---

## C. Serial Link Example

**CP2102 USB-to-TTL adapter** — Connects the FC UART to the Pi 5 over USB serial.

- CP2102 and FTDI adapters typically appear as `/dev/ttyUSB0` on Linux.
- Native USB devices (e.g. some FCs connected directly) often appear as `/dev/ttyACM0`.
- Set `SERIAL_PORT` accordingly; e.g. `SERIAL_PORT=/dev/ttyUSB0` for CP2102.
- Matek F405-WING V2 (arriving): Use TELEM1 or TELEM2 with `SERIALx_PROTOCOL=2`, `SERIALx_BAUD=921`.

---

## D. Power Example

**5V 5A buck converter** — Steps down battery voltage to 5V for the Pi.

**Inline fuse holder** (18 AWG, 10A blade fuse) — Protects the battery feed.

**USB-C bare-wire pigtail** (5V 3A) — Practical wiring from buck converter to Pi USB-C power input.

- This project does **not** manage power electronics. This is a documented bench/example hardware stack only.
- **Do not power the Pi 5 from the flight controller 5V rail** — the FC cannot supply enough current for a Pi 5.

---

## Wiring Overview

- FC UART TX → CP2102 RX
- FC UART RX → CP2102 TX
- FC GND → CP2102 GND
- CP2102 USB → Raspberry Pi 5
- Pi 5 powered separately from buck converter (battery → fuse → buck → USB-C pigtail → Pi)

---

## Supported vs Example

| Category | Supported now | Example / future |
|----------|---------------|------------------|
| Telemetry | Serial MAVLink companion link | — |
| AI | Mock mode, Ollama simulation | AI HAT one-shot (Hailo-8L), Ollama advisory |
| Persistence | SQLite sessions, detections | — |
| Observability | Dashboard, API, health | — |
| Commands | — | Command-back to ArduPilot |
| Vision | — | Full camera pipeline |

---

## Safety / Disclaimer

- This is **experimental companion-computer software**.
- The flight controller remains **flight-critical**; the Pi, AI, and UI layers are **non-flight-critical**.
- Bench test thoroughly before field use.

---

## Example parts used

For reference, the setup described above was built with: Matek F405-WING V2, Raspberry Pi 5, Raspberry Pi AI HAT+ (13 TOPS), WWZMDiB CP2102 USB-to-TTL adapter, UCTRONICS 5V 5A buck converter, ecocstm inline fuse holders, Jienk USB-C pigtail.
