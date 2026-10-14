"""Bộ lọc và hiệu ứng (vector hoá bằng numpy/scipy, không vòng lặp từng mẫu)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.signal import butter, lfilter, oaconvolve, sosfilt

from ..audio_io import SR


@lru_cache(maxsize=512)
def _sos(kind: str, f1: float, f2: float = 0.0, order: int = 2):
    nyq = SR / 2 - 100
    if kind == "band":
        lo, hi = max(20.0, min(f1, nyq - 10)), max(30.0, min(f2, nyq))
        if hi <= lo:
            hi = min(nyq, lo * 1.2)
        return butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    return butter(order, max(20.0, min(f1, nyq)), kind, fs=SR, output="sos")


def lp(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return sosfilt(_sos("lowpass", round(fc, 1), 0, order), x, axis=0).astype(np.float32)


def hp(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return sosfilt(_sos("highpass", round(fc, 1), 0, order), x, axis=0).astype(np.float32)


def bp(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return sosfilt(_sos("band", round(lo, 1), round(hi, 1), order), x, axis=0).astype(np.float32)


def formant(x: np.ndarray, fc: float, bw: float) -> np.ndarray:
    return bp(x, fc - bw / 2, fc + bw / 2, 1)


def one_pole(x: np.ndarray, coef: float) -> np.ndarray:
    return lfilter([1 - coef], [1, -coef], x, axis=0).astype(np.float32)


def sweep_lp(x: np.ndarray, env: np.ndarray, f_lo: float, f_hi: float) -> np.ndarray:
    """"Quét lọc" rẻ: trộn bản lọc tối và sáng theo đường bao 0..1 (thay cho lọc biến thiên theo mẫu)."""
    dark = lp(x, f_lo)
    bright = lp(x, f_hi) if f_hi < SR / 2 - 200 else x
    e = np.clip(env, 0, 1)
    if x.ndim == 2:
        e = e[:, None]
    return (dark + (bright - dark) * e).astype(np.float32)


def saturate(x: np.ndarray, drive: float = 1.5) -> np.ndarray:
    return (np.tanh(drive * x) / np.tanh(drive)).astype(np.float32)


def bitcrush(x: np.ndarray, bits: int = 10, down: int = 2) -> np.ndarray:
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    if down > 1:
        idx = (np.arange(len(y)) // down) * down
        y = y[idx]
    return y.astype(np.float32)


def pan(x: np.ndarray, p: float) -> np.ndarray:
    """Mono → stereo, p ∈ [-1, 1], luật công suất không đổi."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1).astype(np.float32)


def widen(x: np.ndarray, ms: float = 12.0) -> np.ndarray:
    """Haas: trễ kênh phải vài ms để lớp pad/dây rộng ra."""
    d = int(SR * ms / 1000)
    st = x if x.ndim == 2 else np.stack([x, x], axis=1)
    out = st.copy()
    out[d:, 1] = st[:-d, 1]
    return out


@lru_cache(maxsize=8)
def _reverb_ir(size: float, damp: float, seed: int = 7) -> np.ndarray:
    """Đáp ứng xung phòng nhân tạo: nhiễu suy giảm theo dải tần + phản xạ sớm. Trả (n, 2)."""
    rng = np.random.default_rng(seed)
    t60 = 0.6 + 3.2 * size
    n = int(SR * min(4.5, t60 * 1.1))
    t = np.arange(n) / SR
    out = np.zeros((n, 2), dtype=np.float32)
    for ch in range(2):
        noise = rng.standard_normal(n).astype(np.float32)
        lo = lp(noise, 600)
        mid = bp(noise, 600, 4000)
        hi = hp(noise, 4000)
        dec = lambda tt: np.exp(-6.91 * t / tt)
        y = lo * dec(t60) + mid * dec(t60 * (1 - 0.35 * damp)) + hi * dec(t60 * (1 - 0.75 * damp)) * 0.6
        pre = int(SR * (0.012 + 0.008 * size))
        y = np.concatenate([np.zeros(pre, np.float32), y[:-pre]])
        for k in range(6):  # phản xạ sớm
            d = int(SR * rng.uniform(0.004, 0.035))
            y[d] += rng.uniform(0.2, 0.5) * (1 if rng.random() > 0.5 else -1)
        out[:, ch] = y
    out /= np.sqrt((out ** 2).sum(axis=0, keepdims=True)) + 1e-9
    return out


def reverb(x: np.ndarray, size: float = 0.5, damp: float = 0.5, wet: float = 0.25) -> np.ndarray:
    if wet <= 0:
        return x
    st = x if x.ndim == 2 else np.stack([x, x], axis=1)
    ir = _reverb_ir(round(size, 2), round(damp, 2))
    src = hp(st, 180)
    w = np.stack([oaconvolve(src[:, c], ir[:, c])[: len(st)] for c in range(2)], axis=1)
    return (st + wet * w * 0.9).astype(np.float32)


def delay(x: np.ndarray, seconds: float, feedback: float = 0.35, wet: float = 0.2, pingpong: bool = True) -> np.ndarray:
    st = x if x.ndim == 2 else np.stack([x, x], axis=1)
    d = int(seconds * SR)
    if d <= 0 or wet <= 0:
        return st
    wetsig = np.zeros_like(st)
    src = lp(hp(st.mean(axis=1), 300), 5000)
    k, g = 1, feedback
    while g > 0.02 and k * d < len(st):
        ch = (k % 2) if pingpong else None
        seg = src[: len(st) - k * d] * g
        if ch is None:
            wetsig[k * d:, 0] += seg
            wetsig[k * d:, 1] += seg
        else:
            wetsig[k * d:, ch] += seg * 1.3
            wetsig[k * d:, 1 - ch] += seg * 0.4
        k += 1
        g *= feedback
    return (st + wet * wetsig).astype(np.float32)


