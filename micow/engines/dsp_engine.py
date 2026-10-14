"""Engine Micow Beat (có sẵn, chạy CPU, không cần tải mô hình)."""
from __future__ import annotations

from .. import paths
from ..dsp.render import midi_tracks, render
from ..lyrics import to_lrc
from ..midi import write_midi
from ..outputs import save_result
from .base import Engine, GenRequest, blueprint_for


class DSPEngine(Engine):
    id = "micow-dsp"
    name = "Micow Beat"
    license = "MIT (mã Micow) – nhạc tạo ra thuộc về bạn"
    description = ("Có sẵn, chạy trên CPU trong vài giây. Tự soạn hoà âm, trống, bass, hook theo 12 thể loại; "
                   "dùng clip của bạn làm vòng lặp / cắt lát / bộ trống; bài có lời được hát bằng giọng mẫu "
                   "(ngân nguyên âm theo giai điệu) và xuất MIDI kèm lời + LRC.")
    vocals = False
    needs_install = False

    def generate(self, job, req: GenRequest, clips: list[dict]) -> dict:
        job.update(0.03, "Lập bản thiết kế bài")
        bp = blueprint_for(req, clips)
        if req.mode == "song" and not req.lyrics.strip():
            bp.notes.append("Không có lời: tạo bản không lời theo cấu trúc bài hát")
        use_clips = [c for c in clips if c.get("use") in ("loop", "chop", "kit", "hook")]

        def prog(p, m):
            if job.cancel.is_set():
                raise RuntimeError("Đã huỷ")
            job.update(0.05 + 0.85 * p, m)

        res = render(bp, use_clips, gender=req.gender, guide_vocal=req.guide_vocal, progress=prog)
        folder = paths.library() / job.id
        lrc = to_lrc(res.lrc, bp.title) if res.lrc else None
        meta = {"id": job.id, "title": bp.title, "mode": bp.mode, "engine": self.id, "engine_name": self.name,
                "request": req.to_dict(), "bpm": bp.bpm, "key": bp.key.to_dict(), "genre": bp.style.genre,
                "genre_name": bp.style.preset["name"], "stats": res.stats, "notes": bp.notes,
                "sections": bp.to_dict()["sections"], "created": job.created}
        if bp.mode == "capcut":
            meta["capcut"] = {"duration": bp.target_duration, "peak_at": req.peak_at, "loop": bp.loop,
                              "mode": "generated"}
        job.update(0.93, "Lưu tệp (WAV, stem, MIDI, LRC)")
        out = save_result(folder, meta, res.mix, res.stems, lrc,
                          lambda p: write_midi(p, bp.bpm, midi_tracks(res, bp), bp.key.tonic, bp.key.is_minor),
                          bp.to_dict())
        if bp.mode == "capcut":
            from ..ear.capcut import blueprint_markers, finalize
            out = finalize(folder, out, bp.title, blueprint_markers(bp))
        return out
