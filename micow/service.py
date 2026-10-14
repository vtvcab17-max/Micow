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
            if clip["use"] == "hook":
                from .ear import listen_upload
                job.update(0.02, f"Micow Ear đang nghe {clip['name']} để tìm hook")
                clip["ear"] = listen_upload(c["id"])
            clips.append(clip)
        if req.mode == "capcut" and eng.id != "micow-dsp":
            return _capcut_via_cut(job, eng, req, clips)
        return eng.generate(job, req, clips)

    return QUEUE.submit("generate", req.to_dict(), work)


def _capcut_via_cut(job: Job, eng, req: GenRequest, clips: list[dict]) -> dict:
    """Engine AI (ACE-Step, Micow-LM): tạo bài đầy đủ rồi để Micow Ear tìm hook/peak và cắt đúng thời lượng."""
    import copy
    from .audio_io import SR, read_audio
    from .ear import listen
    from .ear.capcut import plan_cut, render_cut, save_cut
    dur = float(req.duration or 15)
    full = copy.copy(req)
    full.mode = "song" if req.lyrics.strip() else "beat"
    full.duration = max(45.0, min(240.0, dur * 3))
    meta = eng.generate(job, full, clips)
    src = paths.library() / job.id
    x = read_audio(src / meta["files"]["wav"], SR)
    job.update(0.9, "Micow Ear tìm hook / peak trong bài vừa tạo")
    ear = listen(x, SR)
    mode = "peak_at" if req.peak_at is not None else "hook"
    plan = plan_cut(ear, len(x) / SR, dur, mode, req.peak_at)
    y = render_cut(x, plan, loop=req.loop)
    for f in src.iterdir():
        if f.is_file():
            f.unlink()
    meta2 = {k: v for k, v in meta.items() if k not in ("files", "peaks", "duration", "finished")}
    meta2.update(mode="capcut", title=meta["title"] + " · CapCut", request=req.to_dict(),
                 notes=meta.get("notes", []) + [f"Tạo bài {full.duration:.0f} giây rồi cắt {plan['mode']} {dur:g} giây"])
    return save_cut(src, meta2["title"], y, plan, ear, meta2)


def start_cut(params: dict) -> Job:
    """Cắt nhạc CapCut từ một clip đã tải lên (bài có sẵn)."""
    uid = params.get("id", "")
    dur = float(params.get("duration") or 15)
    mode = params.get("mode") or "hook"
    peak_at = params.get("peak_at")
    peak_at = float(peak_at) if peak_at not in (None, "") else None
    cand = int(params.get("candidate") or 0)
    loop = bool(params.get("loop"))

    def work(job: Job):
        from .audio_io import SR, read_audio
        from .ear import listen_upload
        from .ear.capcut import plan_cut, render_cut, save_cut
        from .uploads import get_upload
        up = get_upload(uid)
        if not up:
            raise FileNotFoundError("Không thấy bài đã tải lên")
        job.update(0.1, "Micow Ear đang nghe bài")
        ear = listen_upload(uid)
        x = read_audio(paths.uploads() / uid / "clip.wav", SR)
        job.update(0.6, "Cắt đúng nhịp")
        plan = plan_cut(ear, len(x) / SR, dur, mode, peak_at, cand, bool(params.get("snap_end")))
        y = render_cut(x, plan, loop=loop)
        name = up.get("name", "clip").rsplit(".", 1)[0]
        label = {"hook": "Hook", "peak": "Peak", "peak_at": f"Drop@{peak_at:g}s" if peak_at is not None else "Drop"}.get(mode, mode)
        title = f"{name} · {label} {dur:g}s"
        meta = {"id": job.id, "title": title, "mode": "capcut", "engine": "micow-ear", "engine_name": "Micow Ear · cắt",
                "request": dict(params), "bpm": ear.get("bpm"), "key": ear.get("key"), "genre": "", "genre_name": "CapCut",
                "source": {"id": uid, "name": up.get("name"), "start": plan["start"], "end": plan["end"]},
                "notes": [plan["note"]] if plan.get("note") else [], "sections": [], "created": job.created}
        return save_cut(paths.library() / job.id, title, y, plan, ear, meta)

    return QUEUE.submit("generate", {"cut": uid, "mode": mode, "duration": dur}, work)


def start_listen(ids: list[str]) -> Job:
    """Micow Ear nghe nhiều bài (theo hàng đợi), trả kết quả từng bài."""
    def work(job: Job):
        from .ear import listen_upload
        out = {}
        for i, uid in enumerate(ids):
            job.update(i / max(1, len(ids)), f"Đang nghe bài {i + 1}/{len(ids)}")
            try:
                out[uid] = listen_upload(uid)
            except Exception as e:  # noqa: BLE001
                out[uid] = {"error": str(e)}
        return {"results": out}
    return QUEUE.submit("listen", {"ids": ids}, work)


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
