"""Dùng đoạn nhạc người dùng đưa vào làm nguyên liệu (như producer làm beat từ sample).

Các cách dùng (mỗi clip chọn một):
  style  – chỉ học tempo / giọng / năng lượng (planner đã xử lý)
  loop   – lấy vòng lặp 2–4 ô nhịp đẹp nhất, co giãn về tempo bài, dịch giọng, trải suốt bài
  chop   – cắt lát theo onset rồi xếp lại thành nhịp mới (kiểu MPC)
  kit    – tách tiếng kick / snare / hat trong clip để thay bộ trống tổng hợp
"""
from __future__ import annotations

import numpy as np

from ..analysis import A_SR, classify_hit
from ..audio_io import SR, resample
from ..planner import Blueprint
from . import fx


def _key_shift(src_tonic: int, dst_tonic: int) -> int:
    d = (dst_tonic - src_tonic) % 12
    return d - 12 if d > 6 else d


def _slice_stretch(x: np.ndarray, onsets_s: list[float], ratio: float) -> np.ndarray:
    """Co giãn kiểu ReCycle cho clip trống: dời từng lát theo tỉ lệ, giữ nguyên tiếng đánh."""
    n_out = int(len(x) * ratio)
    out = np.zeros(n_out, dtype=np.float32)
    pts = [0] + [int(t * SR) for t in onsets_s if 0 < t * SR < len(x)] + [len(x)]
    for a, b in zip(pts[:-1], pts[1:]):
        seg = x[a:b]
        if not len(seg):
            continue
        pos = int(a * ratio)
        L = min(len(seg), n_out - pos)
        if L <= 0:
            continue
        seg = seg[:L].copy()
        k = min(64, L)
        seg[-k:] *= np.linspace(1, 0, k)
        out[pos:pos + L] += seg
    return out


def best_loop(x: np.ndarray, a: dict, bars: int = 2) -> tuple[np.ndarray, float, float]:
    """Chọn đoạn `bars` ô nhịp (theo tempo của clip) giàu năng lượng nhất, cắt đúng phách. x mono SR."""
    bpm = a.get("bpm") or 0
    if not bpm:
        return x[: int(4 * SR)], 0.0, 0.0
    beat = 60.0 / bpm
    L = int(bars * 4 * beat * SR)
    if L >= len(x):
        bars = max(1, int(len(x) / SR / (4 * beat)))
        L = int(bars * 4 * beat * SR)
        if L <= 0 or L > len(x):
            return x, bpm, 0.0
    off = a.get("beat_offset", 0.0)
    best, best_e = int(off * SR), -1.0
    t = off
    while (t + bars * 4 * beat) * SR <= len(x):
        i = int(t * SR)
        e = float(np.mean(x[i:i + L] ** 2))
        if e > best_e:
            best, best_e = i, e
        t += 4 * beat
    return x[best:best + L].copy(), bpm, best / SR


