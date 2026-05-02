"""End-to-end calibration session.

Steps:
  1. Connect to a BrainBit.
  2. Run a short resistance check and warn on poor channels.
  3. Record an eyes-open baseline.
  4. Record an eyes-closed baseline (alpha rhythm should be visible on O1/O2).

The CSV gets a ``phase`` column (``open``/``closed``) so analysis can split
the two segments without bookkeeping a second file.
"""
from __future__ import annotations

import argparse
import csv
import threading
import time
from pathlib import Path
from typing import Optional

from neurosdk.cmn_types import SensorCommand

from src._device import connect
from src.resistance import _fmt as fmt_ohms


SAMPLE_RATE_HZ = 250
CHANNELS = ("O1", "O2", "T3", "T4")
RESIST_BAD_THRESHOLD_OHMS = 2e6


def _resistance_check(sensor, seconds: float) -> dict[str, Optional[float]]:
    latest: dict[str, Optional[float]] = {c: None for c in CHANNELS}
    lock = threading.Lock()

    def on_resist(_sensor, samples):
        with lock:
            last = samples[-1]
            for c in CHANNELS:
                latest[c] = getattr(last, c)

    sensor.resistDataReceived = on_resist
    threading.Thread(
        target=sensor.exec_command, args=(SensorCommand.StartResist,), daemon=True
    ).start()
    time.sleep(seconds)
    sensor.exec_command(SensorCommand.StopResist)
    sensor.resistDataReceived = None
    return latest


def _record_phase(sensor, writer, phase: str, seconds: float) -> int:
    n = {"v": 0}
    lock = threading.Lock()

    def on_signal(_sensor, samples):
        now = time.time()
        rows = [
            (now, phase, s.PackNum, s.Marker, s.O1 * 1e6, s.O2 * 1e6, s.T3 * 1e6, s.T4 * 1e6)
            for s in samples
        ]
        with lock:
            writer.writerows(rows)
            n["v"] += len(rows)

    sensor.signalDataReceived = on_signal
    threading.Thread(
        target=sensor.exec_command, args=(SensorCommand.StartSignal,), daemon=True
    ).start()

    start = time.time()
    try:
        while time.time() - start < seconds:
            elapsed = time.time() - start
            with lock:
                count = n["v"]
            print(f"  [{phase}] t={elapsed:5.1f}/{seconds:.0f}s  samples={count}", end="\r", flush=True)
            time.sleep(0.1)
    finally:
        sensor.exec_command(SensorCommand.StopSignal)
        sensor.signalDataReceived = None
    print()
    return n["v"]


def main() -> int:
    ap = argparse.ArgumentParser(description="BrainBit calibration: contact check + baseline.")
    ap.add_argument("--out", type=Path, default=Path("data/baseline.csv"), help="CSV output path")
    ap.add_argument("--open-seconds", type=float, default=60.0, help="eyes-open duration")
    ap.add_argument("--closed-seconds", type=float, default=60.0, help="eyes-closed duration")
    ap.add_argument("--resist-seconds", type=float, default=8.0, help="contact-check duration")
    ap.add_argument("--serial", default=None, help="target a specific headband by serial")
    args = ap.parse_args()

    scanner, sensor, info = connect(args.serial)
    print(f"Connected to {info.Name} (serial={info.SerialNumber})")

    try:
        print(f"\n[1/3] Contact check ({args.resist_seconds:.0f}s) — sit still...")
        readings = _resistance_check(sensor, args.resist_seconds)
        bad = [c for c, v in readings.items() if v is None or v > RESIST_BAD_THRESHOLD_OHMS]
        for c in CHANNELS:
            tag = "BAD" if c in bad else "ok "
            print(f"    {c}: {fmt_ohms(readings[c])}  {tag}")
        if bad:
            print(f"  WARNING: {','.join(bad)} above {RESIST_BAD_THRESHOLD_OHMS / 1e6:.0f} MΩ.")
            print("  Reseat / dampen those electrodes; recording anyway.")

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(("t_host", "phase", "pack_num", "marker",
                             *(f"{c}_uV" for c in CHANNELS)))

            input(f"\n[2/3] Eyes OPEN, fixate softly. Press ENTER to start {args.open_seconds:.0f}s.")
            n_open = _record_phase(sensor, writer, "open", args.open_seconds)

            input(f"\n[3/3] Eyes CLOSED. Press ENTER to start {args.closed_seconds:.0f}s.")
            n_closed = _record_phase(sensor, writer, "closed", args.closed_seconds)

        print(f"\nDone. open={n_open} samples, closed={n_closed} samples")
        print(f"Wrote {args.out}")
    finally:
        sensor.disconnect()
        del sensor
        del scanner

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
