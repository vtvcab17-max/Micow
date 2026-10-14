"""Hậu kỳ: cân stem, bus compressor, đo loudness ITU-R BS.1770 (LUFS), limiter, chuẩn -14 LUFS."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.signal import lfilter

from ..audio_io import SR
from . import fx


def _biquad_shelf(fs: float):
    # K-weighting giai đoạn 1 (high-shelf +4 dB @ ~1681 Hz) – công thức của pyloudnorm / BS.1770
    G, Q, fc = 3.99984385397, 0.7071752369554193, 1681.974450955533
    A = 10 ** (G / 40.0)
    w0 = 2.0 * np.pi * (fc / fs)
    alpha = np.sin(w0) / (2.0 * Q)
    b = [A * ((A + 1) + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha),
         -2 * A * ((A - 1) + (A + 1) * np.cos(w0)),
         A * ((A + 1) + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)]
    a = [(A + 1) - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha,
         2 * ((A - 1) - (A + 1) * np.cos(w0)),
         (A + 1) - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def _biquad_hp(fs: float):
    G, Q, fc = 0.0, 0.5003270373253953, 38.13547087613982
    w0 = 2.0 * np.pi * (fc / fs)
    alpha = np.sin(w0) / (2.0 * Q)
    b = [(1 + np.cos(w0)) / 2, -(1 + np.cos(w0)), (1 + np.cos(w0)) / 2]
    a = [1 + alpha, -2 * np.cos(w0), 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def lufs(x: np.ndarray, sr: int = SR) -> float:
    """Loudness tích hợp (LUFS) theo BS.1770-4 với cổng tuyệt đối -70 và tương đối -10."""
    st = x if x.ndim == 2 else x[:, None]
    b1, a1 = _biquad_shelf(sr)
    b2, a2 = _biquad_hp(sr)
    y = lfilter(b2, a2, lfilter(b1, a1, st, axis=0), axis=0)
    T, step = int(0.4 * sr), int(0.1 * sr)
    if len(y) < T:
        return -70.0
    sq = y ** 2
    cs = np.concatenate([np.zeros((1, sq.shape[1])), np.cumsum(sq, axis=0)])
    starts = np.arange(0, len(y) - T + 1, step)
    z = (cs[starts + T] - cs[starts]) / T          # (blocks, ch)
    l = -0.691 + 10 * np.log10(z.sum(axis=1) + 1e-12)
    g = l > -70
    if not g.any():
        return -70.0
    rel = -0.691 + 10 * np.log10(z[g].sum(axis=1).mean() + 1e-12) - 10
    g2 = g & (l > rel)
    if not g2.any():
        return -70.0
    return float(-0.691 + 10 * np.log10(z[g2].sum(axis=1).mean() + 1e-12))


def limiter(x: np.ndarray, ceiling_db: float = -1.0, release_ms: float = 80, look_ms: float = 3) -> np.ndarray:
    ceil = 10 ** (ceiling_db / 20)
    peak = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    w = max(1, int(SR * look_ms / 1000))
    peak = maximum_filter1d(peak, size=2 * w + 1)
    g = np.minimum(1.0, ceil / np.maximum(peak, 1e-9))
    # nhả chậm: làm mượt (1-g) bằng lọc một cực, lấy max với g tức thời để không vượt trần
    coef = np.exp(-1.0 / (SR * release_ms / 1000))
    red = lfilter([1 - coef], [1, -coef], 1 - g)
    red = np.maximum(red, 1 - g)
    gain = (1 - red).astype(np.float32)
    y = x * (gain[:, None] if x.ndim == 2 else gain)
    return np.clip(y, -ceil, ceil).astype(np.float32)


def rms_db(x: np.ndarray) -> float:
    m = x.mean(axis=1) if x.ndim == 2 else x
    act = np.abs(m) > 1e-4
    if act.sum() < SR * 0.1:
        return -120.0
    return float(10 * np.log10(np.mean(m[act] ** 2) + 1e-12))


# mức RMS mục tiêu tương đối cho từng stem (dB) – điểm khởi đầu của một bản mix cân
STEM_LEVEL = {"drums": -15.5, "bass": -17.0, "chords": -21.0, "lead": -22.5, "vocal": -16.5,
              "sample": -19.0, "fx": -26.0, "vinyl": -36.0}


def balance(stems: dict[str, np.ndarray], genre: str = "") -> dict[str, np.ndarray]:
    out = {}
    for name, x in stems.items():
        cur = rms_db(x)
        if cur < -100:
            out[name] = x
            continue
        tgt = STEM_LEVEL.get(name, -20.0)
        if genre in ("trap", "edm", "vinahouse", "house") and name == "bass":
            tgt += 1.5
        if genre in ("ballad", "bolero", "cinematic") and name == "drums":
            tgt -= 3.0
        out[name] = (x * 10 ** ((tgt - cur) / 20)).astype(np.float32)
    return out


def master(mix: np.ndarray, genre: str = "", target_lufs: float = -14.0, ceiling_db: float = -1.0) -> tuple[np.ndarray, dict]:
    y = fx.hp(mix, 28)
    if genre == "lofi":
        y = fx.lp(y, 11000)
        y = fx.saturate(y * 1.1, 1.2)
    y = fx.compress(y, thresh_db=-16, ratio=2.0, attack_ms=12, release_ms=180)
    for _ in range(3):
        L = lufs(y)
        y = y * 10 ** ((target_lufs - L) / 20)
        y = limiter(y, ceiling_db)
    L = lufs(y)
    peak = float(np.abs(y).max())
    return y.astype(np.float32), {"lufs": round(L, 2), "peak_db": round(20 * np.log10(peak + 1e-12), 2)}