def envelope_follow(x: np.ndarray, attack_ms: float = 5, release_ms: float = 120) -> np.ndarray:
    m = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    m = maximum_filter1d(m, size=max(1, int(SR * attack_ms / 1000)))
    coef = np.exp(-1.0 / (SR * release_ms / 1000))
    return lfilter([1 - coef], [1, -coef], m).astype(np.float32)


def compress(x: np.ndarray, thresh_db: float = -14, ratio: float = 2.5, attack_ms: float = 8,
             release_ms: float = 150, makeup_db: float = 0.0) -> np.ndarray:
    env = envelope_follow(x, attack_ms, release_ms)
    lvl = 20 * np.log10(np.maximum(env, 1e-6))
    over = np.maximum(0.0, lvl - thresh_db)
    gain_db = -over * (1 - 1 / ratio) + makeup_db
    g = (10 ** (gain_db / 20)).astype(np.float32)
    return x * (g[:, None] if x.ndim == 2 else g)


def sidechain_curve(n: int, hits_s: list[float], depth: float = 0.5, release_s: float = 0.18) -> np.ndarray:
    g = np.ones(n, dtype=np.float32)
    if depth <= 0:
        return g
    rel = int(release_s * SR)
    att = int(0.004 * SR)
    shape = np.concatenate([np.linspace(1, 1 - depth, att), 1 - depth * (1 - (np.linspace(0, 1, rel) ** 1.6))])
    for t in hits_s:
        i = int(t * SR)
        if i >= n:
            continue
        j = min(n, i + len(shape))
        g[i:j] = np.minimum(g[i:j], shape[: j - i])
    return g


def fade(x: np.ndarray, fin: float = 0.0, fout: float = 0.0) -> np.ndarray:
    y = x.copy()
    n = len(y)
    if fin > 0:
        k = min(n, int(fin * SR))
        r = np.linspace(0, 1, k) ** 2
        y[:k] *= r[:, None] if y.ndim == 2 else r
    if fout > 0:
        k = min(n, int(fout * SR))
        r = np.linspace(1, 0, k) ** 2
        y[n - k:] *= r[:, None] if y.ndim == 2 else r
    return y


def vinyl(n: int, amount: float = 0.5, seed: int = 0) -> np.ndarray:
    """Tiếng đĩa than: lách tách + xì nhẹ."""
    rng = np.random.default_rng(seed + 99)
    hiss = lp(hp(rng.standard_normal(n).astype(np.float32), 2000), 9000) * 0.012
    crack = np.zeros(n, dtype=np.float32)
    k = int(n / SR * 9 * amount)
    pos = rng.integers(0, n, size=k)
    crack[pos] = rng.uniform(0.15, 0.6, size=k) * rng.choice([-1, 1], size=k)
    crack = bp(crack, 1200, 9000) * 1.5
    mono = (hiss + crack) * amount
    return np.stack([mono, np.roll(mono, 37)], axis=1)


# ---------------- co giãn thời gian / đổi cao độ ----------------
def stretch_pv(x: np.ndarray, ratio: float, n_fft: int = 2048, hop: int = 512) -> np.ndarray:
    """Phase vocoder: ratio > 1 làm dài ra (chậm lại) mà giữ cao độ. x mono."""
    if abs(ratio - 1) < 1e-3:
        return x.astype(np.float32)
    win = np.hanning(n_fft).astype(np.float32)
    pad = np.concatenate([np.zeros(n_fft, np.float32), x.astype(np.float32), np.zeros(n_fft, np.float32)])
    nfr = 1 + (len(pad) - n_fft) // hop
    frames = np.lib.stride_tricks.as_strided(pad, (nfr, n_fft), (pad.strides[0] * hop, pad.strides[0]))
    S = np.fft.rfft(frames * win, axis=1)
    steps = np.arange(0, nfr - 1, 1.0 / ratio)
    mag0 = np.abs(S)
    ph = np.angle(S)
    omega = 2 * np.pi * hop * np.arange(n_fft // 2 + 1) / n_fft
    out = np.zeros(int(len(steps) * hop + n_fft), dtype=np.float32)
    wsum = np.zeros_like(out)
    acc = ph[0].copy()
    for k, st in enumerate(steps):
        i = int(st)
        fr = st - i
        mag = (1 - fr) * mag0[i] + fr * mag0[i + 1]
        dphi = ph[i + 1] - ph[i] - omega
        dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))
        frame = np.fft.irfft(mag * np.exp(1j * acc), n_fft).astype(np.float32) * win
        out[k * hop: k * hop + n_fft] += frame
        wsum[k * hop: k * hop + n_fft] += win ** 2
        acc += omega + dphi
    out = out / np.maximum(wsum, 1e-3)
    return out[n_fft: n_fft + int(len(x) * ratio)].astype(np.float32)


def resample_ratio(x: np.ndarray, ratio: float) -> np.ndarray:
    """Đổi tốc độ phát (đổi cả cao độ). ratio > 1 → dài hơn, trầm hơn."""
    n = int(len(x) * ratio)
    idx = np.linspace(0, len(x) - 1, n)
    if x.ndim == 2:
        return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], 1).astype(np.float32)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def pitch_shift(x: np.ndarray, semitones: float) -> np.ndarray:
    if abs(semitones) < 0.01:
        return x
    r = 2 ** (semitones / 12)
    y = stretch_pv(x, r)
    return resample_ratio(y, 1 / r)[: len(x)]
