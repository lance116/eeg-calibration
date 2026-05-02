"""Stream BrainBit signal to stdout and optionally CSV.

Voltage values come out of the SDK in volts; we write microvolts in the CSV
since that is the conventional unit for EEG.
"""
from __future__ import annotations

import argparse
import csv
import threading
import time
from pathlib import Path
from typing import Optional, TextIO

from neurosdk.cmn_types import SensorCommand

from src._device import connect


SAMPLE_RATE_HZ = 250
CHANNELS = ("O1", "O2", "T3", "T4")
CSV_HEADER = ("t_host", "pack_num", "marker", *(f"{c}_uV" for c in CHANNELS))


def main() -> int:
    ap = argparse.ArgumentParser(description="Stream BrainBit signal to CSV.")
    ap.add_argument("--seconds", type=float, default=30.0, help="recording length (default 30)")
    ap.add_argument("--out", type=Path, default=None, help="CSV output path (optional)")
    ap.add_argument("--serial", default=None, help="target a specific headband by serial")
    ap.add_argument("--quiet", action="store_true", help="suppress per-second progress line")
    args = ap.parse_args()

    scanner, sensor, info = connect(args.serial)
    print(f"Connected to {info.Name} (serial={info.SerialNumber}); sampling at {SAMPLE_RATE_HZ} Hz")

    csv_file: Optional[TextIO] = None
    writer: Optional[csv.writer] = None
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        csv_file = open(args.out, "w", newline="")
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADER)

    counter = {"n": 0}
    lock = threading.Lock()

    def on_signal(_sensor, samples):
        now = time.time()
        rows = [
            (now, s.PackNum, s.Marker, s.O1 * 1e6, s.O2 * 1e6, s.T3 * 1e6, s.T4 * 1e6)
            for s in samples
        ]
        with lock:
            if writer is not None:
                writer.writerows(rows)
            counter["n"] += len(rows)

    sensor.signalDataReceived = on_signal

    threading.Thread(
        target=sensor.exec_command, args=(SensorCommand.StartSignal,), daemon=True
    ).start()

    start = time.time()
    try:
        next_tick = start + 1.0
        while True:
            elapsed = time.time() - start
            if elapsed >= args.seconds:
                break
            time.sleep(0.05)
            if not args.quiet and time.time() >= next_tick:
                with lock:
                    n = counter["n"]
                expected = int(elapsed * SAMPLE_RATE_HZ)
                drop = max(expected - n, 0)
                print(
                    f"  t={elapsed:5.1f}s  samples={n:>6}  drop={drop:>4}",
                    end="\r",
                    flush=True,
                )
                next_tick += 1.0
        if not args.quiet:
            print()
    except KeyboardInterrupt:
        print()
    finally:
        sensor.exec_command(SensorCommand.StopSignal)
        sensor.signalDataReceived = None
        sensor.disconnect()
        del sensor
        del scanner
        if csv_file is not None:
            csv_file.close()

    with lock:
        n = counter["n"]
    elapsed = time.time() - start
    print(f"Captured {n} samples in {elapsed:.1f}s ({n / max(elapsed, 1e-9):.1f} Hz effective)")
    if args.out is not None:
        print(f"Wrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
