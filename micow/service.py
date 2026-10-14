"""Lớp dịch vụ dùng chung cho máy chủ HTTP và dòng lệnh: tạo nhạc, cài engine, thư viện."""
from __future__ import annotations

import json
import re
import shutil

from . import paths
from .engines import ENGINES, GenRequest, get, load_clip
from .jobs import QUEUE, Job


def start_generate(params: dict) -> Job:
    req = GenRequest.from_dict(params)
    eng = get(req.engine)
    if req.mode not in eng.modes:
        raise ValueError(f"{eng.name} không hỗ trợ chế độ {req.mode}")

    def work(job: Job):
        clips = []
        for c in req.clips:
            clip = load_clip(c["id"])
            clip["use"] = c.get("use", "style")
            clips.append(clip)
        return eng.generate(job, req, clips)

    return QUEUE.submit("generate", req.to_dict(), work)


def start_install(engine_id: str, options: dict | None = None) -> Job:
    eng = get(engine_id)
    return QUEUE.submit("install", {"engine": engine_id, **(options or {})}, lambda job: eng.install(job))


def engines_info() -> list[dict]:
    out = []
    for e in ENGINES.values():
        try:
            out.append(e.info())
        except Exception as ex:  # noqa: BLE001
            out.append({"id": e.id, "name": e.name, "ready": False, "message": f"Lỗi: {ex}"})
    return out


def library(limit: int = 200) -> list[dict]:
    items = []
    for d in sorted(paths.library().iterdir(), reverse=True):
        m = d / "meta.json"
        if m.exists():
            try:
                meta = json.loads(m.read_text(encoding="utf-8"))
                items.append(meta)
            except Exception:
                continue
        if len(items) >= limit:
            break
    return items


def library_item(item_id: str) -> dict | None:
    if not re.fullmatch(r"[\w\-]+", item_id or ""):
        return None
    m = paths.library() / item_id / "meta.json"
    return json.loads(m.read_text(encoding="utf-8")) if m.exists() else None


def delete_item(item_id: str) -> bool:
    if not re.fullmatch(r"[\w\-]+", item_id or ""):
        return False
    d = paths.library() / item_id
    if d.is_dir():
        shutil.rmtree(d)
        return True
    return False


def rename_item(item_id: str, title: str) -> dict | None:
    meta = library_item(item_id)
    if meta is None:
        return None
    meta["title"] = title.strip()[:120] or meta["title"]
    (paths.library() / item_id / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta
