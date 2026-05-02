"""Shared helpers: scan for BrainBit headbands and connect to one."""
from __future__ import annotations

import time
from typing import Optional

from neurosdk.scanner import Scanner
from neurosdk.cmn_types import SensorFamily


SCAN_SECONDS_DEFAULT = 5.0


def scan(seconds: float = SCAN_SECONDS_DEFAULT) -> tuple[Scanner, list]:
    """Run a BLE scan and return (scanner, sensors_seen).

    The scanner is returned still alive so the caller can call
    ``scanner.create_sensor(...)`` on one of the SensorInfo entries.
    """
    scanner = Scanner([SensorFamily.LEBrainBit])
    seen: dict[str, object] = {}

    def on_change(_scanner, sensors):
        for s in sensors:
            seen[s.Address] = s

    scanner.sensorsChanged = on_change
    scanner.start()
    time.sleep(seconds)
    scanner.stop()
    scanner.sensorsChanged = None

    # Merge anything the SDK already had cached.
    for s in scanner.sensors():
        seen[s.Address] = s

    return scanner, list(seen.values())


def pick(sensors, serial: Optional[str] = None):
    """Pick the SensorInfo matching ``serial``, or the first one if not given."""
    if not sensors:
        return None
    if serial is None:
        return sensors[0]
    for s in sensors:
        if s.SerialNumber == serial:
            return s
    return None


def connect(serial: Optional[str] = None, scan_seconds: float = SCAN_SECONDS_DEFAULT):
    """Scan, pick a device, return (scanner, sensor, sensor_info).

    Raises RuntimeError if no matching device is found. The scanner must be
    kept alive for the lifetime of the sensor — return it so callers can hold
    a reference and clean up at the end.
    """
    scanner, sensors = scan(scan_seconds)
    info = pick(sensors, serial)
    if info is None:
        scanner = None  # let it dispose
        raise RuntimeError(
            f"No BrainBit found"
            + (f" with serial {serial}" if serial else "")
            + f" after {scan_seconds:.0f}s scan."
        )
    sensor = scanner.create_sensor(info)
    return scanner, sensor, info
