"""Micow Ear – cấu trúc bài: đoạn lặp, ranh giới, nhãn đoạn, **hook** và **peak**.

Quy trình (mức ô nhịp):
  1. Ma trận tự tương đồng (SSM) từ chroma xếp chồng 4 phách + âm sắc MFCC, làm nổi đường chéo 4 ô nhịp
     → mỗi ô nhịp "lặp lại" bao nhiêu, giống đoạn nào.
  2. Novelty (kernel bàn cờ – Foote) + bước nhảy năng lượng → ranh giới đoạn, ưu tiên bội số 4 ô nhịp.
  3. Gom đoạn giống nhau thành cụm A/B/C…
  4. Quy tắc: hook = cụm lặp nhiều + to + nhiều giọng; peak = cửa sổ năng lượng/độ dày cao nhất, có cú "drop".
  5. Nếu có mạng BarMLP đã huấn luyện: trộn 50/50 xác suất của mạng với quy tắc.
"""
from __future__ import annotations

import numpy as np

from .features import EarFeatures
from .nn import KINDS, bar_model

FEAT_NAMES = ["energy", "energy_z", "d_energy", "onset", "bright", "bass", "vocal", "harm", "flat", "rep", "rep_count",
              "novelty", "pos", "cluster_count", "seg_energy_rank", "seg_start", "seg_pos", "seg_len"]


