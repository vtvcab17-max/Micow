"""Ghi kết quả một lần tạo vào thư viện: mix (wav/mp3), stem, MIDI, LRC, bản thiết kế, sóng âm cho giao diện."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .audio_io import SR, have_ffmpeg, write_mp3, write_wav


def peaks(x: np.ndarray, n: int = 900) -> list[float]:
    m = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    if len(m) < n:
        return [round(float(v), 3) for v in m]
    k = len(m) // n
    return [round(float(v), 3) for v in m[: k * n].reshape(n, k).max(axis=1)]


def save_result(folder: Path, meta: dict, mix: np.ndarray, stems: dict[str, np.ndarray] | None = None,
                lrc: str | None = None, midi_writer=None, blueprint: dict | None = None,
                mp3: bool = True, sr: int = SR) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    write_wav(folder / "mix.wav", mix, sr)
    files["wav"] = "mix.wav"
    if mp3 and have_ffmpeg():
        try:
            write_mp3(folder / "mix.mp3", folder / "mix.wav")
            files["mp3"] = "mix.mp3"
        except Exception:
            pass
    if stems:
        (folder / "stems").mkdir(exist_ok=True)
        files["stems"] = {}
        for name, x in stems.items():
            write_wav(folder / "stems" / f"{name}.wav", x, sr)
            files["stems"][name] = f"stems/{name}.wav"
    if midi_writer is not None:
        midi_writer(folder / "song.mid")
        files["midi"] = "song.mid"
    if lrc:
        (folder / "lyrics.lrc").write_text(lrc, encoding="utf-8")
        files["lrc"] = "lyrics.lrc"
    if blueprint:
        (folder / "blueprint.json").write_text(json.dumps(blueprint, ensure_ascii=False, indent=1), encoding="utf-8")
        files["blueprint"] = "blueprint.json"
    meta = dict(meta)
    meta.update({"files": files, "duration": round(len(mix) / sr, 2), "peaks": peaks(mix),
                 "finished": time.time()})
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta
