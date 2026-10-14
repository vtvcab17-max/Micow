"""Bộ tổng hợp âm thanh của Micow Beat: trống, bass, phím, dây, guitar, sáo, đàn tranh, giọng mẫu.

Tất cả là thuật toán (FM, cộng hài âm, Karplus–Strong, lọc formant…), không dùng mẫu âm thanh có bản quyền.
Mỗi hàm trả mảng mono float32 ở SR = 44100.
"""
from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np

from ..audio_io import SR
from ..theory import midi_to_hz
from . import fx

TAIL = 0.35  # giây ngân thêm sau khi nhả phím


def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float32) / SR


def _n(sec: float) -> int:
    return max(1, int(sec * SR))


def _rng(*key) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(repr(key).encode()))


def adsr(n: int, a: float, d: float, s: float, r: float, gate: int | None = None) -> np.ndarray:
    gate = n if gate is None else min(gate, n)
    env = np.zeros(n, dtype=np.float32)
    na, nd = _n(a), _n(d)
    i = 0
    seg = np.linspace(0, 1, na, endpoint=False)[: gate]
    env[: len(seg)] = seg
    i = len(seg)
    if i < gate:
        seg = 1 - (1 - s) * (1 - np.exp(-5 * np.arange(min(nd * 3, gate - i)) / nd))
        env[i: i + len(seg)] = seg
        i += len(seg)
    if i < gate:
        env[i:gate] = s
    lvl = env[gate - 1] if gate > 0 else 0
    if gate < n:
        nr = n - gate
        env[gate:] = lvl * np.exp(-5 * np.arange(nr) / max(1, _n(r)))
    return env


def phase_of(freq) -> np.ndarray:
    return np.cumsum(np.asarray(freq, dtype=np.float64) / SR) % 1.0


def sine(freq, n: int | None = None) -> np.ndarray:
    f = np.full(n, freq) if np.isscalar(freq) else freq
    return np.sin(2 * np.pi * phase_of(f)).astype(np.float32)


def saw(freq, n: int | None = None, phase0: float = 0.0) -> np.ndarray:
    """Răng cưa khử răng cưa phổ bằng polyBLEP."""
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=np.float64)
    dt = np.clip(f / SR, 1e-6, 0.5)
    ph = (phase0 + np.cumsum(dt)) % 1.0
    y = 2 * ph - 1
    m1 = ph < dt
    x = ph[m1] / dt[m1]
    y[m1] -= x + x - x * x - 1
    m2 = ph > 1 - dt
    x = (ph[m2] - 1) / dt[m2]
    y[m2] -= x * x + x + x + 1
    return y.astype(np.float32)


def square(freq, n: int | None = None, width: float = 0.5) -> np.ndarray:
    return (saw(freq, n) - saw(freq, n, width)) * 0.5


def noise(n: int, seed=0) -> np.ndarray:
    return _rng("noise", seed, n).standard_normal(n).astype(np.float32)


# =============================== TRỐNG ===============================
@lru_cache(maxsize=64)
def kick(kind: str = "pop", vel: float = 1.0) -> np.ndarray:
    dur = {"house": 0.42, "edm": 0.5, "vinahouse": 0.45, "boombap": 0.38, "lofi": 0.35, "cinematic": 0.9}.get(kind, 0.4)
    n = _n(dur)
    t = _t(n)
    f_top, f_end, pd = {"edm": (180, 48, 0.035), "vinahouse": (200, 50, 0.03), "house": (150, 50, 0.04),
                        "boombap": (130, 52, 0.03), "lofi": (110, 50, 0.03), "cinematic": (90, 32, 0.08)}.get(kind, (150, 48, 0.035))
    f = f_end + (f_top - f_end) * np.exp(-t / pd)
    body = sine(f) * np.exp(-t / (dur * 0.45))
    click = fx.hp(noise(n, 1), 2500) * np.exp(-t / 0.004) * 0.35
    y = fx.saturate((body + click) * 1.4, 1.6)
    if kind in ("lofi", "boombap"):
        y = fx.lp(y, 3500)
    return (y * vel).astype(np.float32)


