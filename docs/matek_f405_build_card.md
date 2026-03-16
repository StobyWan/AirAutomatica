# Matek F405-WING V2 Build Card

Quick reference for **Pi 5 + Matek F405-WING V2 + RP3 ELRS + BE-220 GPS** stack.

See [ardupilot_setup.md](ardupilot_setup.md) for general ArduPilot/MAVLink setup and [hardware_hookup.md](hardware_hookup.md) for serial path notes.

---

## Final Serial Layout

| Port | Component | Purpose | Notes |
|------|-----------|---------|-------|
| UART1 / SERIAL1 | Raspberry Pi 5 | MAVLink companion link | Use for highest-speed serial link |
| UART2 / SERIAL7 | RadioMaster RP3 ELRS | CRSF receiver | Use TX2/RX2, not SBUS |
| UART3 / SERIAL3 | BE-220 GPS | GPS | Good fit for GPS-only module |

---

## Pin-to-Pin Wiring

### Raspberry Pi 5 ↔ Flight Controller (UART1)

- Pi TX → FC RX1
- Pi RX → FC TX1
- Pi GND → FC GND
- Power the Pi from its own proper regulated 5V supply
- Do not rely on the FC UART pins to power the Pi

### RP3 ELRS Receiver ↔ Flight Controller (UART2)

- RP3 TX → FC RX2
- RP3 RX → FC TX2
- RP3 5V → regulated 5V rail
- RP3 GND → FC GND
- Do not use the SBUS pad for ELRS/CRSF

### BE-220 GPS ↔ Flight Controller (UART3)

- GPS TX → FC RX3
- GPS RX → FC TX3
- GPS 5V → regulated 5V rail
- GPS GND → FC GND

---

## ArduPilot Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| SERIAL1_PROTOCOL | 2 | MAVLink2 |
| SERIAL1_BAUD | 921 | 921600 baud |
| BRD_ALT_CONFIG | 1 | Board-specific |
| SERIAL7_PROTOCOL | 23 | CRSF |
| SERIAL7_OPTIONS | 0 | |
| SERIAL3_PROTOCOL | 5 | GPS |

---

## AirAutomatica Serial Config

When the Pi connects via UART1 (direct TX/RX, no USB adapter):

- `SERIAL_PORT=/dev/serial0` (or `/dev/ttyS0` on Pi 5)
- `SERIAL_BAUD=921600`

Enable UART via `raspi-config` → Interfacing Options → Serial (disable login shell, enable hardware).

---

## Bring-Up Order

1. **Receiver first**
   - Confirm RP3 binds and RC channels move correctly
2. **GPS second**
   - Confirm GPS is detected and reporting data
3. **Pi link last**
   - Start with clean UART wiring and shared ground
   - Test MAVLink link stability
   - If needed, test at a lower baud first, then move to 921600

---

## Power Discipline

- All devices must share a common ground
- Pi 5 needs its own robust regulated 5V supply
- Verify bench-power behavior on your exact board with a multimeter before assuming USB powers a given rail

---

## Quick Warnings

- CRSF/ELRS goes on TX2/RX2, not SBUS
- Pi serial goes on UART1 for the strongest link
- Keep wiring short, clean, and strain-relieved
- Do not power heavy accessories from uncertain rails without checking regulator limits

---

## Build Summary

This layout gives the Pi the best serial path, keeps the RP3 on the correct true-UART receiver path, and leaves the GPS on a clean dedicated port. It is the right baseline wiring plan for your current Matek F405-WING V2 + Pi 5 + RP3 + BE-220 stack.
