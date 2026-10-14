"""Micow Ear – tầng nghe: dò phách, dò đầu ô nhịp, đặc trưng theo phách/ô nhịp.

Dò phách có hai đường:
  * mạng BeatTCN đã huấn luyện (micow/ear/weights/beat_tcn.npz) cho xác suất phách / đầu ô nhịp từng khung;
  * dự phòng thuật toán: phổ bộ gõ (HPSS) → tempo theo cấp phách (16-8-4-2-1) → quy hoạch động (Ellis)
    → chọn pha bằng kick + snare + đổi hợp âm.
Mọi đặc trưng ô nhịp được chuẩn hoá *trong từng bài* (tương đối) để học trên nhạc tổng hợp vẫn dùng được cho nhạc thật.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.fft import dct
from scipy.ndimage import maximum_filter1d, median_filter
from scipy.signal import find_peaks, stft

from ..analysis import A_SR, HOP, N_FFT, chroma, estimate_key
from ..audio_io import resample

FPS = A_SR / HOP
LAG = N_FFT / 2 / A_SR  # khung STFT tính từ mép trái: bù nửa cửa sổ
BANDS = [30, 60, 120, 250, 500, 1000, 2000, 4000, 8000, 11025]


def _mel_fb(n_mels: int = 40, n_fft: int = N_FFT, sr: int = A_SR, fmin: float = 40, fmax: float = 10000) -> np.ndarray:
    hz2mel = lambda f: 2595 * np.log10(1 + f / 700)
    mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = mel2hz(np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels + 2))
    freqs = np.linspace(0, sr / 2, n_fft // 2 + 1)
    fb = np.zeros((n_mels, len(freqs)), np.float32)
    for i in range(n_mels):
        l, c, r = pts[i], pts[i + 1], pts[i + 2]
        fb[i] = np.clip(np.minimum((freqs - l) / (c - l), (r - freqs) / (r - c)), 0, None)
    return fb


_FB = _mel_fb()


def flux(Sb: np.ndarray) -> np.ndarray:
    L = np.log1p(100 * Sb)
    f = np.concatenate([[0], np.maximum(0, np.diff(L, axis=1)).sum(0)])
    e = np.maximum(0, f - np.convolve(f, np.ones(16) / 16, "same"))
    return (e / (e.max() + 1e-9)).astype(np.float32)


def hpss(S: np.ndarray, kb: int) -> tuple[np.ndarray, np.ndarray]:
    """Phần hoà âm / bộ gõ của phổ < 5 kHz, mặt nạ tính ở độ phân giải 2 khung cho nhanh."""
    nfr = S.shape[1]
    n2 = nfr // 2 * 2
    S2 = 0.5 * (S[:kb, 0:n2:2] + S[:kb, 1:n2:2]) if n2 else S[:kb]
    H = median_filter(S2, size=(1, 17))
    P = median_filter(S2, size=(9, 1))
    mh = H ** 2 / (H ** 2 + P ** 2 + 1e-12)
    mh = np.repeat(mh, 2, axis=1) if n2 else mh
    if mh.shape[1] < nfr:
        mh = np.concatenate([mh, mh[:, -1:].repeat(nfr - mh.shape[1], 1)], 1)
    return S[:kb] * mh, S[:kb] * (1 - mh)


def chord_novelty(C: np.ndarray, w: int) -> np.ndarray:
    C = C / (np.linalg.norm(C, axis=0, keepdims=True) + 1e-9)
    cs = np.concatenate([np.zeros((12, 1)), np.cumsum(C, axis=1)], 1)
    n = C.shape[1]
    out = np.zeros(n, np.float32)
    if n > 2 * w:
        t = np.arange(w, n - w)
        a = cs[:, t] - cs[:, t - w]
        b = cs[:, t + w] - cs[:, t]
        out[t] = 1 - (a * b).sum(0) / (np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0) + 1e-9)
    return out / (out.max() + 1e-9)


def frame_features(S: np.ndarray, C: np.ndarray) -> np.ndarray:
    """Đặc trưng từng khung cho BeatTCN: năng lượng log + flux của 9 dải tần, đổi hợp âm. (T, 19)"""
    freqs = np.linspace(0, A_SR / 2, S.shape[0])
    feats = []
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        L = np.log1p(10 * S[(freqs >= lo) & (freqs < hi)].sum(axis=0))
        Lz = (L - L.mean()) / (L.std() + 1e-6)
        fl = np.concatenate([[0], np.maximum(0, np.diff(L))])
        feats += [Lz, fl / (fl.std() + 1e-6)]
    feats.append(chord_novelty(C, 8) * 3)
    return np.stack(feats, 1).astype(np.float32)


def track_beats(env: np.ndarray, bpm: float, tightness: float = 100.0) -> np.ndarray:
    """Dò phách bằng quy hoạch động (Ellis 2007). Trả chỉ số khung của các phách."""
    n = len(env)
    period = 60.0 * FPS / bpm
    w = np.arange(-int(period), int(period) + 1)
    local = np.convolve(env, np.exp(-0.5 * (w * 32.0 / period) ** 2), "same")
    lo, hi = max(1, int(round(period / 2))), int(round(2 * period))
    offs = np.arange(-hi, -lo + 1)
    pen = -tightness * np.log(-offs / period) ** 2
    score = local.astype(np.float64).copy()
    back = np.full(n, -1)
    for t in range(n):
        c = t + offs
        ok = c >= 0
        if not ok.any():
            continue
        s = score[c[ok]] + pen[ok]
        k = int(np.argmax(s))
        if s[k] > 0:
            score[t] = local[t] + s[k]
            back[t] = c[ok][k]
    tail = max(1, int(period))
    t = n - tail + int(np.argmax(score[n - tail:]))
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    beats = np.array(beats[::-1])
    thr = 0.1 * np.median(local[beats]) if len(beats) else 0
    keep = np.where(local[beats] > thr)[0]
    return beats[keep[0]: keep[-1] + 1] if len(keep) else beats


def _autocorr(env: np.ndarray) -> np.ndarray:
    e = env - env.mean()
    n = len(e)
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    return ac / (ac[0] + 1e-9)


def tempo_candidates(env: np.ndarray, lo: float = 55, hi: float = 210) -> list[float]:
    ac = _autocorr(env)
    lags = np.arange(len(ac))
    bpms = 60 * FPS / np.maximum(lags, 1)
    ok = (bpms >= lo) & (bpms <= hi)
    pk, _ = find_peaks(np.where(ok, ac, -1), distance=3)
    pk = pk[np.argsort(-ac[pk])][:5]
    out = set()
    for L in pk:
        Lf = float(L)
        if 1 <= L < len(ac) - 1:
            a, b, c = ac[L - 1], ac[L], ac[L + 1]
            Lf = L + float(np.clip(0.5 * (a - c) / (a - 2 * b + c + 1e-12), -0.5, 0.5))
        bpm = 60 * FPS / Lf
        for m in (1, 2, 0.5, 1.5, 2 / 3):
            if 60 <= bpm * m <= 190:
                out.add(round(bpm * m, 2))
    return sorted(out)


def metrical_tempo(env: np.ndarray, cands: list[float], prior: float = 110, sd: float = 0.9) -> float:
    """Chọn tempo được cả các cấp phách (1/4, 1/2, 1, 2, 4 phách) ủng hộ – tránh nhầm 2/3, 4/3 do nhịp nghịch."""
    ac = _autocorr(env)

    def A(L):
        if L < 1 or L >= len(ac) - 1:
            return 0.0
        i = int(L)
        f = L - i
        return (1 - f) * ac[i] + f * ac[i + 1]
    best, bt = -1e9, 120.0
    for T in cands:
        L = 60 * FPS / T
        m = sum(w * max(0.0, A(k * L)) for k, w in ((0.25, .5), (0.5, .75), (1, 1), (2, .75), (4, .5)))
        s = m * np.exp(-0.5 * (np.log2(T / prior) / sd) ** 2)
        if s > best:
            best, bt = s, T
    return bt


@dataclass
class EarFeatures:
    duration: float
    bpm: float
    key: dict
    beats: np.ndarray          # giây
    downbeat_phase: int
    bars: np.ndarray           # giây bắt đầu mỗi ô nhịp (+ mốc kết thúc ô cuối)
    beat_chroma: np.ndarray    # (n_beats, 12)
    bar_chroma: np.ndarray     # (n_bars, 48) chroma xếp chồng 4 phách
    bar_mfcc: np.ndarray       # (n_bars, 13)
    scal: dict = field(default_factory=dict)  # đặc trưng vô hướng theo ô nhịp: tên → (n_bars,)
    method: str = "dsp"
    activation: np.ndarray | None = None      # (T, 2) xác suất phách / đầu ô nhịp (nếu có mạng)
    beat_db: np.ndarray | None = None         # độ lớn (dB) từng phách
    frame_db: np.ndarray | None = None        # độ lớn (dB) từng khung 23 ms – để bắt đúng khoảnh khắc drop

    @property
    def n_bars(self) -> int:
        return len(self.bars) - 1


def analyze_frames(y: np.ndarray):
    """Phổ + phần hoà âm/bộ gõ + chroma (dùng chung cho dò phách và huấn luyện)."""
    _, _, Z = stft(y, fs=A_SR, nperseg=N_FFT, noverlap=N_FFT - HOP, boundary=None, padded=True)
    S = np.abs(Z).astype(np.float32)
    kb = int(5200 / (A_SR / N_FFT)) + 1
    H, P = hpss(S, kb)
    C = chroma(np.concatenate([H, np.zeros((S.shape[0] - kb, S.shape[1]), np.float32)], 0))
    return S, H, P, C, kb


def beat_grid(S, P, C, kb, use_model: bool = True):
    """Trả (chỉ số khung các phách, pha đầu ô nhịp, bpm, phương pháp, activation)."""
    freqs = np.linspace(0, A_SR / 2, S.shape[0])
    fp = freqs[:kb]
    kick = flux(P[fp < 150])
    snare = flux(P[(fp > 150) & (fp < 5000)])
    envb = 0.5 * flux(P) + 0.5 * kick
    model = None
    if use_model:
        from .nn import beat_model
        model = beat_model()
    act = None
    if model is not None:
        act = model(frame_features(S, C))
        env = 0.75 * act[:, 0] / (act[:, 0].max() + 1e-9) + 0.25 * envb
        method = "tcn"
    else:
        env = envb
        method = "dsp"
    cands = tempo_candidates(env)
    T = metrical_tempo(env, cands) if cands else 120.0
    bt = track_beats(env, T)
    if len(bt) < 8:
        bt = np.arange(0, S.shape[1], 60 * FPS / T).astype(int)
    per = int(round(np.median(np.diff(bt)))) if len(bt) > 1 else int(60 * FPS / T)
    cnov = maximum_filter1d(chord_novelty(C, max(2, per // 2)), 5)
    k5, s5 = maximum_filter1d(kick, 5), maximum_filter1d(snare, 5)
    a5 = maximum_filter1d(act[:, 0], 3) if act is not None else None
    best, best_o = -1e9, 0
    for o in (0, per // 4, per // 2, 3 * per // 4):  # chọn pha phách
        b2 = np.clip(bt + o, 0, len(env) - 1)
        sc = k5[b2].mean() + 0.6 * s5[b2].mean() + 1.5 * np.sort(cnov[b2])[-max(1, len(b2) // 4):].mean()
        if a5 is not None:
            sc = 0.4 * sc + 3.0 * a5[b2].mean()
        if sc > best:
            best, best_o = sc, o
    bt = np.clip(bt + best_o, 0, len(env) - 1)
    d5 = maximum_filter1d(act[:, 1], 3) if act is not None else None
    scores = []
    for p in range(4):  # pha đầu ô nhịp
        b = bt[p::4]
        s = cnov[b].mean() + 0.5 * k5[b].mean() - 0.3 * s5[b].mean()
        if d5 is not None:
            s = 0.3 * s + 2.0 * d5[b].mean()
        scores.append(s)
    phase = int(np.argmax(scores))
    if len(bt) > 4:
        T = float(60 * FPS / np.median(np.diff(bt)))
    return bt, phase, T, method, act


def extract(x: np.ndarray, sr: int, use_model: bool = True) -> EarFeatures:
    m = x.mean(axis=1) if x.ndim == 2 else x
    y = resample(m.astype(np.float32), sr, A_SR) if sr != A_SR else m.astype(np.float32)
    dur = len(y) / A_SR
    S, H, P, C, kb = analyze_frames(y)
    nfr = S.shape[1]
    beats_f, phase, bpm, method, act = beat_grid(S, P, C, kb, use_model)
    beats_f = beats_f[beats_f < nfr]

    freqs = np.linspace(0, A_SR / 2, S.shape[0])
    Pw = S ** 2
    tot = Pw.sum(axis=0) + 1e-10
    rms_db = 10 * np.log10(Pw.mean(axis=0) + 1e-12)
    bass = Pw[freqs < 150].sum(axis=0) / tot
    Hp = H ** 2
    fk = freqs[:kb]
    vocal = Hp[(fk > 300) & (fk < 3400)].sum(axis=0) / (Hp.sum(axis=0) + 1e-10)
    harm_ratio = Hp.sum(axis=0) / (Pw[:kb].sum(axis=0) + 1e-10)
    cent = (S * freqs[:, None]).sum(axis=0) / (S.sum(axis=0) + 1e-9)
    flat = np.exp(np.mean(np.log(S[5:400] + 1e-9), axis=0)) / (np.mean(S[5:400], axis=0) + 1e-9)
    mfcc = dct(np.log(_FB @ Pw + 1e-8), type=2, axis=0, norm="ortho")[:13]
    env = flux(S)

    def seg_mean(a, idx):
        out = []
        step = int(np.median(np.diff(idx))) if len(idx) > 1 else nfr
        b = list(idx) + [min(nfr, idx[-1] + step)]
        for s, e in zip(b[:-1], b[1:]):
            out.append(a[..., s:max(e, s + 1)].mean(axis=-1))
        return np.stack(out, axis=-1)

    bc = seg_mean(C, beats_f).T
    bc = bc / (np.linalg.norm(bc, axis=1, keepdims=True) + 1e-9)
    down = beats_f[phase::4]
    beat_s = beats_f / FPS + LAG
    bar_starts = down / FPS + LAG
    period = float(np.median(np.diff(beat_s))) if len(beat_s) > 1 else 60 / bpm
    bars = np.concatenate([bar_starts, [min(dur, bar_starts[-1] + 4 * period)]]) if len(bar_starts) else np.array([0.0, dur])
    nbar = len(bars) - 1
    bar_frames = np.clip(((bars - LAG) * FPS).round().astype(int), 0, nfr - 1)
    bar_chroma = np.zeros((nbar, 48), np.float32)
    for i in range(nbar):
        bi = phase + 4 * i
        for k in range(4):
            if bi + k < len(bc):
                bar_chroma[i, 12 * k:12 * k + 12] = bc[bi + k]
    bar_chroma /= np.linalg.norm(bar_chroma, axis=1, keepdims=True) + 1e-9
    bm = seg_mean(mfcc, bar_frames[:-1]).T if nbar else np.zeros((0, 13))
    scal = {}
    for name, arr in (("db", rms_db), ("onset", env), ("bright", cent), ("bass", bass), ("vocal", vocal),
                      ("harm", harm_ratio), ("flat", flat)):
        scal[name] = seg_mean(arr, bar_frames[:-1]) if nbar else np.zeros(0)
    mid = len(y) // 2  # giọng: đo trên 60 giây giữa bài cho nhanh
    key, _ = estimate_key(y[max(0, mid - 30 * A_SR): mid + 30 * A_SR])
    beat_db = seg_mean(rms_db, beats_f) if len(beats_f) else np.zeros(0)
    return EarFeatures(dur, round(bpm, 2), key.to_dict(), beat_s, phase, bars, bc, bar_chroma,
                       bm.astype(np.float32), scal, method, act, beat_db.astype(np.float32), rms_db.astype(np.float32))