def make_loop_layer(x_st: np.ndarray, a: dict, bp: Blueprint) -> np.ndarray:
    """Vòng lặp đã khớp tempo + giọng, trải theo các đoạn có năng lượng; intro lọc tối (filter-in)."""
    mono = x_st.mean(axis=1)
    loop, src_bpm, start = best_loop(mono, a, bars=2 if bp.bpm < 120 else 4)
    if not len(loop):
        return np.zeros((int(bp.duration * SR), 2), np.float32)
    if src_bpm:
        ratio = src_bpm / bp.bpm
        if a.get("kind") == "drums":
            ons = [t - start for t in a.get("onsets", []) if start <= t < start + len(loop) / SR]
            loop = _slice_stretch(loop, ons, ratio)
        else:
            loop = fx.stretch_pv(loop, ratio)
    if a.get("kind") != "drums" and a.get("key"):
        sh = _key_shift(a["key"]["tonic"], bp.key.tonic)
        loop = fx.pitch_shift(loop, sh)
    # cắt / đệm đúng số ô nhịp
    bars_in_loop = max(1, int(round(len(loop) / SR / bp.bar_seconds)))
    want = int(bars_in_loop * bp.bar_seconds * SR)
    loop = np.pad(loop, (0, max(0, want - len(loop))))[:want]
    k = min(256, len(loop) // 8)
    if k:
        loop[:k] *= np.linspace(0, 1, k)
        loop[-k:] *= np.linspace(1, 0, k)
    total = int(bp.duration * SR) + SR
    out = np.zeros(total, np.float32)
    for sec in bp.sections:
        if sec.kind == "break":
            continue
        g = 0.55 + 0.45 * sec.energy
        for b in range(0, sec.bars, bars_in_loop):
            i = int((sec.start_bar + b) * bp.bar_seconds * SR)
            seg = loop[: min(len(loop), int((sec.bars - b) * bp.bar_seconds * SR))]
            if sec.kind in ("intro", "outro"):
                seg = fx.lp(seg, 900 if sec.kind == "intro" else 1500)
            j = min(total, i + len(seg))
            out[i:j] += seg[: j - i] * g
    return np.stack([out, out], axis=1)


def extract_kit(x_st: np.ndarray, a: dict) -> dict[str, np.ndarray]:
    """Lấy lát kick / snare / hat to nhất trong clip."""
    mono = x_st.mean(axis=1)
    y22 = resample(mono, SR, A_SR)
    best: dict[str, tuple[float, np.ndarray]] = {}
    for t in a.get("onsets", [])[:300]:
        i22 = int(t * A_SR)
        cls = classify_hit(y22[i22:i22 + int(0.2 * A_SR)])
        if cls == "tonal":
            continue
        i = int(t * SR)
        L = int({"kick": 0.35, "snare": 0.3, "hat": 0.12}[cls] * SR)
        seg = mono[max(0, i - 64): i + L].copy()
        if len(seg) < 512:
            continue
        loud = float(np.max(np.abs(seg[:2048])))
        if cls not in best or loud > best[cls][0]:
            best[cls] = (loud, seg)
    kit = {}
    for cls, (loud, seg) in best.items():
        seg = seg / (loud + 1e-9)
        k = min(len(seg) // 3, int(0.04 * SR))
        seg[-k:] *= np.linspace(1, 0, k)
        kit[cls] = seg.astype(np.float32)
    return kit


def make_chop_layer(x_st: np.ndarray, a: dict, bp: Blueprint, seed: int = 0) -> np.ndarray:
    """Cắt lát theo onset, chọn 6–8 lát, xếp thành mẫu 2 ô nhịp lặp lại (biến tấu nhẹ ở cuối đoạn)."""
    rng = np.random.default_rng(seed + 77)
    mono = x_st.mean(axis=1)
    ons = [t for t in a.get("onsets", []) if t * SR < len(mono) - 2048]
    if len(ons) < 3:
        ons = list(np.arange(0, len(mono) / SR - 0.3, 60.0 / max(60, a.get("bpm") or 100)))
    sh = _key_shift(a["key"]["tonic"], bp.key.tonic) if a.get("key") and a.get("kind") != "drums" else 0
    slices = []
    for i, t in enumerate(ons[:64]):
        end = ons[i + 1] if i + 1 < len(ons) else t + 0.5
        seg = mono[int(t * SR): int(min(end, t + 0.6) * SR)].copy()
        if len(seg) > 1024:
            slices.append(seg)
    if not slices:
        return np.zeros((int(bp.duration * SR) + SR, 2), np.float32)
    energy = np.array([np.mean(s ** 2) for s in slices])
    order = np.argsort(-energy)[: min(8, len(slices))]
    pick = [slices[i] for i in order]
    if sh:
        pick = [fx.pitch_shift(s, sh) for s in pick]
    steps = sorted(rng.choice(32, size=min(12, 32), replace=False).tolist())
    steps = sorted(set([0, 8, 16, 24] + steps[:8]))
    pattern = [(st, int(rng.integers(0, len(pick)))) for st in steps]
    step_s = 60.0 / bp.bpm / 4
    total = int(bp.duration * SR) + SR
    out = np.zeros(total, np.float32)
    for sec in bp.sections:
        if sec.kind in ("intro", "break") or sec.energy < 0.45:
            continue
        for b in range(0, sec.bars, 2):
            base = (sec.start_bar + b) * bp.bar_seconds
            for j, (st, si) in enumerate(pattern):
                if st >= (sec.bars - b) * 16:
                    continue
                nxt = pattern[j + 1][0] if j + 1 < len(pattern) else 32
                seg = pick[si][: int((nxt - st) * step_s * SR)].copy()
                if len(seg) < 64:
                    continue
                kf = min(128, len(seg) // 4)
                seg[-kf:] *= np.linspace(1, 0, kf)
                i = int((base + st * step_s) * SR)
                jj = min(total, i + len(seg))
                out[i:jj] += seg[: jj - i] * (0.6 + 0.4 * sec.energy)
    return np.stack([out, out], axis=1)
