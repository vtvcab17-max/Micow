"""Huấn luyện Micow: (1) codec  →  (2) token hoá dữ liệu  →  (3) Micow-LM.

  micow train codec    --data data/manifest.jsonl --out ~/.micow/models/micow-lm/my/codec.pt
  micow train tokenize --data data/manifest.jsonl --codec .../codec.pt --out data/tokens
  micow train lm       --tokens data/tokens --out ~/.micow/models/micow-lm/my/lm.pt --preset small

Mỗi bước lưu checkpoint định kỳ và tiếp tục được (--resume).
"""
from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from .codec import CodecConfig, MicowCodec, STFTDiscriminator, load_codec, stft_loss
from .data import load_mono, lyrics_in_window, read_manifest
from .lm import LMConfig, MicowLM, save_lm
from .tokenizer import encode_text, meta_string


def pick_device(pref: str = "auto") -> str:
    if pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _lr(step, total, base, warm=500):
    if step < warm:
        return base * (step + 1) / warm
    p = (step - warm) / max(1, total - warm)
    return base * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, p))))


def _log(cb, msg):
    print(msg, flush=True)
    if cb:
        cb(msg)


# ---------------------------------------------------------------- codec
def train_codec(data: str, out: str, preset: str = "default", steps: int = 100_000, batch: int = 8,
                seconds: float = 1.0, lr: float = 3e-4, adv: bool = True, device: str = "auto",
                resume: bool = False, log=None, every: int = 1000) -> Path:
    dev = pick_device(device)
    cfg = CodecConfig.tiny() if preset == "tiny" else CodecConfig()
    items, base = read_manifest(data)
    _log(log, f"Nạp {len(items)} tệp âm thanh @ {cfg.sample_rate} Hz")
    wavs = [load_mono(base / it["audio"], cfg.sample_rate) for it in items]
    wavs = [w for w in wavs if len(w) > cfg.sample_rate * seconds]
    if not wavs:
        raise RuntimeError("Không có tệp âm thanh đủ dài")
    model = MicowCodec(cfg).to(dev)
    disc = STFTDiscriminator().to(dev) if adv else None
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.8, 0.99))
    optd = torch.optim.AdamW(disc.parameters(), lr=lr, betas=(0.8, 0.99)) if disc else None
    out_p = Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    step0 = 0
    if resume and out_p.exists():
        ck = torch.load(out_p, map_location=dev, weights_only=False)
        model.load_state_dict(ck["state"])
        step0 = ck.get("step", 0)
    L = int(cfg.sample_rate * seconds)
    t0 = time.time()
    for step in range(step0, steps):
        x = []
        for _ in range(batch):
            w = random.choice(wavs)
            i = random.randint(0, len(w) - L)
            seg = w[i:i + L] * random.uniform(0.5, 1.0)
            x.append(torch.from_numpy(seg.copy()))
        x = torch.stack(x)[:, None].to(dev)
        for g in opt.param_groups:
            g["lr"] = _lr(step, steps, lr)
        n_q = random.randint(1, cfg.n_q) if random.random() < 0.5 else cfg.n_q  # quantizer dropout
        y, _, commit = model(x, n_q)
        rec = F.l1_loss(y, x) + stft_loss(y, x)
        loss = rec + 0.25 * commit
        if disc is not None and step > 2000:
            outs, fy = disc(y)
            _, fx = disc(x)
            g_adv = sum(F.relu(1 - o).mean() for o in outs) / len(outs)
            feat = sum(F.l1_loss(a, b.detach()) for fa, fb in zip(fy, fx) for a, b in zip(fa, fb)) / len(outs)
            loss = loss + 0.5 * g_adv + 1.0 * feat
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if disc is not None and step > 2000:
            ro, _ = disc(x)
            fo, _ = disc(y.detach())
            d_loss = sum(F.relu(1 - r).mean() + F.relu(1 + f).mean() for r, f in zip(ro, fo)) / len(ro)
            optd.zero_grad()
            d_loss.backward()
            optd.step()
        if step % 50 == 0:
            _log(log, f"codec bước {step}/{steps} loss={loss.item():.4f} rec={rec.item():.4f} ({time.time() - t0:.0f}s)")
        if (step + 1) % every == 0 or step == steps - 1:
            torch.save({"config": cfg.to_dict(), "state": model.state_dict(), "kind": "micow-codec", "step": step + 1}, out_p)
    return out_p


