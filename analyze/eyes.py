"""Eye-state alpha test. Computes alpha-band (8-13 Hz) power on O1/O2/T3/T4
across an eyes-open / eyes-closed calibration recording and prints the ratio.

Closed-eye alpha on O1/O2 is the canonical EEG sanity check — it should
go up by 3-10x. Temporal channels (T3/T4) should change much less.

  python -m analyze.eyes data/baseline.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, iirnotch, welch

CHANNELS = ("O1", "O2", "T3", "T4")
SAMPLE_RATE_HZ = 250
ALPHA_BAND = (8.0, 13.0)


def _filter(x: np.ndarray, line_hz: float = 60.0) -> np.ndarray:
    nyq = SAMPLE_RATE_HZ / 2
    bp_b, bp_a = butter(4, [1.0 / nyq, 45.0 / nyq], btype="band")
    nt_b, nt_a = iirnotch(line_hz / nyq, Q=30)
    return filtfilt(nt_b, nt_a, filtfilt(bp_b, bp_a, x, axis=0), axis=0)


def _alpha_power(signal: np.ndarray) -> np.ndarray:
    f, p = welch(signal, fs=SAMPLE_RATE_HZ, nperseg=min(len(signal), 1024), axis=0)
    mask = (f >= ALPHA_BAND[0]) & (f < ALPHA_BAND[1])
    return np.trapz(p[mask], f[mask], axis=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path, help="CSV from `eegcli calibrate` (must have a `phase` column)")
    ap.add_argument("--line-hz", type=float, default=60.0)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if "phase" not in df.columns:
        print("error: this CSV has no `phase` column. Use eegcli calibrate, not stream.")
        return 1

    cols = [f"{c}_uV" for c in CHANNELS]
    open_sig = _filter(df[df["phase"] == "open"][cols].to_numpy(), args.line_hz)
    closed_sig = _filter(df[df["phase"] == "closed"][cols].to_numpy(), args.line_hz)

    open_alpha = _alpha_power(open_sig)
    closed_alpha = _alpha_power(closed_sig)
    ratio = closed_alpha / np.maximum(open_alpha, 1e-12)

    print(f"\nAlpha-band (8-13 Hz) power, integrated over each phase:\n")
    print(f"  {'channel':<8} {'open (µV²)':>14} {'closed (µV²)':>14} {'closed/open':>12}")
    for i, c in enumerate(CHANNELS):
        bar = "█" * min(int(ratio[i]), 30)
        print(f"  {c:<8} {open_alpha[i]:>14.1f} {closed_alpha[i]:>14.1f} {ratio[i]:>11.2f}x  {bar}")
    print()
    occ = ratio[[CHANNELS.index("O1"), CHANNELS.index("O2")]].mean()
    tmp = ratio[[CHANNELS.index("T3"), CHANNELS.index("T4")]].mean()
    print(f"  occipital (O1/O2) mean ratio: {occ:.2f}x")
    print(f"  temporal  (T3/T4) mean ratio: {tmp:.2f}x")
    if occ > 2.0 and occ > tmp * 1.3:
        print("\n  Verdict: alpha rhythm clearly detected — this is real brain signal,")
        print("           not noise. The headband works as expected.")
    elif occ > 1.3:
        print("\n  Verdict: weak alpha effect. Real but small — usually a sign of")
        print("           tired electrodes or headband too loose on the back.")
    else:
        print("\n  Verdict: no clear alpha effect. Either the eyes-closed phase wasn't")
        print("           long enough, or the headband isn't reading occipital well.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
