"""Engine Micow-LM – mô hình riêng của Micow (kiến trúc suy ra từ Suno), chạy checkpoint bạn tự huấn luyện.

Checkpoint đặt ở ~/.micow/models/micow-lm/<tên>/{lm.pt, codec.pt}. Chưa có checkpoint thì engine báo
"chưa sẵn sàng" và hướng dẫn `micow data synth` → `micow train codec|tokenize|lm`.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from .. import paths, system
from ..audio_io import SR, resample, to_stereo
from ..dsp import master as mastering
from ..lyrics import parse_lyrics, to_engine_lyrics
from ..outputs import save_result
from .base import Engine, GenRequest, blueprint_for

_RUNNERS: dict[str, object] = {}
_LOCK = threading.Lock()


def model_root() -> Path:
    d = paths.models() / "micow-lm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_models() -> list[dict]:
    out = []
    for d in sorted(model_root().iterdir()):
        if (d / "lm.pt").exists():
            size = sum(f.stat().st_size for f in d.glob("*.pt"))
            out.append({"name": d.name, "path": str(d), "size_mb": round(size / 2 ** 20, 1),
                        "codec": (d / "codec.pt").exists()})
    return out


class MicowLMEngine(Engine):
    id = "micow-lm"
    name = "Micow-LM"
    license = "MIT (mã + trọng số do bạn huấn luyện)"
    description = ("Mô hình riêng của Micow theo kiến trúc suy ra từ Suno: codec RVQ + transformer tự hồi quy "
                   "trên token âm thanh, điều kiện bằng phong cách, lời (byte UTF-8) và clip tham chiếu; "
                   "nối dài clip như Suno Extend. Cần PyTorch và checkpoint tự huấn luyện (micow train …).")
    vocals = True

    def status(self) -> dict:
        if not system.torch_available():
            return {"installed": False, "ready": False, "models": [],
                    "message": "Cần PyTorch: pip install torch (hoặc chạy bộ cài với tuỳ chọn --with-torch)"}
        ms = list_models()
        if not ms:
            return {"installed": True, "ready": False, "models": [],
                    "message": "Chưa có checkpoint. Huấn luyện: micow data synth → micow train codec/tokenize/lm"}
        return {"installed": True, "ready": True, "models": ms, "message": f"{len(ms)} checkpoint sẵn sàng"}

    def install(self, job) -> dict:
        import subprocess
        import sys
        job.update(0.1, "Cài PyTorch (có thể mất vài phút)")
        subprocess.run([sys.executable, "-m", "pip", "install", "torch"], check=True)
        return {"message": "Đã cài PyTorch"}

    def runner(self, name: str | None):
        from ..model.generate import MicowLMRunner
        ms = list_models()
        if not ms:
            raise RuntimeError("Chưa có checkpoint Micow-LM nào trong ~/.micow/models/micow-lm/")
        pick = next((m for m in ms if m["name"] == name), ms[0])
        with _LOCK:
            if pick["path"] not in _RUNNERS:
                _RUNNERS[pick["path"]] = MicowLMRunner(pick["path"])
            return _RUNNERS[pick["path"]], pick["name"]

    def generate(self, job, req: GenRequest, clips: list[dict]) -> dict:
        opts = req.options or {}
        job.update(0.03, "Nạp Micow-LM")
        run, mname = self.runner(opts.get("model"))
        bp = blueprint_for(req, clips)
        instrumental = req.mode == "beat" or not req.lyrics.strip()
        lyrics = "" if instrumental else to_engine_lyrics(parse_lyrics(req.lyrics))
        dur = float(req.duration or min(240.0, bp.duration))
        ref = prompt = None
        for c in clips:
            mono = resample(c["audio"].mean(axis=1), SR, run.sr)
            if c["use"] in ("complete", "loop", "cover") and prompt is None:
                prompt = mono[: int(min(len(mono) / run.sr, dur * 0.5) * run.sr)]  # nối dài từ clip
            elif ref is None:
                ref = mono
        job.update(0.08, "Sinh token âm thanh" + (" (nối dài từ clip)" if prompt is not None else ""))
        wav = run.generate(bp.style.caption(instrumental), lyrics, bp.bpm, bp.key.name(), dur, ref, prompt,
                           cfg_scale=float(opts.get("cfg", 3.0)), temperature=float(opts.get("temperature", 1.0)),
                           top_k=int(opts.get("top_k", 250)), seed=req.seed,
                           progress=lambda p: job.update(0.08 + 0.8 * p, f"Sinh token {int(p * 100)}%"),
                           plan=bp.to_dict()["sections"])
        audio = to_stereo(resample(wav.astype(np.float32), run.sr, SR))
        audio, mst = mastering.master(audio, bp.style.genre)
        meta = {"id": job.id, "title": bp.title, "mode": bp.mode, "engine": self.id, "engine_name": f"{self.name} · {mname}",
                "request": req.to_dict(), "bpm": bp.bpm, "key": bp.key.to_dict(), "genre": bp.style.genre,
                "genre_name": bp.style.preset["name"], "stats": mst, "notes": bp.notes, "sections": [],
                "created": job.created}
        return save_result(paths.library() / job.id, meta, audio, None, None, None, bp.to_dict())