@lru_cache(maxsize=256)
def kick808(freq: float, dur: float, vel: float = 1.0, glide_from: float = 0.0) -> np.ndarray:
    n = _n(dur + 0.08)
    t = _t(n)
    f = freq * (1 + 0.5 * np.exp(-t / 0.018))
    if glide_from:
        f = f * np.where(t < 0.07, (glide_from / freq) ** (1 - t / 0.07), 1.0)
    y = sine(f)
    amp = np.exp(-t / max(0.25, dur * 0.9))
    amp *= np.clip((dur + 0.06 - t) / 0.06, 0, 1)
    y = fx.saturate(y * amp * 1.8, 2.2)
    return (y * vel * 0.9).astype(np.float32)


@lru_cache(maxsize=64)
def snare(kind: str = "pop", vel: float = 1.0) -> np.ndarray:
    n = _n(0.35)
    t = _t(n)
    tone = (sine(np.full(n, 185.0)) * 0.6 + sine(np.full(n, 330.0)) * 0.3) * np.exp(-t / 0.05)
    nz = fx.bp(noise(n, 2), 1500, 9000) * np.exp(-t / (0.12 if kind not in ("lofi", "boombap") else 0.09))
    y = tone * 0.7 + nz * 1.1
    if kind in ("lofi", "boombap"):
        y = fx.lp(y, 5000)
    if kind == "cinematic":
        y = fx.reverb(y, 0.8, 0.4, 0.5)[:, 0]
    return fx.saturate(y * vel, 1.3)


@lru_cache(maxsize=32)
def clap(vel: float = 1.0) -> np.ndarray:
    n = _n(0.4)
    t = _t(n)
    nz = fx.bp(noise(n, 3), 900, 3200)
    env = np.zeros(n, dtype=np.float32)
    for d in (0.0, 0.011, 0.022):
        k = _n(d)
        env[k:] += np.exp(-(t[: n - k]) / 0.007)
    env += 0.6 * np.exp(-t / 0.13) * (t > 0.03)
    return (nz * env * 1.6 * vel).astype(np.float32)


@lru_cache(maxsize=32)
def hat(open_: bool = False, vel: float = 1.0, kind: str = "pop") -> np.ndarray:
    dur = 0.45 if open_ else 0.08
    n = _n(dur)
    t = _t(n)
    metal = sum(square(f * 3.0, n) for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)) / 6
    y = fx.hp(metal * 0.6 + noise(n, 4) * 0.5, 7000)
    y *= np.exp(-t / (0.16 if open_ else 0.022))
    if kind in ("lofi", "boombap"):
        y = fx.lp(y, 8000) * 0.8
    return (y * vel * 0.9).astype(np.float32)


@lru_cache(maxsize=16)
def rim(vel: float = 1.0) -> np.ndarray:
    n = _n(0.08)
    t = _t(n)
    y = fx.bp(noise(n, 5), 1500, 2600) * np.exp(-t / 0.01) * 1.2 + sine(np.full(n, 500.0)) * np.exp(-t / 0.012) * 0.6
    return (y * vel).astype(np.float32)


@lru_cache(maxsize=16)
def shaker(vel: float = 1.0) -> np.ndarray:
    n = _n(0.09)
    t = _t(n)
    env = np.minimum(1, t / 0.012) * np.exp(-t / 0.035)
    return (fx.bp(noise(n, 6), 5000, 12000) * env * 0.8 * vel).astype(np.float32)


@lru_cache(maxsize=32)
def tom(freq: float = 110.0, vel: float = 1.0, big: bool = False) -> np.ndarray:
    dur = 1.2 if big else 0.45
    n = _n(dur)
    t = _t(n)
    f = freq * (1 + 0.35 * np.exp(-t / 0.04))
    y = sine(f) * np.exp(-t / (dur * 0.35)) + fx.lp(noise(n, 7), 900) * np.exp(-t / 0.03) * 0.4
    if big:
        y = fx.saturate(y * 1.5, 1.4)
    return (y * vel).astype(np.float32)


