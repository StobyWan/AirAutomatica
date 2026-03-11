# Raspberry Pi 5 Diagnostic Scripts

Fast on-device diagnostics for AirAutomatica on Raspberry Pi. Use these for thermal monitoring, throttling interpretation, and benchmarking before/after hardware or code changes.

**Note:** `vcgencmd` is Raspberry Pi–specific. Scripts degrade gracefully when run on non-Pi systems (e.g. temp from sysfs, throttled as N/A).

## Scripts

| Script | Purpose |
|--------|---------|
| `decode_throttled.sh` | Decode throttled flags from `vcgencmd get_throttled` or a raw value |
| `watch_thermal.sh` | Live thermal watch: temp, throttled, CPU freq, load (1s refresh) |
| `watch_ollama.sh` | Live system metrics + Ollama processes (2s refresh) |
| `log_thermal_csv.sh` | Log thermal metrics to CSV every 5s until Ctrl+C |
| `bench_snapshot.sh` | One-shot snapshot to stdout and `tmp/pi-bench-snapshot-*.txt` |
| `compare_snapshots.sh` | Compare two bench_snapshot files (before/after) |
| `inference_probe.sh` | Run short Ollama inference, capture thermal before/after |
| `watch_top_processes.sh` | Live top CPU and memory processes (2s refresh) |
| `quick_diag.sh` | Brief SSH-friendly checks including serial/video devices |

## Usage

### Decode throttled flags

```bash
# Use vcgencmd (Pi only)
./decode_throttled.sh

# Pass raw value (works anywhere)
./decode_throttled.sh 0xe0000
```

### Watch thermal state

```bash
./watch_thermal.sh
# Ctrl+C to exit
```

### Benchmark snapshot

```bash
./bench_snapshot.sh
# Prints to stdout and saves to tmp/pi-bench-snapshot-YYYYMMDD-HHMMSS.txt
```

### Watch top processes

```bash
./watch_top_processes.sh
# Ctrl+C to exit
```

### Watch Ollama processes

```bash
./watch_ollama.sh
# Ctrl+C to exit
```

### Log thermal to CSV

```bash
./log_thermal_csv.sh
# Logs to tmp/pi-thermal-YYYYMMDD-HHMMSS.csv, Ctrl+C to stop
```

### Compare snapshots

```bash
./compare_snapshots.sh tmp/pi-bench-snapshot-before.txt tmp/pi-bench-snapshot-after.txt
```

### Ollama inference probe

```bash
./inference_probe.sh
# or with model: ./inference_probe.sh gemma3:1b
```

### Quick SSH diagnosis

```bash
./quick_diag.sh
```

## Makefile targets

From the project root:

```bash
make pi-thermal     # Run watch_thermal.sh
make pi-ollama      # Run watch_ollama.sh
make pi-log-thermal # Run log_thermal_csv.sh
make pi-snapshot    # Run bench_snapshot.sh
make pi-diag        # Run quick_diag.sh
```

## Throttled flag reference

| Bit | Current | Historical |
|-----|---------|------------|
| 0x1 | Undervoltage now | Undervoltage occurred |
| 0x2 | ARM frequency capped now | ARM capping occurred |
| 0x4 | Throttling now | Throttling occurred |
| 0x8 | Soft temp limit now | Soft temp limit occurred |
