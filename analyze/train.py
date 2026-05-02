"""Train + evaluate emotion classifiers on labeled BrainBit recordings.

Runs three reports per dataset: full multi-class, calm-vs-music (arousal
proxy), and happy-vs-sad (valence). Uses LeaveOneGroupOut so accuracy
reflects new-recording generalization.

  python -m analyze.train data/happy_*.csv data/calm_*.csv data/sad_*.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import build_features


def _make_pipe() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("clf",   LogisticRegression(max_iter=5000, C=1.0, solver="lbfgs")),
    ])


def _evaluate(X: np.ndarray, y: np.ndarray, groups: np.ndarray, label: str) -> dict:
    classes = sorted(set(y))
    if len(classes) < 2:
        print(f"\n=== {label} ===  only one class, skipping")
        return {}

    print(f"\n=== {label} ===")
    print(f"  classes: {classes}  chance: {1/len(classes):.3f}")
    cv = LeaveOneGroupOut()
    accs, all_true, all_pred = [], [], []
    for tr, te in cv.split(X, y, groups):
        held = sorted(set(groups[te]))
        if len(set(y[tr])) < 2:
            print(f"  fold held_out={held}: training set has <2 classes, skipping")
            continue
        pipe = _make_pipe()
        pipe.fit(X[tr], y[tr])
        pred = pipe.predict(X[te])
        acc = (pred == y[te]).mean()
        print(f"  held_out={held}: acc={acc:.3f}  ({(pred == y[te]).sum()}/{len(pred)})")
        accs.append(acc); all_true.extend(y[te]); all_pred.extend(pred)

    if not accs:
        return {}
    print(f"  mean: {np.mean(accs):.3f} ± {np.std(accs):.3f}")
    cm = confusion_matrix(all_true, all_pred, labels=classes)
    print("  confusion (rows=true, cols=pred):")
    print("    " + " ".join(f"{c:>8}" for c in classes))
    for i, c in enumerate(classes):
        print(f"    {c:>5} " + " ".join(f"{v:>8}" for v in cm[i]))
    return {"mean_acc": float(np.mean(accs)), "std_acc": float(np.std(accs)),
            "classes": classes, "confusion": cm.tolist()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("analyze/model.joblib"))
    ap.add_argument("--line-hz", type=float, default=60.0)
    ap.add_argument("--reject-uv", type=float, default=200.0,
                    help="drop epochs with peak-to-peak above this on any channel")
    args = ap.parse_args()

    print(f"Loading {len(args.csvs)} files (artifact threshold {args.reject_uv} µV p2p)...")
    fs = build_features(args.csvs, line_hz=args.line_hz, reject_threshold_uv=args.reject_uv)
    print(f"\nTotal: {fs.X.shape[0]} clean epochs across {len(set(fs.source))} files, "
          f"{fs.X.shape[1]} features")

    groups = np.array(fs.source)
    y = fs.y
    X = fs.X

    results = {}
    results["multiclass"] = _evaluate(X, y, groups, f"{len(set(y))}-class: " + " vs ".join(sorted(set(y))))

    if {"calm", "happy", "sad"}.issubset(set(y)):
        y_arousal = np.where(y == "calm", "calm", "music")
        results["arousal"] = _evaluate(X, y_arousal, groups, "arousal: calm vs music")

        m = (y == "happy") | (y == "sad")
        results["valence"] = _evaluate(X[m], y[m], groups[m], "valence: happy vs sad")

    pipe = _make_pipe()
    pipe.fit(X, y)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "feature_names": fs.feature_names,
                 "classes": sorted(set(y)), "line_hz": args.line_hz}, args.out)
    args.out.with_suffix(".json").write_text(json.dumps(results, indent=2))
    print(f"\nSaved model to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