@lru_cache(maxsize=16)
def conga(high: bool = False, vel: float = 1.0) -> np.ndarray:
    n = _n(0.3)
    t = _t(n)
    f = (330.0 if high else 220.0) * (1 + 0.15 * np.exp(-t / 0.01))
    y = sine(f) * np.exp(-t / 0.09) + fx.bp(noise(n, 8), 1000, 4000) * np.exp(-t / 0.006) * 0.4
    return (y * vel * 0.8).astype(np.float32)


@lru_cache(maxsize=8)
def crash(vel: float = 1.0) -> np.ndarray:
    n = _n(2.2)
    t = _t(n)
    metal = sum(square(f * 4.1, n) for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)) / 6
    y = fx.hp(metal * 0.4 + noise(n, 9) * 0.6, 4000) * np.exp(-t / 0.7)
    return (y * vel * 0.55).astype(np.float32)


def riser(sec: float) -> np.ndarray:
    n = _n(sec)
    t = _t(n)
    ramp = (t / sec) ** 2
    nz = fx.sweep_lp(noise(n, 10), ramp, 400, 12000) * ramp
    tone = saw(220 * 2 ** (2 * t / sec), n) * ramp * 0.15
    return (nz * 0.5 + fx.lp(tone, 3000)).astype(np.float32)


def impact() -> np.ndarray:
    n = _n(2.5)
    t = _t(n)
    boom = sine(40 + 60 * np.exp(-t / 0.08)) * np.exp(-t / 0.6)
    nz = fx.lp(noise(n, 11), 3000) * np.exp(-t / 0.4) * 0.4
    return fx.saturate(boom + nz, 1.2)