def _rel(x: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(x, 5), np.percentile(x, 95)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


def _z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / (x.std() + 1e-9)


def ssm(f: EarFeatures) -> np.ndarray:
    c = f.bar_chroma
    m = f.bar_mfcc - f.bar_mfcc.mean(axis=0)
    m = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
    S = 0.6 * (c @ c.T) + 0.4 * (0.5 + 0.5 * (m @ m.T))
    return S.astype(np.float32)


def path_enhance(S: np.ndarray, L: int = 4) -> np.ndarray:
    n = len(S)
    E = np.zeros_like(S)
    cnt = np.zeros_like(S)
    for k in range(L):
        E[: n - k, : n - k] += S[k:, k:]
        cnt[: n - k, : n - k] += 1
    return E / np.maximum(cnt, 1)


def novelty(S: np.ndarray, half: int = 4) -> np.ndarray:
    n = len(S)
    g = np.exp(-0.5 * (np.linspace(-1.5, 1.5, 2 * half)) ** 2)
    K = np.outer(g, g) * np.block([[np.ones((half, half)), -np.ones((half, half))], [-np.ones((half, half)), np.ones((half, half))]])
    P = np.pad(S, half, mode="edge")
    out = np.array([(P[i:i + 2 * half, i:i + 2 * half] * K).sum() for i in range(n)])
    out = np.maximum(out, 0)
    return out / (out.max() + 1e-9)


def segment(nov: np.ndarray, energy: np.ndarray, min_len: int = 4) -> list[int]:
    n = len(nov)
    jump = np.abs(np.diff(np.concatenate([[energy[0]], energy])))
    score = 0.7 * nov + 0.5 * _rel(jump)
    score = score + 0.12 * (np.arange(n) % 4 == 0)
    bounds = [0]
    cands = sorted(range(min_len, n - min_len + 1), key=lambda i: -score[i])
    thr = max(0.25, np.percentile(score, 75))
    for i in cands:
        if score[i] < thr:
            break
        if all(abs(i - b) >= min_len for b in bounds):
            bounds.append(i)
    return sorted(bounds) + [n]


def cluster(bounds: list[int], E: np.ndarray, thr: float = 0.86) -> list[int]:
    labels: list[int] = []
    reps: list[int] = []
    for a in range(len(bounds) - 1):
        s0, s1 = bounds[a], bounds[a + 1]
        best, bl = -1.0, -1
        for lab, r in enumerate(reps):
            r0, r1 = bounds[r], bounds[r + 1]
            L = min(s1 - s0, r1 - r0)
            if L <= 0:
                continue
            sim = float(np.mean([E[s0 + k, r0 + k] for k in range(L)]))
            if sim > best:
                best, bl = sim, lab
        if best >= thr:
            labels.append(bl)
        else:
            labels.append(len(reps))
            reps.append(a)
    return labels


def bar_features(f: EarFeatures) -> tuple[np.ndarray, dict]:
    """Đặc trưng từng ô nhịp (n, 18) + thông tin cấu trúc trung gian."""
    n = f.n_bars
    sc = f.scal
    e = _rel(sc["db"])
    S = ssm(f)
    E = path_enhance(S, 4)
    off = np.abs(np.arange(n)[:, None] - np.arange(n)[None, :]) >= 4
    Eo = np.where(off, E, -1)
    rep = Eo.max(axis=1) if n > 4 else np.zeros(n)
    thr = max(0.8, float(np.percentile(E[off], 90))) if off.any() else 1.0
    rep_count = (Eo > thr).sum(axis=1) / 4.0
    nov = novelty(S, 4 if n >= 16 else 2)
    bounds = segment(nov, e, 4 if n >= 16 else 2)
    labels = cluster(bounds, E)
    counts = {lab: labels.count(lab) for lab in labels}
    seg_of = np.zeros(n, int)
    for a in range(len(bounds) - 1):
        seg_of[bounds[a]:bounds[a + 1]] = a
    seg_e = np.array([e[bounds[a]:bounds[a + 1]].mean() for a in range(len(bounds) - 1)])
    rank = np.argsort(np.argsort(seg_e)) / max(1, len(seg_e) - 1)
    de = np.array([e[i:i + 2].mean() - e[max(0, i - 2):i].mean() if i > 0 else 0 for i in range(n)])
    feats = np.zeros((n, len(FEAT_NAMES)), np.float32)
    for i in range(n):
        a = seg_of[i]
        s0, s1 = bounds[a], bounds[a + 1]
        feats[i] = [e[i], _z(sc["db"])[i], de[i], _rel(sc["onset"])[i], _rel(sc["bright"])[i], _rel(sc["bass"])[i],
                    _rel(sc["vocal"])[i], _rel(sc["harm"])[i], _rel(sc["flat"])[i], rep[i], min(2.0, rep_count[i]),
                    nov[i], i / max(1, n - 1), counts[labels[a]] / max(counts.values()), rank[a], float(i == s0),
                    (i - s0) / max(1, s1 - s0), min(2.0, (s1 - s0) / 16)]
    return feats, {"S": S, "E": E, "bounds": bounds, "labels": labels, "seg_of": seg_of, "energy": e, "novelty": nov}


def rule_scores(feats: np.ndarray, info: dict) -> tuple[np.ndarray, np.ndarray]:
    """Điểm hook / peak theo quy tắc (0..1 cho từng ô nhịp)."""
    F = {k: feats[:, i] for i, k in enumerate(FEAT_NAMES)}
    bounds, labels = info["bounds"], info["labels"]
    n = len(feats)
    seg_score = []
    for a in range(len(bounds) - 1):
        s0, s1 = bounds[a], bounds[a + 1]
        sl = slice(s0, s1)
        # nhân (không cộng): đoạn lặp nhiều nhưng nhỏ tiếng (intro/break lặp lại) không thể là hook
        s = (F["energy"][sl].mean() ** 1.2 * (0.55 + 0.45 * F["cluster_count"][s0])
             * (0.8 + 0.2 * F["vocal"][sl].mean()) * (0.85 + 0.15 * F["onset"][sl].mean()))
        if a == 0 or a == len(bounds) - 2:
            s *= 0.6
        seg_score.append(s)
    seg_score = np.array(seg_score)
    # cụm hook = cụm có điểm trung bình cao nhất
    cl = {}
    for a, lab in enumerate(labels):
        cl.setdefault(lab, []).append(seg_score[a])
    best_lab = max(cl, key=lambda k: np.mean(cl[k]) + 0.05 * len(cl[k]))
    hook = np.zeros(n)
    for a, lab in enumerate(labels):
        v = seg_score[a] / (seg_score.max() + 1e-9)
        hook[bounds[a]:bounds[a + 1]] = v if lab == best_lab else 0.6 * v
    peak = 0.55 * F["energy"] + 0.2 * F["onset"] + 0.15 * F["bright"] + 0.1 * F["bass"]
    return np.clip(hook, 0, 1), np.clip(peak / (peak.max() + 1e-9), 0, 1)


def _best_window(score: np.ndarray, L: int, starts: list[int], bonus: np.ndarray | None = None, exclude=()):
    n = len(score)
    best, bs = -1e9, 0
    for s in starts:
        if s + L > n or any(s < e1 and s + L > e0 for e0, e1 in exclude):
            continue
        v = score[s:s + L].mean() + (bonus[s] if bonus is not None else 0)
        if v > best:
            best, bs = v, s
    return bs, best


def energy_jump(e: np.ndarray, i: int) -> float:
    """Độ tăng năng lượng tại ô nhịp i (2 ô sau so với 2 ô trước)."""
    return float(e[i:i + 2].mean() - e[max(0, i - 2):i].mean()) if i > 0 else 0.0


SNAP_RATIO = 0.6
PREF_RATIO = 0.5


def refine_drop(f: EarFeatures, t0: float, span: float) -> float:
    """Khoảnh khắc drop chính xác: điểm (độ phân giải 23 ms) có bước nhảy độ lớn mạnh nhất quanh t0,
    rồi bám phách gần nhất nếu lệch < 60 ms. Không phụ thuộc việc chia ô nhịp đúng hay sai."""
    from .features import FPS, LAG
    if f.frame_db is None or len(f.frame_db) < 20:
        return t0
    db = np.convolve(f.frame_db, np.ones(5) / 5, "same")
    beat = 60.0 / max(f.bpm, 40)
    w = max(4, int(0.75 * beat * FPS))
    i0 = int(max(w, (t0 - span - LAG) * FPS))
    i1 = int(min(len(db) - w, (t0 + span - LAG) * FPS))
    if i1 <= i0:
        return t0
    cs = np.concatenate([[0.0], np.cumsum(db)])
    idx = np.arange(i0, i1)
    jump = (cs[idx + w] - cs[idx]) / w - (cs[idx] - cs[idx - w]) / w
    k = int(np.argmax(jump))
    if jump[k] < 1.5:  # không có cú nhảy rõ → giữ điểm cấp ô nhịp
        return t0
    t = idx[k] / FPS + LAG
    bars = np.asarray(f.bars[:-1])
    b = np.asarray(f.beats)
    bar_s = float(np.median(np.diff(f.bars))) if len(f.bars) > 2 else 2.0

    def jump_at(tt):
        i = int(round((tt - LAG) * FPS))
        if i - w < 0 or i + w >= len(db):
            return -1e9
        return (cs[i + w] - cs[i]) / w - (cs[i] - cs[i - w]) / w
    # ưu tiên đầu ô nhịp mà phân tích cấu trúc đã chọn (t0) nếu ở đó cũng có thay đổi độ lớn rõ ràng
    # (fill / build ngay trước điệp khúc hay tạo cú nhảy sớm hơn 1 phách – đừng đuổi theo nó)
    if jump_at(t0) >= PREF_RATIO * jump[k]:
        return float(t0)
    # đoạn mới thường vào ở đầu ô nhịp (hoặc nửa ô khi tempo bị bắt nửa): chọn điểm lưới có cú nhảy mạnh nhất
    # trong ±0,6 ô nhịp; dùng nếu nó đạt ≥ SNAP_RATIO cú nhảy mạnh nhất tìm được ở mức khung
    if len(bars):
        grid = np.concatenate([bars, bars + bar_s / 2])
        grid = grid[np.abs(grid - t) <= 0.6 * bar_s]
        if len(grid):
            js = np.array([jump_at(g) for g in grid])
            g = float(grid[int(np.argmax(js))])
            if js.max() >= SNAP_RATIO * jump[k]:
                return g
    if len(b) and np.min(np.abs(b - t)) < 0.06:
        t = float(b[np.argmin(np.abs(b - t))])
    return float(t)


def analyze_structure(f: EarFeatures, use_model: bool = True) -> dict:
    n = f.n_bars
    bs = float(np.median(np.diff(f.bars))) if n > 1 else 2.0
    if n < 4:  # đoạn quá ngắn: cả đoạn là hook, peak là ô nhịp to nhất
        e = _rel(f.scal["db"]) if n else np.zeros(0)
        whole = {"start_bar": 0, "end_bar": n, "bars": n, "start": round(float(f.bars[0]), 3),
                 "end": round(float(f.bars[-1]), 3), "score": 1.0, "confidence": 0.3}
        pk = int(np.argmax(e)) if n else 0
        t = refine_drop(f, float(f.bars[pk]), 1.2 * bs)
        peak = {"start_bar": pk, "end_bar": min(n, pk + 1), "bars": 1, "start": round(t, 3), "drop": round(t, 3),
                "end": round(float(f.bars[min(n, pk + 1)]) + t - float(f.bars[pk]), 3), "score": 1.0}
        return {"bars": [round(float(b), 3) for b in f.bars], "sections": [], "hook": whole, "candidates": [whole],
                "peak": peak, "energy": [round(float(v), 3) for v in e], "hook_curve": [], "peak_curve": [],
                "bar_seconds": round(bs, 4), "model": "rule"}
    feats, info = bar_features(f)
    hook_r, peak_r = rule_scores(feats, info)
    model = bar_model() if use_model else None
    kind_p = None
    if model is not None:
        o = model(feats)
        hook = 0.5 * hook_r + 0.5 * o["hook"]
        peak = 0.5 * peak_r + 0.5 * o["peak"]
        kind_p = o["kind"]
    else:
        hook, peak = hook_r, peak_r
    bounds, labels = info["bounds"], info["labels"]
    L = 8 if 8 * bs <= 22 else 4
    L = min(L, max(2, n // 3))
    starts = sorted(set(bounds[:-1]) | set(range(0, n - L + 1, 4)) | {i for i in range(1, n) if hook[i] > 0.5 >= hook[i - 1]})
    early = np.array([0.04 * (1 - i / n) for i in range(n)])  # hook: ưu tiên lần xuất hiện sớm
    cands = []
    # ứng viên = các "vùng hook" liền mạch (mỗi lần điệp khúc/drop xuất hiện), cắt theo đúng biên của vùng
    thr = max(0.45, 0.6 * float(hook.max()))
    runs, i = [], 0
    while i < n:
        if hook[i] >= thr:
            j = i
            while j < n and hook[j] >= thr:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    scored = []
    for a, b in runs:
        Lr = int(np.clip(b - a, min(4, L), L))
        a2 = min(a, max(0, n - Lr))
        scored.append((float(hook[a2:a2 + Lr].mean()) + early[a2] + 0.1 * float(info["energy"][a2:a2 + Lr].mean()), a2, Lr))
    scored.sort(reverse=True)
    for v, a2, Lr in scored:
        if all(not (a2 < c["start_bar"] + c["bars"] and a2 + Lr > c["start_bar"]) for c in cands):
            cands.append({"start_bar": int(a2), "bars": int(Lr), "score": round(float(hook[a2:a2 + Lr].mean()), 3)})
        if len(cands) == 3:
            break
    while len(cands) < 3:  # bổ sung bằng cửa sổ cố định nếu ít vùng
        s0, v = _best_window(hook, L, starts, early, [(c["start_bar"], c["start_bar"] + c["bars"]) for c in cands])
        if v <= -1e8:
            break
        cands.append({"start_bar": int(s0), "bars": L, "score": round(float(hook[s0:s0 + L].mean()), 3)})
    jump = np.array([max(0.0, peak[i:i + 2].mean() - peak[max(0, i - 2):i].mean()) if i > 1 else 0 for i in range(n)])
    pk_s, _ = _best_window(peak, L, list(range(0, n - L + 1)), 0.6 * jump)
    # điểm vào cao trào: quanh cửa sổ tốt nhất (±2 ô nhịp), chọn ô nhịp mà xác suất peak + năng lượng TĂNG mạnh nhất
    e_bar = info["energy"]
    best_c, best_v = pk_s, -1e9
    for c in range(max(1, pk_s - 2), min(n - 1, pk_s + 2) + 1):
        v = (peak[c:c + 2].mean() - peak[max(0, c - 2):c].mean()) + 0.5 * energy_jump(e_bar, c)
        if v > best_v:
            best_c, best_v = c, v
    if best_v > 0.05:
        pk_s = best_c
    pk_s = int(min(pk_s, max(0, n - L)))
    # nhãn đoạn
    sections = []
    for a in range(len(bounds) - 1):
        s0, s1 = bounds[a], bounds[a + 1]
        if kind_p is not None:
            kind = KINDS[int(np.argmax(kind_p[s0:s1].mean(axis=0)))]
        else:
            kind = _heuristic_kind(a, len(bounds) - 1, hook[s0:s1].mean(), feats[s0:s1], labels, s1 - s0, n)
        sections.append({"kind": kind, "label": chr(65 + labels[a]) if labels[a] < 26 else str(labels[a]),
                         "start_bar": int(s0), "end_bar": int(s1), "start": round(float(f.bars[s0]), 3),
                         "end": round(float(f.bars[s1]), 3), "energy": round(float(info["energy"][s0:s1].mean()), 3),
                         "hook": round(float(hook[s0:s1].mean()), 3)})

    def win(sb, L):
        e = min(n, sb + L)
        return {"start_bar": int(sb), "end_bar": int(e), "bars": int(e - sb), "start": round(float(f.bars[sb]), 3),
                "end": round(float(f.bars[e]), 3)}
    for c in cands:
        c.update(win(c["start_bar"], c["bars"]))
    peak_w = win(pk_s, L)
    peak_w["score"] = round(float(peak[pk_s:pk_s + L].mean()), 3)
    drop_t = refine_drop(f, peak_w["start"], 0.6 * bs)
    peak_w["drop"] = round(drop_t, 3)
    if abs(drop_t - peak_w["start"]) > 1e-3:
        peak_w["end"] = round(peak_w["end"] + (drop_t - peak_w["start"]), 3)
        peak_w["start"] = round(drop_t, 3)
    conf = float(np.clip((cands[0]["score"] - (cands[1]["score"] if len(cands) > 1 else 0)) * 3 + 0.4, 0, 1)) if cands else 0
    return {"bars": [round(float(b), 3) for b in f.bars], "sections": sections,
            "hook": dict(cands[0], confidence=round(conf, 2)) if cands else None, "candidates": cands, "peak": peak_w,
            "hook_curve": [round(float(v), 3) for v in hook], "peak_curve": [round(float(v), 3) for v in peak],
            "energy": [round(float(v), 3) for v in info["energy"]], "bar_seconds": round(bs, 4),
            "model": "mlp+rule" if model is not None else "rule"}


def _heuristic_kind(a, nseg, hook, F, labels, length, n):
    e = F[:, 0].mean()
    vocal = F[:, 6].mean()
    if a == 0 and e < 0.5:
        return "intro"
    if a == nseg - 1 and e < 0.5:
        return "outro"
    if hook > 0.75:
        return "chorus" if vocal > 0.35 else "drop"
    if labels.count(labels[a]) == 1 and 0.45 < a / max(1, nseg - 1) < 0.9:
        return "bridge"
    if length <= 4 and e > 0.4:
        return "prechorus"
    if e < 0.3:
        return "break"
    return "verse"