# ---------------------------------------------------------------- tokenize
@torch.no_grad()
def tokenize(data: str, codec_path: str, out: str, device: str = "auto", log=None) -> Path:
    dev = pick_device(device)
    codec = load_codec(codec_path, dev)
    items, base = read_manifest(data)
    od = Path(out)
    od.mkdir(parents=True, exist_ok=True)
    index = []
    for i, it in enumerate(items):
        w = load_mono(base / it["audio"], codec.sample_rate)
        chunks = []
        step = codec.sample_rate * 30
        for s in range(0, len(w), step):  # mã hoá từng 30 giây cho đỡ tốn bộ nhớ
            x = torch.from_numpy(w[s:s + step].copy())[None, None].to(dev)
            chunks.append(codec.encode(x)[0].cpu())
        codes = torch.cat(chunks, 1).to(torch.int16)
        name = f"{i:06d}.pt"
        torch.save(codes, od / name)
        rec = dict(it)
        rec.update({"tokens": name, "frames": int(codes.shape[1]), "base": str(base)})
        index.append(rec)
        if i % 10 == 0:
            _log(log, f"token hoá {i + 1}/{len(items)}")
    meta = {"codec": str(Path(codec_path).resolve()), "frame_rate": codec.frame_rate, "n_q": codec.n_q,
            "card": codec.codebook_size, "sample_rate": codec.sample_rate, "items": index}
    (od / "index.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return od / "index.json"


# ---------------------------------------------------------------- LM
def train_lm(tokens: str, out: str, preset: str = "small", steps: int = 200_000, batch: int = 8,
             window_s: float | None = None, lr: float = 3e-4, device: str = "auto", resume: bool = False,
             log=None, every: int = 2000) -> Path:
    dev = pick_device(device)
    meta = json.loads((Path(tokens) / "index.json").read_text(encoding="utf-8"))
    fr = meta["frame_rate"]
    cfg = LMConfig.preset(preset, n_q=meta["n_q"], card=meta["card"], frame_rate=fr, sample_rate=meta["sample_rate"])
    if window_s:
        cfg.max_audio = int(window_s * fr)
    items = meta["items"]
    data = [torch.load(Path(tokens) / it["tokens"]).long() for it in items]
    model = MicowLM(cfg).to(dev)
    _log(log, f"Micow-LM {preset}: {model.n_params() / 1e6:.1f}M tham số, {len(items)} bài, cửa sổ {cfg.max_audio} khung")
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.1)
    out_p = Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    step0 = 0
    if resume and out_p.exists():
        ck = torch.load(out_p, map_location=dev, weights_only=False)
        model.load_state_dict(ck["state"])
        step0 = ck.get("step", 0)
    use_amp = dev == "cuda"
    W = cfg.max_audio
    t0 = time.time()
    model.train()
    for step in range(step0, steps):
        texts, codes, refs = [], [], []
        Tb = min(W, min(d.shape[1] for d in data))
        for _ in range(batch):
            j = random.randrange(len(data))
            d, it = data[j], items[j]
            T = d.shape[1]
            s = random.randint(0, max(0, T - Tb))
            crop = d[:, s:s + Tb]
            t_start, t_end = s / fr, (s + Tb) / fr
            lyr = lyrics_in_window(it, Path(it.get("base", ".")), t_start, t_end)
            meta_s = meta_string(it.get("bpm"), it.get("key"), T / fr, t_start)
            texts.append(encode_text(it.get("style", ""), lyr, meta_s, cfg.max_text))
            codes.append(crop)
            # clip tham chiếu: lấy từ phần KHÁC của cùng bài để học "phong cách" chứ không chép nội dung
            R = min(cfg.max_ref, T // 3)
            if R > 10 and T > Tb + R:
                rs = random.choice([random.randint(0, max(0, s - R)), random.randint(min(T - R, s + Tb), T - R)])
                refs.append(d[:, rs:rs + R])
            else:
                refs.append(None)
        codes_t = torch.stack(codes).to(dev)
        for g in opt.param_groups:
            g["lr"] = _lr(step, steps, lr, warm=min(2000, steps // 10 + 1))
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
            loss, parts = model(texts, codes_t, refs)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 25 == 0:
            _log(log, f"lm bước {step}/{steps} loss={loss.item():.4f} [{', '.join(f'{p:.2f}' for p in parts)}] ({time.time() - t0:.0f}s)")
        if (step + 1) % every == 0 or step == steps - 1:
            save_lm(model, out_p, {"step": step + 1, "codec": meta["codec"]})
    return out_p
