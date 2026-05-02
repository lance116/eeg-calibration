"""Live concentration / relaxation monitor.

Loops: record `--window` seconds via the Swift CLI, run BrainFlow's
pretrained MINDFULNESS + RESTFULNESS classifiers, print the scores. Run
until Ctrl-C.

  python -m analyze.live_state --window 12
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from brainflow.data_filter import DataFilter
from brainflow.ml_model import (BrainFlowClassifiers, BrainFlowMetrics,
                                BrainFlowModelParams, MLModel)


CHANNELS = ("O1", "O2", "T3", "T4")
SAMPLE_RATE_HZ = 250
EEGCLI = "./build/eegcli"


def _bar(score: float, width: int = 30) -> str:
    n = int(round(score * width))
    return "[" + "█" * n + "·" * (width - n) + "]"


def _score(features: np.ndarray, metric: BrainFlowMetrics) -> float:
    p = BrainFlowModelParams(metric.value, BrainFlowClassifiers.DEFAULT_CLASSIFIER.value)
    m = MLModel(p)
    m.prepare()
    try:
        return float(m.predict(features)[0])
    finally:
        m.release()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=float, default=12.0, help="seconds per measurement")
    ap.add_argument("--serial", default=None)
    args = ap.parse_args()

    print(f"Recording {args.window:.0f}s windows. Ctrl-C to stop.\n")
    print(f"  {'mindfulness (focus)':<35} {'restfulness (relax)':<35}")

    tmpdir = Path(tempfile.mkdtemp(prefix="eeg_live_"))
    try:
        i = 0
        while True:
            i += 1
            tmp = tmpdir / f"w{i}.csv"
            cmd = [EEGCLI, "stream", "--seconds", str(args.window), "--out", str(tmp), "--quiet"]
            if args.serial: cmd += ["--serial", args.serial]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                sys.stderr.write(r.stderr)
                return r.returncode

            df = pd.read_csv(tmp)
            cols = [f"{c}_uV" for c in CHANNELS]
            data = df[cols].to_numpy().T.astype(np.float64)
            avg, std = DataFilter.get_avg_band_powers(data, list(range(len(CHANNELS))),
                                                     SAMPLE_RATE_HZ, True)
            features = np.concatenate([avg, std])

            mind = _score(features, BrainFlowMetrics.MINDFULNESS)
            rest = _score(features, BrainFlowMetrics.RESTFULNESS)

            print(f"  {mind:.2f} {_bar(mind)}    {rest:.2f} {_bar(rest)}", flush=True)
            tmp.unlink()
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0
    finally:
        for f in tmpdir.glob("*"): f.unlink()
        os.rmdir(tmpdir)


if __name__ == "__main__":
    raise SystemExit(main())
