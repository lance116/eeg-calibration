"""Live electrode contact-quality check.

Resistance comes back in ohms per channel. Rule of thumb for BrainBit dry
electrodes:
  < 750 kΩ  excellent
  < 2 MΩ    good — usable signal
  > 2 MΩ    reseat / wet the contact
"""
from __future__ import annotations

import argparse
import threading
import time
from typing import Optional

from neurosdk.cmn_types import SensorCommand

from src._device import connect


CHANNELS = ("O1", "O2", "T3", "T4")


def _fmt(ohms: Optional[float]) -> str:
    if ohms is None:
        return "  --   "
    if ohms >= 1e6:
        return f"{ohms / 1e6:5.2f} MΩ"
    return f"{ohms / 1e3:5.0f} kΩ"


def _quality(ohms: Optional[float]) -> str:
    if ohms is None:
        return "?"
    if ohms < 750e3:
        return "OK "
    if ohms < 2e6:
        return "ok "
    return "BAD"


def main() -> int:
    ap = argparse.ArgumentParser(description="Check BrainBit electrode contact resistance.")
    ap.add_argument("--seconds", type=float, default=20.0, help="how long to monitor (default 20)")
    ap.add_argument("--serial", default=None, help="target a specific headband by serial")
    args = ap.parse_args()

    scanner, sensor, info = connect(args.serial)
    print(f"Connected to {info.Name} (serial={info.SerialNumber})")

    latest: dict[str, Optional[float]] = {c: None for c in CHANNELS}
    lock = threading.Lock()

    def on_resist(_sensor, samples):
        # samples is a list of BrainBitResistData with O1/O2/T3/T4 fields.
        with lock:
            last = samples[-1]
            for c in CHANNELS:
                latest[c] = getattr(last, c)

    sensor.resistDataReceived = on_resist

    # Per docs, signal/resist commands should run off the main thread.
    threading.Thread(
        target=sensor.exec_command, args=(SensorCommand.StartResist,), daemon=True
    ).start()

    try:
        deadline = time.time() + args.seconds
        while time.time() < deadline:
            with lock:
                row = "  ".join(f"{c}: {_fmt(latest[c])} {_quality(latest[c])}" for c in CHANNELS)
            print(row, end="\r", flush=True)
            time.sleep(0.25)
        print()
    except KeyboardInterrupt:
        print()
    finally:
        sensor.exec_command(SensorCommand.StopResist)
        sensor.resistDataReceived = None
        sensor.disconnect()
        del sensor
        del scanner

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
