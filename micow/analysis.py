"""Phân tích đoạn nhạc đưa vào: tempo, phách, giọng, năng lượng, độ sáng, điểm onset, lát cắt trống.

Chỉ cần numpy + scipy, chạy CPU vài trăm mili-giây cho một clip 30 giây.
Kết quả dùng để: (1) planner khớp tempo/giọng/thể loại, (2) sampler cắt lát, lấy tiếng trống, vòng lặp,
(3) gửi kèm cho engine AI (ACE-Step reference audio).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import stft, find_peaks

from .theory import Key

A_SR = 22050
N_FFT = 2048
HOP = 512

# Krumhansl–Kessler key profiles
_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _mono22(x: np.ndarray, sr: int) -> np.ndarray:
    from .audio_io import resample
    m = x.mean(axis=1) if x.ndim == 2 else x
    return resample(m.astype(np.float32), sr, A_SR) if sr != A_SR else m.astype(np.float32)


def spectrogram(y: np.ndarray) -> np.ndarray:
    _, _, Z = stft(y, fs=A_SR, nperseg=N_FFT, noverlap=N_FFT - HOP, boundary=None, padded=True)
    return np.abs(Z).astype(np.float32)  # (freq, frames)


def onset_envelope(S: np.ndarray) -> np.ndarray:
    L = np.log1p(100.0 * S)
    flux = np.maximum(0.0, np.diff(L, axis=1)).sum(axis=0)
    flux = np.concatenate([[0.0], flux])
    # trừ trung bình trượt để làm nổi đỉnh
    k = 16
    ker = np.ones(k) / k
    base = np.convolve(flux, ker, mode="same")
    env = np.maximum(0.0, flux - base)
    return env / (env.max() + 1e-9)


def estimate_tempo(env: np.ndarray, lo: float = 60, hi: float = 200) -> tuple[float, float]:
    """Tự tương quan đường onset + ưu tiên log-normal quanh 110 BPM. Trả (bpm, độ tin cậy 0..1)."""
    fps = A_SR / HOP
    n = len(env)
    if n < fps * 2:
        return 0.0, 0.0
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[n - 1:]
    ac /= ac[0] + 1e-9
    lags = np.arange(len(ac))
    with np.errstate(divide="ignore"):
        bpms = 60.0 * fps / np.maximum(lags, 1)
    valid = (bpms >= lo) & (bpms <= hi)
    prior = np.exp(-0.5 * (np.log2(np.maximum(bpms, 1) / 110.0) / 0.9) ** 2)
    # cộng điều hoà: nhịp đúng thì lag*2 cũng tương quan
    harm = ac.copy()
    for mlt in (2, 3, 4):
        idx = np.minimum(lags * mlt, len(ac) - 1)
        harm += 0.5 * ac[idx]
    score = np.where(valid, harm * prior, -np.inf)
    best = int(np.argmax(score))
    if not np.isfinite(score[best]) or best == 0:
        return 0.0, 0.0
    # nội suy parabol để lấy lag lẻ
    if 1 <= best < len(score) - 1 and np.isfinite(score[best - 1]) and np.isfinite(score[best + 1]):
        a, b, c = score[best - 1], score[best], score[best + 1]
        d = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
        lag = best + float(np.clip(d, -0.5, 0.5))
    else:
        lag = float(best)
    bpm = 60.0 * fps / lag
    conf = float(np.clip(ac[best] * 1.5, 0.0, 1.0))
    return bpm, conf


def beat_phase(env: np.ndarray, bpm: float) -> float:
    """Thời điểm phách đầu tiên (giây) khớp nhất với đường onset."""
    fps = A_SR / HOP
    period = 60.0 * fps / bpm
    best, best_s = 0.0, -1.0
    for off in np.linspace(0, period, 48, endpoint=False):
        idx = np.round(np.arange(off, len(env), period)).astype(int)
        idx = idx[idx < len(env)]
        s = env[idx].mean() if len(idx) else 0.0
        if s > best_s:
            best, best_s = off, s
    return best / fps


def chroma(S: np.ndarray, n_fft: int = N_FFT, fmin: float = 100, fmax: float = 5000) -> np.ndarray:
    freqs = np.linspace(0, A_SR / 2, S.shape[0])
    sel = (freqs > fmin) & (freqs < fmax)
    f = freqs[sel]
    pcs = (np.round(12 * np.log2(f / 440.0)) + 9) % 12
    C = np.zeros((12, S.shape[1]), dtype=np.float32)
    P = S[sel] ** 2
    for pc in range(12):
        C[pc] = P[pcs == pc].sum(axis=0)
    return C


def harmonic_part(S: np.ndarray) -> np.ndarray:
    """Tách phần hoà âm (HPSS bằng lọc trung vị) để trống không làm sai giọng."""
    from scipy.ndimage import median_filter
    H = median_filter(S, size=(1, 17))
    P = median_filter(S, size=(9, 1))
    return S * (H ** 2 / (H ** 2 + P ** 2 + 1e-12))


# Albrecht & Shanahan (2013): profile giọng sắc nét hơn cho nhạc phổ thông
_AS_MAJ = np.array([0.238, 0.006, 0.111, 0.006, 0.137, 0.094, 0.016, 0.214, 0.009, 0.080, 0.008, 0.081])
_AS_MIN = np.array([0.220, 0.006, 0.104, 0.123, 0.019, 0.103, 0.012, 0.214, 0.062, 0.022, 0.061, 0.052])


def estimate_key(y: np.ndarray) -> tuple[Key, float]:
    """Giọng từ chroma hoà âm (100–5000 Hz) + chroma bass (35–200 Hz, FFT dài cho đủ phân giải)."""
    nf = 8192
    _, _, Z = stft(y, fs=A_SR, nperseg=nf, noverlap=nf - 2048, boundary=None, padded=True)
    S = harmonic_part(np.abs(Z).astype(np.float32))
    T = chroma(S, nf, 100, 5000)
    T = T / (T.sum(axis=0, keepdims=True) + 1e-9)
    B = chroma(S, nf, 35, 200)
    B = B / (B.sum(axis=0, keepdims=True) + 1e-9)
    t, b = T.sum(axis=1), B.sum(axis=1)
    t, b = t / (t.sum() + 1e-9), b / (b.sum() + 1e-9)
    scores = []
    for mode, tpl, kk in (("major", _AS_MAJ, _MAJ), ("minor", _AS_MIN, _MIN)):
        for k in range(12):
            r1 = float(np.corrcoef(t, np.roll(tpl, k))[0, 1])
            r2 = float(np.corrcoef(t, np.roll(kk, k))[0, 1])
            rb = float(np.corrcoef(b, np.roll(tpl, k))[0, 1])
            scores.append((0.5 * r1 + 0.5 * r2 + 0.5 * rb, k, mode))
    scores.sort(reverse=True)
    best = scores[0]
    conf = float(np.clip((best[0] - scores[1][0]) * 4 + 0.3 * best[0], 0, 1))
    return Key(best[1], best[2]), conf


def onsets(env: np.ndarray, min_gap_s: float = 0.06) -> np.ndarray:
    fps = A_SR / HOP
    pk, _ = find_peaks(env, height=0.12, distance=max(1, int(min_gap_s * fps)))
    return pk / fps


def classify_hit(seg: np.ndarray) -> str:
    """Phân loại một lát (150 ms đầu) thành kick / snare / hat / tonal."""
    if len(seg) < 256:
        return "tonal"
    w = seg[: int(0.15 * A_SR)]
    sp = np.abs(np.fft.rfft(w * np.hanning(len(w))))
    f = np.fft.rfftfreq(len(w), 1 / A_SR)
    tot = sp.sum() + 1e-9
    low = sp[f < 150].sum() / tot
    high = sp[f > 5000].sum() / tot
    cent = float((sp * f).sum() / tot)
    flat = float(np.exp(np.mean(np.log(sp + 1e-9))) / (np.mean(sp) + 1e-9))
    if low > 0.35 and cent < 900:
        return "kick"
    if high > 0.35 or cent > 5000:
        return "hat"
    if flat > 0.25 and 900 <= cent <= 5000:
        return "snare"
    return "tonal"


def analyze(x: np.ndarray, sr: int) -> dict:
    """Phân tích đầy đủ; trả dict JSON được (không chứa mảng lớn)."""
    y = _mono22(x, sr)
    dur = len(y) / A_SR
    if dur < 0.5:
        return {"duration": dur, "bpm": 0, "error": "Đoạn quá ngắn (< 0,5 giây)"}
    S = spectrogram(y)
    env = onset_envelope(S)
    bpm, tconf = estimate_tempo(env)
    phase = beat_phase(env, bpm) if bpm else 0.0
    key, kconf = estimate_key(y)
    rms = float(np.sqrt(np.mean(y ** 2)) + 1e-12)
    freqs = np.linspace(0, A_SR / 2, S.shape[0])
    mag = S.mean(axis=1)
    centroid = float((mag * freqs).sum() / (mag.sum() + 1e-9))
    ons = onsets(env)
    density = len(ons) / dur
    perc = float(np.clip(np.percentile(env, 95) * density / 6.0, 0, 1))
    hits = {"kick": 0, "snare": 0, "hat": 0, "tonal": 0}
    for t in ons[:200]:
        i = int(t * A_SR)
        hits[classify_hit(y[i:i + int(0.2 * A_SR)])] += 1
    loud = 20 * np.log10(rms)
    energy = float(np.clip((loud + 30) / 24, 0, 1) * 0.6 + perc * 0.4)
    return {
        "duration": round(dur, 3),
        "bpm": round(bpm, 2), "bpm_confidence": round(tconf, 2), "beat_offset": round(phase, 3),
        "key": key.to_dict(), "key_confidence": round(kconf, 2),
        "rms_db": round(loud, 1), "brightness": round(centroid, 1),
        "onset_density": round(density, 2), "percussive": round(perc, 2), "energy": round(energy, 2),
        "onsets": [round(float(t), 3) for t in ons[:400]],
        "hits": hits,
        "kind": "drums" if hits["kick"] + hits["snare"] + hits["hat"] > 1.5 * max(1, hits["tonal"]) else
                "music" if perc > 0.2 else "tonal",
    }


def suggest_genre(a: dict) -> str | None:
    """Đoán thể loại gần nhất từ tempo + độ dồn dập + độ sáng của clip."""
    bpm = a.get("bpm") or 0
    if not bpm:
        return None
    perc, bright = a.get("percussive", 0.3), a.get("brightness", 2000)
    if 128 <= bpm <= 142 and perc > 0.35:
        return "vinahouse" if bpm >= 131 else "edm"
    if 118 <= bpm < 128 and perc > 0.3:
        return "house"
    if bpm >= 128:
        return "trap"
    if bpm < 80:
        return "ballad" if perc < 0.35 else "lofi"
    if bpm < 98:
        return "lofi" if bright < 1800 else "boombap"
    return "vpop"


def fit_tempo(bpm: float, lo: float, hi: float) -> float:
    """Nhân/chia đôi tempo đo được cho vừa khoảng tempo của thể loại."""
    if not bpm:
        return 0.0
    cands = [bpm / 2, bpm, bpm * 2, bpm * 2 / 3, bpm * 3 / 2]
    mid = (lo + hi) / 2
    return min(cands, key=lambda b: (0 if lo - 4 <= b <= hi + 4 else 1, abs(np.log2(b / mid))))
