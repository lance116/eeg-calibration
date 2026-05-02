"""Bandpower feature extraction for BrainBit recordings.

Reads CSVs produced by `eegcli stream --label X --out ...` and turns them into
fixed-length epochs with one feature vector each. Features per epoch:

  - log-bandpower per (channel, band): 4 channels x 5 bands = 20
  - left/right asymmetry per band on (T3,T4) and (O1,O2): 5 + 5 = 10
  - Hjorth mobility per channel: 4

= 34 features per epoch.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, iirnotch, welch


SAMPLE_RATE_HZ = 250
CHANNELS = ("O1", "O2", "T3", "T4")
BANDS = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta":  (13.0, 30.0),
    "gamma": (30.0, 45.0),
}
EPOCH_SEC = 4.0
EPOCH_STRIDE_SEC = 2.0


@dataclass
class FeatureSet:
    X: np.ndarray          # (n_epochs, n_features)
    y: np.ndarray          # (n_epochs,) string labels
    feature_names: list[str]
    source: list[str]      # per-epoch source filename


def _design_filters(line_hz: float) -> tuple:
    nyq = SAMPLE_RATE_HZ / 2
    bp_b, bp_a = butter(4, [1.0 / nyq, 45.0 / nyq], btype="band")
    nt_b, nt_a = iirnotch(line_hz / nyq, Q=30)
    return (bp_b, bp_a), (nt_b, nt_a)


def _filter(x: np.ndarray, line_hz: float) -> np.ndarray:
    (bp_b, bp_a), (nt_b, nt_a) = _design_filters(line_hz)
    y = filtfilt(bp_b, bp_a, x, axis=0)
    y = filtfilt(nt_b, nt_a, y, axis=0)
    return y


def _bandpower(epoch: np.ndarray) -> np.ndarray:
    """Welch PSD → integrated power per band per channel. Returns (n_chan, n_bands)."""
    f, p = welch(epoch, fs=SAMPLE_RATE_HZ, nperseg=min(len(epoch), 256), axis=0)
    out = np.zeros((epoch.shape[1], len(BANDS)))
    for j, (lo, hi) in enumerate(BANDS.values()):
        mask = (f >= lo) & (f < hi)
        out[:, j] = np.trapz(p[mask], f[mask], axis=0)
    return out


def _hjorth_mobility(epoch: np.ndarray) -> np.ndarray:
    var0 = np.var(epoch, axis=0) + 1e-12
    d1 = np.diff(epoch, axis=0)
    var1 = np.var(d1, axis=0) + 1e-12
    return np.sqrt(var1 / var0)


def _features_for_epoch(epoch: np.ndarray) -> np.ndarray:
    bp = _bandpower(epoch)                       # (4, 5)
    log_bp = np.log(bp + 1e-12).flatten()        # 20

    o_idx = [CHANNELS.index("O1"), CHANNELS.index("O2")]
    t_idx = [CHANNELS.index("T3"), CHANNELS.index("T4")]
    asym_o = np.log((bp[o_idx[1]] + 1e-12) / (bp[o_idx[0]] + 1e-12))   # 5
    asym_t = np.log((bp[t_idx[1]] + 1e-12) / (bp[t_idx[0]] + 1e-12))   # 5

    mob = _hjorth_mobility(epoch)                # 4

    return np.concatenate([log_bp, asym_o, asym_t, mob])


def feature_names() -> list[str]:
    names: list[str] = []
    for c in CHANNELS:
        for b in BANDS: names.append(f"logbp_{c}_{b}")
    for b in BANDS: names.append(f"asym_O2_O1_{b}")
    for b in BANDS: names.append(f"asym_T4_T3_{b}")
    for c in CHANNELS: names.append(f"hjorth_mob_{c}")
    return names


def load_csv(path: Path, line_hz: float = 60.0) -> tuple[np.ndarray, str | None]:
    """Return (signal_uV [n_samples, 4], label_or_None)."""
    df = pd.read_csv(path)
    sig = df[list(CHANNELS)].to_numpy().astype(np.float64) if all(c in df for c in CHANNELS) \
        else df[[f"{c}_uV" for c in CHANNELS]].to_numpy().astype(np.float64)
    label = None
    if "label" in df.columns:
        labels = df["label"].dropna().unique()
        if len(labels) == 1:
            label = str(labels[0])
        elif len(labels) > 1:
            raise ValueError(f"{path}: multiple labels in one file: {labels}")
    return _filter(sig, line_hz), label


def epoch(signal: np.ndarray) -> np.ndarray:
    """Slice a filtered signal into overlapping epochs. Returns (n_epochs, n_samples_per_epoch, n_chan)."""
    n = int(EPOCH_SEC * SAMPLE_RATE_HZ)
    stride = int(EPOCH_STRIDE_SEC * SAMPLE_RATE_HZ)
    if signal.shape[0] < n:
        return np.empty((0, n, signal.shape[1]))
    starts = range(0, signal.shape[0] - n + 1, stride)
    return np.stack([signal[s:s + n] for s in starts], axis=0)


def build_features(csv_paths: list[Path], line_hz: float = 60.0,
                   label_override: str | None = None) -> FeatureSet:
    all_X, all_y, all_src = [], [], []
    for p in csv_paths:
        sig, file_label = load_csv(p, line_hz=line_hz)
        label = label_override or file_label
        if label is None:
            raise ValueError(f"{p}: no label column and no --label override")
        epochs = epoch(sig)
        if epochs.shape[0] == 0:
            print(f"  {p.name}: too short, skipping")
            continue
        feats = np.stack([_features_for_epoch(e) for e in epochs], axis=0)
        all_X.append(feats); all_y.extend([label] * feats.shape[0]); all_src.extend([p.name] * feats.shape[0])
        print(f"  {p.name}: {feats.shape[0]} epochs, label={label}")
    if not all_X:
        raise ValueError("no usable epochs in input files")
    return FeatureSet(
        X=np.vstack(all_X),
        y=np.array(all_y),
        feature_names=feature_names(),
        source=all_src,
    )
