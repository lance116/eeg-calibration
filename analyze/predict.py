"""Predict emotion from a recorded CSV using a trained model.

  python -m analyze.predict data/test.csv --model analyze/model.joblib
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import joblib
import numpy as np

from .features import _features_for_epoch, epoch, load_csv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--model", type=Path, default=Path("analyze/model.joblib"))
    args = ap.parse_args()

    bundle = joblib.load(args.model)
    pipe = bundle["pipeline"]
    line_hz = bundle.get("line_hz", 60.0)

    sig, file_label = load_csv(args.csv, line_hz=line_hz)
    epochs = epoch(sig)
    if epochs.shape[0] == 0:
        print("Recording too short for one full epoch.")
        return 1
    X = np.stack([_features_for_epoch(e) for e in epochs], axis=0)
    preds = pipe.predict(X)
    probs = pipe.predict_proba(X)
    classes = list(pipe.classes_)

    print(f"File: {args.csv.name}  (true label: {file_label or '?'})")
    print(f"{epochs.shape[0]} epochs ({epochs.shape[0] * 2:.0f}s of signal after epoching)")
    print()
    counts = Counter(preds)
    for c in classes:
        share = counts.get(c, 0) / len(preds)
        avg_p = probs[:, classes.index(c)].mean()
        print(f"  {c:>10}: {counts.get(c, 0):>3}/{len(preds)} epochs ({share:.0%})  mean P={avg_p:.2f}")
    winner = counts.most_common(1)[0][0]
    print(f"\nMajority vote: {winner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
