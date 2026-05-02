"""Train a logistic-regression emotion classifier on labeled BrainBit recordings.

  python -m analyze.train data/happy_*.csv data/calm_*.csv data/sad_*.csv \\
    --out analyze/model.joblib

Splits epochs by source file to avoid leakage (epochs from the same recording
are highly correlated, so randomly splitting epochs over-reports accuracy).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import build_features


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+", type=Path, help="labeled CSVs from `eegcli stream --label X`")
    ap.add_argument("--out", type=Path, default=Path("analyze/model.joblib"))
    ap.add_argument("--line-hz", type=float, default=60.0, help="line-noise notch (60 US, 50 EU)")
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    print(f"Loading {len(args.csvs)} files...")
    fs = build_features(args.csvs, line_hz=args.line_hz)
    print(f"\nTotal: {fs.X.shape[0]} epochs across {len(set(fs.source))} files, "
          f"{fs.X.shape[1]} features, classes={sorted(set(fs.y))}")

    groups = np.array(fs.source)
    n_groups = len(set(groups))
    n_folds = min(args.folds, n_groups)
    if n_folds < 2:
        print("Need recordings from at least 2 different files per class; aborting CV.")
        return 1

    pipe = Pipeline([
        ("scale", StandardScaler()),
        ("clf",   LogisticRegression(max_iter=2000, C=1.0, multi_class="auto")),
    ])

    print(f"\nGroupKFold cross-validation ({n_folds} folds, grouped by source file):")
    cv = GroupKFold(n_splits=n_folds)
    accs, all_true, all_pred = [], [], []
    for k, (tr, te) in enumerate(cv.split(fs.X, fs.y, groups)):
        pipe.fit(fs.X[tr], fs.y[tr])
        pred = pipe.predict(fs.X[te])
        acc = (pred == fs.y[te]).mean()
        held_out = sorted(set(groups[te]))
        print(f"  fold {k+1}: acc={acc:.3f}  held_out={held_out}")
        accs.append(acc); all_true.extend(fs.y[te]); all_pred.extend(pred)

    print(f"\nMean CV accuracy: {np.mean(accs):.3f} ± {np.std(accs):.3f}  (chance={1/len(set(fs.y)):.3f})")
    print("\nConfusion matrix (rows=true, cols=pred):")
    classes = sorted(set(fs.y))
    cm = confusion_matrix(all_true, all_pred, labels=classes)
    print("       " + "  ".join(f"{c:>8}" for c in classes))
    for i, c in enumerate(classes):
        print(f"  {c:>5}  " + "  ".join(f"{v:>8}" for v in cm[i]))
    print()
    print(classification_report(all_true, all_pred, digits=3))

    pipe.fit(fs.X, fs.y)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "feature_names": fs.feature_names,
                 "classes": classes, "line_hz": args.line_hz}, args.out)
    meta = {"cv_mean_acc": float(np.mean(accs)), "cv_std_acc": float(np.std(accs)),
            "classes": classes, "n_epochs": int(fs.X.shape[0])}
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"Saved model to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
