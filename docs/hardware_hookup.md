# Hardware Hookup Notes

Short practical notes for bench work. See [example_hardware.md](example_hardware.md) and [bench_first_test.md](bench_first_test.md) for full workflows.

---

## Camera Path

**Planned:** Pi Camera → Picamera2 → `camera.interface` → AiHatAiService.

- No capture yet. `camera.interface.CameraFrameProvider` is a placeholder.
- When Picamera2 is in hand, implement `get_frame() -> object | None` and wire into AiHatAiService.

---

## Serial Path

**FC UART** → CP2102/FTDI → Pi USB → `/dev/ttyUSB0`.

- CP2102/FTDI adapters appear as `/dev/ttyUSB0` on Linux.
- Native USB FC (direct connect) → `/dev/ttyACM0`.
- Set `SERIAL_PORT` and `SERIAL_BAUD=921600` (companion link). Use 57600 for telemetry radios.

---

## AI HAT vs Ollama

| Component | Role |
|-----------|------|
| **Ollama** | Text/reasoning, telemetry summary, event classification. State-only input. |
| **AI HAT** | Vision/detection (additive). Future: camera frames → HailoRT → AiResult. |

AI HAT runs alongside Ollama when enabled. ComposedAiService uses AI HAT result when meaningful, else Ollama.

---

## Matek F405-WING V2 Hookup

- Use **TELEM1** or **TELEM2** for MAVLink companion.
- FC params: `SERIALx_PROTOCOL=2` (MAVLink2), `SERIALx_BAUD=921` (921600).
- Wiring: FC UART TX → CP2102 RX; FC UART RX → CP2102 TX; FC GND → CP2102 GND.
- CP2102 USB → Pi 5.
