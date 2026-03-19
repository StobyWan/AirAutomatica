"""Vehicle control subsystem for rover and bench modes.

When VEHICLE_MODE is rover or bench, this subsystem is started instead of
the full telemetry/mission loop. It provides the bridge between browser
control and the flight controller or Arduino motor-control layer.
"""
