"""Run BrainFlow's pretrained MINDFULNESS (concentration) and RESTFULNESS
(relaxation) classifiers on our recordings.

These are BrainFlow's stock band-power → logistic-regression models, the same
class of algorithm BrainBit's SmartBeat app uses. Each output is in [0, 1]
where higher = more of that state.

  python -m analyze.state data/calm_*.csv data/happy_*.csv data/sad_*.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from brainflow.data_filter import DataFilter
from brainflow.ml_model import (BrainFlowClassifiers, BrainFlowMetrics,
                                BrainFlowModelParams, MLModel)


CHANNELS = ("O1", "O2", "T3", "T4")
SAMPLE_RATE_HZ = 250


def _score(metric: BrainFlowMetrics, features: np.ndarray) -> float:
    p = BrainFlowModelParams(metric.value, BrainFlowClassifiers.DEFAULT_CLASSIFIER.value)
    m = MLModel(p)
    m.prepare()
    try:
        return float(m.predict(features)[0])
    finally:
        m.release()


def analyze(path: Path) -> dict:
    df = pd.read_csv(path)
    cols = [f"{c}_uV" for c in CHANNELS]
    data = df[cols].to_numpy().T.astype(np.float64)  # (n_chan, n_samples)

    avg, std = DataFilter.get_avg_band_powers(data, list(range(len(CHANNELS))), SAMPLE_RATE_HZ, True)
    features = np.concatenate([avg, std])

    return {
        "file": path.name,
        "label": (df["label"].iloc[0] if "label" in df.columns else "?"),
        "duration_s": len(df) / SAMPLE_RATE_HZ,
        "mindfulness": _score(BrainFlowMetrics.MINDFULNESS, features),
        "restfulness": _score(BrainFlowMetrics.RESTFULNESS, features),
        "bands": dict(zip(["delta", "theta", "alpha", "beta", "gamma"], avg)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+", type=Path)
    args = ap.parse_args()

    results = [analyze(p) for p in args.csvs]

    print(f"\n{'file':<18} {'label':<8} {'mind.':>7} {'rest.':>7}  bands (relative)")
    print("-" * 78)
    for r in results:
        bands = "  ".join(f"{k[0].upper()}={v:.2f}" for k, v in r["bands"].items())
        print(f"  {r['file']:<16} {r['label']:<8} {r['mindfulness']:>6.2f}  {r['restfulness']:>6.2f}  {bands}")

    df = pd.DataFrame(results)
    if df["label"].nunique() > 1:
        print("\nMean by label:")
        agg = df.groupby("label")[["mindfulness", "restfulness"]].mean()
        print(agg.round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
