"""Huấn luyện Micow Ear (cần PyTorch khi huấn luyện; khi dùng chỉ cần numpy).

  micow train ear --data ~/.micow/ear_data --n 260      # sinh dữ liệu (nếu chưa có), huấn luyện 2 mạng, đánh giá

1. BeatTCN: đặc trưng 19 chiều mỗi khung 23 ms → xác suất phách + đầu ô nhịp (TCN giãn 1..32, tầm nhìn ~3 giây).
2. BarMLP : 18 đặc trưng mỗi ô nhịp × ngữ cảnh ±4 ô → hook, peak, loại đoạn (10 lớp).
Nhãn người dùng (nút "Đúng hook" trong giao diện, lưu ở ~/.micow/ear_labels.jsonl) được trộn vào lần huấn luyện sau.
"""
from __future__ import annotations

import glob
import json
import random
import time
from pathlib import Path

import numpy as np

from .. import paths
from .dataset import load
from .features import FPS, LAG, analyze_frames, extract, frame_features
from .nn import KINDS, WEIGHTS
from .structure import FEAT_NAMES, bar_features

CTX = 4


def _log(cb, msg):
    print(msg, flush=True)
    if cb:
        cb(msg)


def _split(files: list[str], val_frac: float = 0.15):
    files = sorted(files)
    rng = random.Random(0)
    rng.shuffle(files)
    k = max(1, int(len(files) * val_frac))
    return sorted(files[k:]), sorted(files[:k])


# ------------------------------------------------------------------ BeatTCN
def prepare_frames(files: list[str], cache: Path, log=None) -> list[str]:
    cache.mkdir(parents=True, exist_ok=True)
    out = []
    for i, p in enumerate(files):
        c = cache / (Path(p).stem + ".frames.npz")
        if not c.exists():
            y, lab = load(p)
            S, H, P, C, kb = analyze_frames(y)
            F = frame_features(S, C)
            T = len(F)
            tgt = np.zeros((T, 2), np.float32)
            for j, key in enumerate(("beats", "downbeats")):
                for t in lab[key]:
                    k = int(round((t - LAG) * FPS))
                    for d, v in ((0, 1.0), (-1, 0.5), (1, 0.5)):
                        if 0 <= k + d < T:
                            tgt[k + d, j] = max(tgt[k + d, j], v)
            np.savez_compressed(c, feats=F.astype(np.float16), tgt=tgt.astype(np.float16))
        out.append(str(c))
        if (i + 1) % 25 == 0:
            _log(log, f"đặc trưng khung {i + 1}/{len(files)}")
    return out


