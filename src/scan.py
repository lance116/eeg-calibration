"""Discover BrainBit headbands within Bluetooth range."""
from __future__ import annotations

import argparse

from src._device import scan


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan for BrainBit headbands.")
    ap.add_argument("--seconds", type=float, default=5.0, help="scan duration (default 5)")
    args = ap.parse_args()

    print(f"Scanning for {args.seconds:.0f}s...")
    scanner, sensors = scan(args.seconds)

    if not sensors:
        print("No headbands found. Make sure the device is powered on and in range,")
        print("and that Terminal has Bluetooth permission in System Settings.")
        return 1

    print(f"Found {len(sensors)} device(s):")
    for s in sensors:
        print(f"  - {s.Name}  serial={s.SerialNumber}  addr={s.Address}  rssi={s.RSSI} dBm")

    del scanner
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
