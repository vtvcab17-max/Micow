"""Suy luận mạng nơ-ron của Micow Ear bằng numpy thuần (không cần PyTorch khi dùng).

Hai mạng nhỏ, trọng số trong `micow/ear/weights/*.npz` (huấn luyện bằng `micow train ear`):
  * BeatTCN – mạng tích chập giãn (TCN) trên đặc trưng từng khung → xác suất phách / đầu ô nhịp.
  * BarMLP  – mạng nhiều lớp trên đặc trưng từng ô nhịp (kèm ngữ cảnh ±4 ô) → hook / peak / loại đoạn.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

WEIGHTS = Path(__file__).resolve().parent / "weights"
KINDS = ["intro", "verse", "prechorus", "chorus", "postchorus", "bridge", "drop", "break", "instrumental", "outro"]


def _elu(x):
    return np.where(x > 0, x, np.expm1(np.minimum(x, 0)))


def _sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -60, 60)))


def conv1d(x: np.ndarray, w: np.ndarray, b: np.ndarray, dil: int = 1) -> np.ndarray:
    """x (C_in, T), w (C_out, C_in, K) – padding 'same'."""
    K = w.shape[2]
    pad = dil * (K - 1) // 2
    xp = np.pad(x, ((0, 0), (pad, pad)))
    T = x.shape[1]
    y = np.zeros((w.shape[0], T), np.float32)
    for k in range(K):
        y += w[:, :, k] @ xp[:, k * dil: k * dil + T]
    return y + b[:, None]


class BeatTCN:
    def __init__(self, path: Path):
        d = np.load(path)
        self.p = {k: d[k].astype(np.float32) for k in d.files}
        self.dils = [int(v) for v in self.p["dils"]]
        self.mean, self.std = self.p["mean"], self.p["std"]

    def __call__(self, feats: np.ndarray) -> np.ndarray:
        """feats (T, F) → (T, 2) xác suất [phách, đầu ô nhịp]."""
        x = ((feats - self.mean) / self.std).T.astype(np.float32)
        h = _elu(conv1d(x, self.p["in_w"], self.p["in_b"]))
        for i, d in enumerate(self.dils):
            h = h + _elu(conv1d(h, self.p[f"b{i}_w"], self.p[f"b{i}_b"], d))
        return _sigmoid(conv1d(h, self.p["out_w"], self.p["out_b"])).T


class BarMLP:
    def __init__(self, path: Path):
        d = np.load(path)
        self.p = {k: d[k].astype(np.float32) for k in d.files if d[k].dtype.kind in "fiu"}
        self.feat_names = [str(x) for x in d["feat_names"]] if "feat_names" in d.files else []
        self.ctx = int(self.p["ctx"])
        self.mean, self.std = self.p["mean"], self.p["std"]

    def __call__(self, bar_feats: np.ndarray) -> dict:
        x = context_stack(bar_feats, self.ctx)
        x = (x - self.mean) / self.std
        h = _elu(x @ self.p["w1"] + self.p["b1"])
        h = _elu(h @ self.p["w2"] + self.p["b2"])
        o = h @ self.p["w3"] + self.p["b3"]
        logits = o[:, 2:]
        e = np.exp(logits - logits.max(axis=1, keepdims=True))
        return {"hook": _sigmoid(o[:, 0]), "peak": _sigmoid(o[:, 1]), "kind": e / e.sum(axis=1, keepdims=True)}


def context_stack(f: np.ndarray, ctx: int) -> np.ndarray:
    """(n, F) → (n, (2ctx+1)·F): ghép đặc trưng các ô nhịp lân cận (đệm bằng mép)."""
    n = len(f)
    idx = np.clip(np.arange(n)[:, None] + np.arange(-ctx, ctx + 1)[None, :], 0, max(0, n - 1))
    return f[idx].reshape(n, -1)


@lru_cache(maxsize=2)
def beat_model() -> BeatTCN | None:
    p = WEIGHTS / "beat_tcn.npz"
    return BeatTCN(p) if p.exists() else None


@lru_cache(maxsize=2)
def bar_model() -> BarMLP | None:
    p = WEIGHTS / "bar_mlp.npz"
    return BarMLP(p) if p.exists() else None
