"""Giao diện chung cho các engine sinh nhạc và yêu cầu tạo nhạc (GenRequest)."""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

import numpy as np

from .. import paths
from ..audio_io import read_audio
from ..planner import Blueprint, make_blueprint

CLIP_USES = {"style", "loop", "chop", "kit", "cover", "complete"}


@dataclass
class GenRequest:
    mode: str = "song"                  # beat | song
    engine: str = "micow-dsp"
    style: str = ""
    genre: str | None = None
    title: str = ""
    lyrics: str = ""
    duration: float | None = None
    bpm: int | None = None
    key: str | None = None
    energy: float | None = None
    seed: int | None = None
    gender: str | None = None           # female | male
    guide_vocal: bool = True
    clips: list[dict] = field(default_factory=list)   # [{"id": upload_id, "use": "style|loop|chop|kit|cover|complete"}]
    options: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "GenRequest":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        r = cls(**known)
        if r.mode not in ("beat", "song"):
            r.mode = "song"
        if r.seed is None or r.seed == "" or (isinstance(r.seed, (int, float)) and r.seed < 0):
            r.seed = random.randint(0, 999_999)
        r.seed = int(r.seed)
        for k in ("bpm",):
            v = getattr(r, k)
            setattr(r, k, int(v) if v not in (None, "", 0) else None)
        r.duration = float(r.duration) if r.duration not in (None, "", 0) else None
        r.clips = [c for c in (r.clips or []) if isinstance(c, dict) and c.get("id")]
        for c in r.clips:
            if c.get("use") not in CLIP_USES:
                c["use"] = "style"
        return r

    def to_dict(self) -> dict:
        return asdict(self)


def load_clip(clip_id: str) -> dict:
    d = paths.uploads() / clip_id
    if not d.is_dir() or "/" in clip_id or ".." in clip_id:
        raise FileNotFoundError(f"Không thấy clip {clip_id}")
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    return {"id": clip_id, "audio": read_audio(d / "clip.wav"), "analysis": meta.get("analysis", {}),
            "name": meta.get("name", clip_id), "path": str(d / "clip.wav")}


def blueprint_for(req: GenRequest, clips: list[dict]) -> Blueprint:
    ref = None
    for c in clips:  # clip đầu tiên dùng để học phong cách (trừ cover/complete)
        if c.get("use") in ("style", "loop", "chop", "kit") and c.get("analysis", {}).get("bpm"):
            ref = c["analysis"]
            break
    return make_blueprint(req.mode, req.style, req.lyrics, req.title, req.genre, req.bpm, req.key,
                          req.duration, req.energy, req.seed, ref)


class Engine:
    id = "base"
    name = "Engine"
    modes = ("beat", "song")
    license = ""
    description = ""
    vocals = False          # có giọng hát thật không
    needs_install = True

    def status(self) -> dict:
        return {"installed": True, "ready": True, "message": ""}

    def info(self) -> dict:
        st = self.status()
        return {"id": self.id, "name": self.name, "modes": list(self.modes), "license": self.license,
                "description": self.description, "vocals": self.vocals, "needs_install": self.needs_install, **st}

    def install(self, job) -> dict:
        return {"message": "Không cần cài"}

    def generate(self, job, req: GenRequest, clips: list[dict]) -> dict:
        raise NotImplementedError


def np_seed(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)
