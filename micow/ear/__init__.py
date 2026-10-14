"""Micow Ear – "tai" của Micow: nghe nhiều bài, tìm cấu trúc, hook và đoạn peak (để cắt nhạc CapCut).

    from micow.ear import listen
    r = listen(audio, sr)   # {"bpm", "key", "beats", "bars", "sections", "hook", "candidates", "peak", ...}
"""
from __future__ import annotations

import json
import time

import numpy as np

EAR_VERSION = 1


def listen(x: np.ndarray, sr: int, use_model: bool = True) -> dict:
    from .features import extract
    from .structure import analyze_structure
    t0 = time.time()
    f = extract(x, sr, use_model=use_model)
    r = analyze_structure(f, use_model=use_model)
    r.update({"version": EAR_VERSION, "duration": round(f.duration, 3), "bpm": f.bpm, "key": f.key,
              "beats": [round(float(b), 3) for b in f.beats], "beat_method": f.method,
              "seconds": round(time.time() - t0, 2)})
    return r


def listen_upload(uid: str, force: bool = False) -> dict:
    """Phân tích một clip đã tải lên (lưu kết quả ở uploads/<id>/ear.json)."""
    from .. import paths
    from ..audio_io import SR, read_audio
    d = paths.uploads() / uid
    cache = d / "ear.json"
    if cache.exists() and not force:
        r = json.loads(cache.read_text(encoding="utf-8"))
        if r.get("version") == EAR_VERSION:
            return r
    r = listen(read_audio(d / "clip.wav", SR), SR)
    cache.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    return r


def save_label(uid: str, hook_start: float, hook_end: float, peak_start: float | None = None,
               peak_end: float | None = None) -> dict:
    """Người dùng xác nhận hook (và peak) đúng → dữ liệu cho lần huấn luyện sau (micow train ear)."""
    from .. import paths
    rec = {"id": uid, "hook_start": float(hook_start), "hook_end": float(hook_end), "time": time.time()}
    if peak_start is not None:
        rec.update(peak_start=float(peak_start), peak_end=float(peak_end if peak_end is not None else peak_start + 15))
    with open(paths.home() / "ear_labels.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec
