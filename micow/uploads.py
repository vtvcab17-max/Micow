"""Nhận đoạn nhạc người dùng đưa vào: chuẩn hoá về WAV 44,1 kHz stereo, phân tích, lưu ~/.micow/uploads/<id>/."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from . import paths
from .analysis import analyze
from .audio_io import SR, read_audio, write_wav
from .outputs import peaks

MAX_SECONDS = 8 * 60  # như Suno: tối đa 8 phút mỗi clip


def add_upload(data: bytes, name: str = "clip.wav") -> dict:
    uid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = paths.uploads() / uid
    d.mkdir(parents=True)
    safe = re.sub(r"[^\w.\- ]+", "_", Path(name).name)[:80] or "clip"
    suffix = Path(safe).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=d) as f:
        f.write(data)
        tmp = Path(f.name)
    try:
        x = read_audio(tmp, SR)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise ValueError(f"Không đọc được tệp âm thanh '{safe}': {e}") from e
    finally:
        tmp.unlink(missing_ok=True)
    x = x[: MAX_SECONDS * SR]
    write_wav(d / "clip.wav", x, SR)
    a = analyze(x, SR)
    meta = {"id": uid, "name": safe, "duration": round(len(x) / SR, 2), "analysis": a, "peaks": peaks(x, 300),
            "created": time.time()}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def add_upload_file(path: str | Path) -> dict:
    p = Path(path)
    return add_upload(p.read_bytes(), p.name)


def list_uploads() -> list[dict]:
    out = []
    for d in sorted(paths.uploads().iterdir(), reverse=True):
        m = d / "meta.json"
        if m.exists():
            try:
                meta = json.loads(m.read_text(encoding="utf-8"))
                meta.pop("peaks", None)
                out.append(meta)
            except Exception:
                pass
    return out


def get_upload(uid: str) -> dict | None:
    if not re.fullmatch(r"[\w\-]+", uid or ""):
        return None
    m = paths.uploads() / uid / "meta.json"
    return json.loads(m.read_text(encoding="utf-8")) if m.exists() else None


def delete_upload(uid: str) -> bool:
    if not re.fullmatch(r"[\w\-]+", uid or ""):
        return False
    d = paths.uploads() / uid
    if d.is_dir():
        shutil.rmtree(d)
        return True
    return False