def train_beat(cache_files: list[str], steps: int = 3000, ch: int = 32, crop: int = 1024, batch: int = 16,
               lr: float = 2e-3, log=None) -> Path:
    import torch
    import torch.nn as nn
    torch.manual_seed(0)
    data = [(np.load(c)["feats"].astype(np.float32), np.load(c)["tgt"].astype(np.float32)) for c in cache_files]
    allf = np.concatenate([d[0] for d in data])
    mean, std = allf.mean(0), allf.std(0) + 1e-6
    dils = [1, 2, 4, 8, 16, 32]

    class TCN(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Conv1d(19, ch, 3, padding=1)
            self.blocks = nn.ModuleList([nn.Conv1d(ch, ch, 3, padding=d, dilation=d) for d in dils])
            self.drop = nn.Dropout(0.1)
            self.out = nn.Conv1d(ch, 2, 1)

        def forward(self, x):
            h = nn.functional.elu(self.inp(x))
            for b in self.blocks:
                h = h + self.drop(nn.functional.elu(b(h)))
            return self.out(h)

    net = TCN()
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    posw = torch.tensor([6.0, 20.0])[:, None]
    t0 = time.time()
    for step in range(steps):
        xb, yb = [], []
        for _ in range(batch):
            f, t = random.choice(data)
            s = random.randint(0, max(0, len(f) - crop))
            ff = (f[s:s + crop] - mean) / std
            tt = t[s:s + crop]
            if len(ff) < crop:
                ff = np.pad(ff, ((0, crop - len(ff)), (0, 0)))
                tt = np.pad(tt, ((0, crop - len(tt)), (0, 0)))
            ff = ff * np.random.uniform(0.8, 1.2, (1, ff.shape[1])) + np.random.normal(0, 0.05, ff.shape)
            xb.append(ff.T)
            yb.append(tt.T)
        x = torch.tensor(np.array(xb), dtype=torch.float32)
        y = torch.tensor(np.array(yb), dtype=torch.float32)
        logit = net(x)
        loss = nn.functional.binary_cross_entropy_with_logits(logit, y, pos_weight=posw)
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if step % 200 == 0 or step == steps - 1:
            _log(log, f"BeatTCN bước {step}/{steps} loss {loss.item():.4f} ({time.time() - t0:.0f}s)")
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    p = {"in_w": net.inp.weight, "in_b": net.inp.bias, "out_w": net.out.weight, "out_b": net.out.bias}
    for i, b in enumerate(net.blocks):
        p[f"b{i}_w"], p[f"b{i}_b"] = b.weight, b.bias
    out = WEIGHTS / "beat_tcn.npz"
    np.savez(out, dils=np.array(dils), mean=mean.astype(np.float32), std=std.astype(np.float32),
             **{k: v.detach().numpy().astype(np.float32) for k, v in p.items()})
    from .nn import beat_model
    beat_model.cache_clear()
    return out


# ------------------------------------------------------------------ BarMLP
def _bar_labels(bars: np.ndarray, sections: list[dict]) -> np.ndarray:
    """(n, 3): hook, peak, kind (theo tâm ô nhịp)."""
    n = len(bars) - 1
    lab = np.full((n, 3), -1.0, np.float32)
    for i in range(n):
        c = 0.5 * (bars[i] + bars[i + 1])
        for s in sections:
            if s["start"] <= c < s["end"]:
                lab[i] = [float(s["hook"]), float(s["peak"]), KINDS.index(s["kind"]) if s["kind"] in KINDS else -1]
                break
    return lab


def prepare_bars(files: list[str], cache: Path, log=None) -> list[str]:
    cache.mkdir(parents=True, exist_ok=True)
    out = []
    for i, p in enumerate(files):
        c = cache / (Path(p).stem + ".bars.npz")
        if not c.exists():
            y, lab = load(p)
            f = extract(y, 22050, use_model=True)
            if f.n_bars >= 6:
                feats, _ = bar_features(f)
                np.savez_compressed(c, feats=feats, lab=_bar_labels(f.bars, lab["sections"]))
        if c.exists():
            out.append(str(c))
        if (i + 1) % 25 == 0:
            _log(log, f"đặc trưng ô nhịp {i + 1}/{len(files)}")
    return out


def user_label_bars(cache: Path, log=None) -> list[str]:
    """Nhãn người dùng: hook do người nghe xác nhận trên bài thật → thêm vào dữ liệu huấn luyện BarMLP."""
    lf = paths.home() / "ear_labels.jsonl"
    if not lf.exists():
        return []
    from ..audio_io import SR, read_audio
    out = []
    cache.mkdir(parents=True, exist_ok=True)
    for line in lf.read_text(encoding="utf-8").splitlines():
        try:
            L = json.loads(line)
        except Exception:
            continue
        clip = paths.uploads() / L.get("id", "") / "clip.wav"
        if not clip.exists():
            continue
        c = cache / f"user-{L['id']}.bars.npz"
        f = extract(read_audio(clip, SR), SR)
        if f.n_bars < 6:
            continue
        feats, _ = bar_features(f)
        lab = np.full((f.n_bars, 3), -1.0, np.float32)
        lab[:, 0] = 0.0
        for i in range(f.n_bars):
            ctr = 0.5 * (f.bars[i] + f.bars[i + 1])
            if L["hook_start"] <= ctr < L["hook_end"]:
                lab[i, 0] = 1.0
            if L.get("peak_start") is not None:
                lab[i, 1] = float(L["peak_start"] <= ctr < L.get("peak_end", L["peak_start"] + 20))
        np.savez_compressed(c, feats=feats, lab=lab)
        out.append(str(c))
    if out:
        _log(log, f"thêm {len(out)} bài có nhãn của người dùng")
    return out


def train_bar(cache_files: list[str], steps: int = 4000, hidden: int = 96, lr: float = 2e-3, log=None,
              user_weight: float = 3.0) -> Path:
    import torch
    import torch.nn as nn
    from .nn import context_stack
    torch.manual_seed(0)
    X, Y, W = [], [], []
    for c in cache_files:
        d = np.load(c)
        X.append(context_stack(d["feats"], CTX))
        Y.append(d["lab"])
        W.append(np.full(len(d["lab"]), user_weight if "user-" in c else 1.0, np.float32))
    X, Y, W = np.concatenate(X), np.concatenate(Y), np.concatenate(W)
    mean, std = X.mean(0), X.std(0) + 1e-6
    Xt = torch.tensor((X - mean) / std, dtype=torch.float32)
    Yt = torch.tensor(Y, dtype=torch.float32)
    Wt = torch.tensor(W)
    din = X.shape[1]
    net = nn.Sequential(nn.Linear(din, hidden), nn.ELU(), nn.Dropout(0.15), nn.Linear(hidden, 64), nn.ELU(),
                        nn.Linear(64, 2 + len(KINDS)))
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    t0 = time.time()
    for step in range(steps):
        idx = torch.randint(0, len(Xt), (256,))
        x = Xt[idx] + 0.05 * torch.randn(256, din)
        y = Yt[idx]
        w = Wt[idx]
        o = net(x)
        loss = 0
        for j in (0, 1):
            m = y[:, j] >= 0
            if m.any():
                l = nn.functional.binary_cross_entropy_with_logits(o[m, j], y[m, j], reduction="none")
                loss = loss + (l * w[m]).mean()
        m = y[:, 2] >= 0
        if m.any():
            loss = loss + 0.5 * nn.functional.cross_entropy(o[m, 2:], y[m, 2].long())
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if step % 500 == 0 or step == steps - 1:
            _log(log, f"BarMLP bước {step}/{steps} loss {float(loss):.4f} ({time.time() - t0:.0f}s)")
    lin = [m for m in net if isinstance(m, nn.Linear)]
    out = WEIGHTS / "bar_mlp.npz"
    np.savez(out, ctx=np.array(CTX), mean=mean.astype(np.float32), std=std.astype(np.float32),
             feat_names=np.array(FEAT_NAMES),
             **{f"w{i + 1}": l.weight.detach().numpy().T.astype(np.float32) for i, l in enumerate(lin)},
             **{f"b{i + 1}": l.bias.detach().numpy().astype(np.float32) for i, l in enumerate(lin)})
    from .nn import bar_model
    bar_model.cache_clear()
    return out


# ------------------------------------------------------------------ đánh giá
def evaluate(files: list[str], use_model: bool = True, log=None) -> dict:
    from .structure import analyze_structure
    res = {"beat": [], "downbeat": [], "hook": [], "peak": [], "kind": [], "tempo": []}
    for p in files:
        y, lab = load(p)
        f = extract(y, 22050, use_model=use_model)
        r = analyze_structure(f, use_model=use_model)
        tb, td = np.array(lab["beats"]), np.array(lab["downbeats"])
        res["beat"].append(np.mean([np.min(np.abs(tb - x)) < 0.07 for x in f.beats]) if len(f.beats) else 0)
        res["downbeat"].append(np.mean([np.min(np.abs(td - x)) < 0.07 for x in f.bars[:-1]]) if f.n_bars else 0)
        ratio = f.bpm / lab["bpm"]
        res["tempo"].append(min(abs(ratio - k) for k in (0.5, 1, 2)) < 0.04)
        secs = lab["sections"]

        def frac(t0, t1, key):
            ov = sum(max(0, min(t1, s["end"]) - max(t0, s["start"])) for s in secs if s[key])
            return ov / max(1e-6, t1 - t0)
        res["hook"].append(bool(r["hook"]) and frac(r["hook"]["start"], r["hook"]["end"], "hook") >= 0.5)
        res["peak"].append(bool(r["peak"]) and frac(r["peak"]["start"], r["peak"]["end"], "peak") >= 0.5)
        ok = tot = 0
        for s in r["sections"]:
            ctr = 0.5 * (s["start"] + s["end"])
            true = next((x["kind"] for x in secs if x["start"] <= ctr < x["end"]), None)
            if true:
                tot += 1
                same = s["kind"] == true or {s["kind"], true} <= {"chorus", "drop", "postchorus"}
                ok += same
        res["kind"].append(ok / max(1, tot))
    out = {k: round(float(np.mean(v)), 3) for k, v in res.items()}
    out["n"] = len(files)
    return out


def run_all(data_dir: str | None = None, n: int = 260, beat_steps: int = 3000, bar_steps: int = 4000, log=None) -> dict:
    data = Path(data_dir) if data_dir else paths.home() / "ear_data"
    files = sorted(glob.glob(str(data / "*.npz")))
    if len(files) < n:
        from .dataset import build
        _log(log, f"Sinh dữ liệu tổng hợp có nhãn: {n} bài")
        build(data, n=n, start=1000)
        files = sorted(glob.glob(str(data / "*.npz")))
    train, val = _split(files)
    _log(log, f"{len(train)} bài huấn luyện, {len(val)} bài kiểm tra")
    base = evaluate(val, use_model=False, log=log)
    _log(log, f"Chỉ thuật toán (trước huấn luyện): {base}")
    cache = data / "cache"
    tc = prepare_frames(train, cache, log)
    train_beat(tc, beat_steps, log=log)
    bc = prepare_bars(train, cache, log) + user_label_bars(cache, log)
    train_bar(bc, bar_steps, log=log)
    after = evaluate(val, use_model=True, log=log)
    _log(log, f"Sau huấn luyện: {after}")
    report = {"train": len(train), "val": len(val), "rule_only": base, "trained": after,
              "date": time.strftime("%Y-%m-%d %H:%M")}
    (WEIGHTS / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report