# =============================== BASS ===============================
def bass_note(kind: str, midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(dur + 0.12)
    t = _t(n)
    gate = _n(dur)
    if kind == "sub":
        y = sine(np.full(n, f)) + 0.15 * sine(np.full(n, 2 * f))
        y *= adsr(n, 0.01, 0.2, 0.9, 0.1, gate)
    elif kind == "soft":
        y = sine(np.full(n, f)) * 0.8 + fx.lp(saw(f, n), 500) * 0.35
        y *= adsr(n, 0.02, 0.4, 0.7, 0.15, gate)
    elif kind == "pluck_bass":
        y = karplus(f, dur + 0.1, bright=0.35, decay=0.995, seed=int(midi))[:n]
        y = fx.lp(y, 900) * 1.6
        y = np.pad(y, (0, max(0, n - len(y))))[:n] * adsr(n, 0.002, 0.3, 0.8, 0.08, gate)
    elif kind == "rolling":
        y = saw(f, n) * 0.6 + sine(np.full(n, f)) * 0.6
        env = np.exp(-t / 0.09)
        y = fx.sweep_lp(y, env, 250, 1800) * adsr(n, 0.002, 0.08, 0.5, 0.03, gate)
    else:  # synth
        y = saw(f, n) * 0.55 + square(f / 2, n) * 0.2 + sine(np.full(n, f)) * 0.5
        env = np.exp(-t / 0.18)
        y = fx.sweep_lp(y, env, 300, 1600) * adsr(n, 0.004, 0.25, 0.75, 0.06, gate)
    return fx.saturate(y * vel, 1.3)


# =============================== PHÍM / HOÀ ÂM ===============================
def epiano(midi: float, dur: float, vel: float = 0.8) -> np.ndarray:
    """Piano điện kiểu Rhodes bằng FM 2 toán tử."""
    f = midi_to_hz(midi)
    n = _n(dur + 1.0)
    t = _t(n)
    idx = (1.6 * vel + 0.3) * np.exp(-t / 0.4) + 0.25
    mod = np.sin(2 * np.pi * f * t) * idx
    tine = np.sin(2 * np.pi * f * 14.0 * t) * 0.6 * np.exp(-t / 0.015)
    y = np.sin(2 * np.pi * f * t + mod + tine)
    amp = np.exp(-t / (1.6 if midi < 72 else 0.9)) * adsr(n, 0.002, 0.1, 1, 0.25, _n(dur))
    return (y * amp * vel).astype(np.float32)


def piano(midi: float, dur: float, vel: float = 0.8) -> np.ndarray:
    """Piano cộng hài âm có độ lệch hài (inharmonicity) và suy giảm theo từng hài."""
    f = midi_to_hz(midi)
    n = _n(min(dur, 3.5) + 1.2)
    t = _t(n)
    B = 0.0004
    tau0 = 3.2 * (1.6 if midi < 55 else 1.0 if midi < 72 else 0.55)
    y = np.zeros(n, dtype=np.float32)
    nh = int(min(14, 9000 / f))
    bright = 0.6 + 0.4 * vel
    for k in range(1, nh + 1):
        fk = k * f * np.sqrt(1 + B * k * k)
        ak = (bright ** (k - 1)) / (k ** 1.05)
        y += ak * np.sin(2 * np.pi * fk * t + k) * np.exp(-t * (1 + 0.45 * k) / tau0)
    ham = fx.lp(noise(n, int(midi)), 1500) * np.exp(-t / 0.008) * 0.15
    y = (y + ham) * adsr(n, 0.001, 0.05, 1, 0.3, _n(dur))
    return (y * vel * 0.5).astype(np.float32)


def supersaw(midi: float, dur: float, vel: float = 0.8, voices: int = 7, detune: float = 0.18,
             attack: float = 0.01, cutoff: float = 6000, release: float = 0.25) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(dur + release + 0.05)
    rng = _rng("ss", midi, voices)
    y = np.zeros(n, dtype=np.float32)
    for i in range(voices):
        cents = (i - (voices - 1) / 2) / max(1, (voices - 1) / 2) * detune * 100
        y += saw(f * 2 ** (cents / 1200), n, rng.random())
    y /= np.sqrt(voices)
    y = fx.lp(y, cutoff)
    return (y * adsr(n, attack, 0.3, 0.85, release, _n(dur)) * vel * 0.5).astype(np.float32)


def pad(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    return supersaw(midi, dur, vel, voices=4, detune=0.08, attack=0.35, cutoff=1800 + 1500 * vel, release=0.6)


def strings(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(dur + 0.7)
    t = _t(n)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.3 * t) * np.clip((t - 0.3) / 0.4, 0, 1)
    rng = _rng("str", midi)
    y = sum(saw(f * vib * 2 ** (c / 1200), n, rng.random()) for c in (-9, -3, 4, 10)) / 2
    y = fx.lp(y, 3200)
    y = fx.hp(y, 150)
    return (y * adsr(n, 0.28, 0.4, 0.9, 0.55, _n(dur)) * vel * 0.45).astype(np.float32)


def organ(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(dur + 0.15)
    t = _t(n)
    y = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in ((0.5, 0.5), (1, 1), (2, 0.6), (3, 0.35), (4, 0.25), (6, 0.15)))
    y *= 1 + 0.08 * np.sin(2 * np.pi * 6.2 * t)
    return (y * adsr(n, 0.01, 0.05, 1, 0.08, _n(dur)) * vel * 0.25).astype(np.float32)


def pluck(midi: float, dur: float, vel: float = 0.8) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(min(dur, 1.2) + 0.3)
    t = _t(n)
    y = saw(f, n) * 0.6 + square(f * 1.005, n) * 0.4
    env = np.exp(-t / 0.09)
    y = fx.sweep_lp(y, env, 600, 7000)
    return (y * np.exp(-t / 0.32) * adsr(n, 0.002, 0.1, 1, 0.1, _n(dur)) * vel * 0.6).astype(np.float32)


def bell(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(2.2)
    t = _t(n)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t / 0.5)
    y = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / 0.9)
    return (y * vel * 0.4).astype(np.float32)


def karplus(f: float, dur: float, bright: float = 0.6, decay: float = 0.996, seed: int = 0) -> np.ndarray:
    """Dây gảy Karplus–Strong, xử lý theo khối dài bằng chu kỳ trễ (vector hoá)."""
    N = max(2, int(round(SR / f)))
    n = _n(dur + 0.2)
    rng = _rng("ks", seed, N)
    exc = rng.uniform(-1, 1, N).astype(np.float32)
    if bright < 1:
        exc = fx.lp(exc, 800 + 9000 * bright)
    out = np.zeros(n + N + 1, dtype=np.float32)
    out[:N] = exc
    g = decay * 0.5
    pos = N
    while pos < len(out):
        end = min(len(out), pos + N)
        L = end - pos
        prev = out[pos - N: pos - N + L]
        prev2 = out[pos - N - 1: pos - N - 1 + L] if pos - N - 1 >= 0 else np.concatenate([[0.0], out[pos - N: pos - N + L - 1]])
        out[pos:end] = g * (prev + prev2)
        pos = end
    return out[:n]


def guitar(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    f = midi_to_hz(midi)
    y = karplus(f, dur + 0.4, bright=0.35 + 0.4 * vel, decay=0.997, seed=int(midi * 7))
    n = len(y)
    body = fx.bp(y, 90, 5000) + 0.3 * fx.lp(y, 300)
    return (body * adsr(n, 0.001, 0.1, 1, 0.12, _n(dur + 0.25)) * vel * 0.8).astype(np.float32)


def zither(midi: float, dur: float, vel: float = 0.8) -> np.ndarray:
    """Đàn tranh: dây gảy sáng + luyến (nhấn lên rồi trả về) ở nửa sau nốt dài."""
    f = midi_to_hz(midi)
    y = karplus(f, dur + 0.5, bright=0.85, decay=0.9975, seed=int(midi * 13))
    n = len(y)
    t = _t(n)
    bend = np.zeros(n, dtype=np.float32)
    if dur > 0.35:
        t0 = dur * 0.45
        up = np.clip((t - t0) / 0.12, 0, 1) * np.clip((t0 + 0.4 - t) / 0.15, 0, 1)
        bend = 1.5 * up + 0.25 * np.sin(2 * np.pi * 5.5 * t) * (t > t0 + 0.4)
    rate = 2 ** (bend / 12)
    pos = np.cumsum(rate) - rate[0]
    pos = np.clip(pos, 0, n - 1)
    y = np.interp(pos, np.arange(n), y).astype(np.float32)
    return (fx.hp(y, 150) * adsr(n, 0.001, 0.1, 1, 0.2, _n(dur + 0.3)) * vel).astype(np.float32)


def flute(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    """Sáo trúc: sin + hài nhẹ + hơi thổi + rung (vibrato) chậm vào + vuốt cao độ lúc bắt đầu."""
    f0 = midi_to_hz(midi)
    n = _n(dur + 0.2)
    t = _t(n)
    scoop = 2 ** (-0.6 * np.exp(-t / 0.05) / 12)
    vib = 2 ** (0.28 * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.25) / 0.3, 0, 1) / 12)
    f = f0 * scoop * vib
    ph = 2 * np.pi * phase_of(f)
    y = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.07 * np.sin(3 * ph)
    breath = fx.bp(noise(n, int(midi)), f0 * 1.5, f0 * 5) * 0.12
    env = adsr(n, 0.07, 0.2, 0.85, 0.12, _n(dur))
    return ((y * 0.5 + breath) * env * vel).astype(np.float32)


def arp_note(midi: float, dur: float, vel: float = 0.7) -> np.ndarray:
    f = midi_to_hz(midi)
    n = _n(min(dur, 0.5) + 0.15)
    t = _t(n)
    y = square(f, n, 0.3) * 0.5 + saw(f * 1.003, n) * 0.4
    y = fx.sweep_lp(y, np.exp(-t / 0.06), 900, 5000)
    return (y * np.exp(-t / 0.18) * vel * 0.5).astype(np.float32)


INSTRUMENTS = {"epiano": epiano, "piano": piano, "pad": pad, "supersaw": supersaw, "strings": strings,
               "strings_lead": strings, "organ": organ, "pluck": pluck, "bell": bell, "guitar": guitar,
               "zither": zither, "flute": flute, "arp": arp_note}


def instrument(name: str, midi: float, dur: float, vel: float) -> np.ndarray:
    return INSTRUMENTS.get(name, pluck)(midi, dur, vel)


# =============================== GIỌNG MẪU ===============================
# Formant (F1, F2, F3) theo nguyên âm cho giọng nữ / nam
FORMANTS_F = {"a": (800, 1150, 2900), "e": (400, 2000, 2800), "i": (300, 2300, 3000), "o": (450, 850, 2830),
              "u": (325, 750, 2700), "ə": (550, 1500, 2600), "ɯ": (360, 1400, 2500)}
FORMANTS_M = {"a": (700, 1100, 2600), "e": (420, 1800, 2550), "i": (290, 2000, 2800), "o": (430, 800, 2550),
              "u": (330, 650, 2500), "ə": (520, 1350, 2400), "ɯ": (340, 1250, 2300)}
_UNVOICED = ("s", "x", "ch", "tr", "t", "th", "k", "c", "q", "p", "ph", "h", "kh", "f", "sh")


def voice_note(midi: float, dur: float, vowel: str = "a", syl: str = "", vel: float = 0.8,
               gender: str = "female", seed: int = 0) -> tuple[np.ndarray, float]:
    """Giọng hát mẫu: nguồn thanh môn + 3 formant theo nguyên âm, có vuốt cao độ, rung giọng, phụ âm đầu.
    Ngân nguyên âm theo giai điệu (không phát âm rõ lời) – dùng làm guide vocal / demo."""
    f0 = midi_to_hz(midi)
    pre = 0.0
    low = syl.lower()
    unv = next((c for c in sorted(_UNVOICED, key=len, reverse=True) if low.startswith(c)), None)
    if unv:
        pre = 0.045 if unv in ("s", "x", "ch", "tr", "kh", "sh", "f", "ph") else 0.025
    n = _n(dur + 0.08)
    t = _t(n)
    rng = _rng("voice", seed, midi)
    scoop = 2 ** (-0.7 * np.exp(-t / 0.06) / 12)
    vib_amt = np.clip((t - 0.28) / 0.35, 0, 1) * (0.35 if dur > 0.45 else 0.0)
    vib = 2 ** (vib_amt * np.sin(2 * np.pi * (5.4 + rng.uniform(-0.3, 0.3)) * t) / 12)
    jitter = 1 + 0.003 * fx.lp(rng.standard_normal(n).astype(np.float32), 8)
    f = f0 * scoop * vib * jitter
    src = saw(f, n) * 0.8 + square(f, n, 0.42) * 0.2
    src = fx.lp(src, 4500 if gender == "female" else 3500)
    table = FORMANTS_F if gender == "female" else FORMANTS_M
    F1, F2, F3 = table.get(vowel, table["a"])
    y = fx.formant(src, F1, 110) * 1.0 + fx.formant(src, F2, 150) * 0.5 + fx.formant(src, F3, 220) * 0.25
    y += fx.lp(src, F1 * 1.2) * 0.15  # thân giọng (hài thấp) cho đầy đặn
    y /= float(np.sqrt(np.mean(y ** 2)) + 1e-9) * 6.0
    breath = fx.bp(noise(n, seed), 2000, 7000)
    breath *= 0.04 / (float(np.sqrt(np.mean(breath ** 2))) + 1e-9) * float(np.sqrt(np.mean(y ** 2)))
    env = adsr(n, 0.04, 0.15, 0.85, 0.06, _n(dur))
    y = (y + breath) * env
    if pre > 0:
        k = _n(pre)
        cons = fx.hp(noise(k, seed + 1), 3000 if unv in ("s", "x", "ch", "sh") else 1500)
        cons *= np.hanning(2 * k)[:k] * 0.06 / (float(np.sqrt(np.mean(cons ** 2))) + 1e-9)
        y = np.concatenate([cons, y])
    return (y * vel).astype(np.float32), pre
