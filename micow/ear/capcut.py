"""Cắt nhạc cho CapCut / TikTok / Reels từ bài có sẵn, dựa trên phân tích của Micow Ear.

Chế độ:
  hook     – bắt đầu đúng đầu ô nhịp của hook (nghe là "dính" ngay giây đầu)
  peak     – bắt đầu ở cú drop / đoạn cao trào
  peak_at  – đặt cú drop rơi ĐÚNG giây X của video (vd. giây 7 lúc chuyển cảnh)
Đoạn cắt kết thúc ở đầu ô nhịp gần nhất với thời lượng mong muốn; thiếu nhạc thì lặp hook theo ô nhịp.
Tuỳ chọn "vòng lặp liền mạch": cuối đoạn hoà vào đầu đoạn, phát lặp không bị giật.
Xuất kèm mốc nhịp (CSV/JSON) để cắt cảnh theo nhịp, và tệp .bravin.json để mở thẳng trong Bravin.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np

from .. import __version__
from ..audio_io import SR
from ..dsp import fx
from ..dsp import master as M


def plan_cut(ear: dict, total: float, duration: float, mode: str = "hook", peak_at: float | None = None,
             candidate: int = 0, snap_end: bool = False) -> dict:
    """snap_end=False (mặc định): dài ĐÚNG `duration` giây như mẫu CapCut; True: kết thúc ở đầu ô nhịp gần nhất."""
    bars = np.array(ear["bars"])
    beats = np.array(ear.get("beats") or [])
    cands = ear.get("candidates") or ([ear["hook"]] if ear.get("hook") else [])
    hook = cands[min(candidate, len(cands) - 1)] if cands else None
    peak = ear.get("peak")
    bar_s = float(ear.get("bar_seconds") or (np.median(np.diff(bars)) if len(bars) > 1 else 2.0))
    note = ""
    if mode == "peak_at" and peak and peak_at is not None:
        start = float(peak["start"]) - float(peak_at)
        anchor = float(peak["start"])
        if start < 0:  # không đủ nhạc trước drop: lùi tối đa có thể
            note = f"Bài chỉ có {peak['start']:.1f} giây trước drop – drop sẽ ở giây {peak['start']:.1f}"
            start = 0.0
    elif mode == "peak" and peak:
        start = anchor = float(peak["start"])
    else:
        if hook is None:
            hook = {"start": float(bars[0]) if len(bars) else 0.0}
        start = anchor = float(hook["start"])
    # điểm kết thúc: đầu ô nhịp gần start+duration nhất (cho phép lệch nửa ô nhịp), nếu không thì cắt chính xác
    want = start + duration
    later = bars[bars > start + 0.5 * duration]
    end = want
    if snap_end and len(later):
        k = int(np.argmin(np.abs(later - want)))
        if abs(later[k] - want) <= 0.5 * bar_s:
            end = float(later[k])
    if end > total:
        end = want  # sẽ lặp hook để đủ thời lượng
    loop_from = loop_to = None
    if end > total:
        h = hook or {"start": start, "end": min(total, start + 4 * bar_s)}
        loop_from, loop_to = float(h["start"]), float(h.get("end", min(total, h["start"] + 8 * bar_s)))
    return {"mode": mode, "start": round(start, 4), "end": round(end, 4), "anchor": round(anchor, 4),
            "duration": round(end - start, 4), "loop_from": loop_from, "loop_to": loop_to, "note": note,
            "beats": [round(float(b), 4) for b in beats if start <= b < end],
            "downbeats": [round(float(b), 4) for b in bars if start <= b < end]}


def _xfade(a: np.ndarray, b: np.ndarray, n: int) -> np.ndarray:
    n = min(n, len(a), len(b))
    if n <= 0:
        return np.concatenate([a, b])
    r = np.linspace(0, 1, n)[:, None]
    return np.concatenate([a[:-n], a[-n:] * np.cos(r * np.pi / 2) + b[:n] * np.sin(r * np.pi / 2), b[n:]])


def render_cut(x: np.ndarray, plan: dict, loop: bool = False, fade_out: float | None = None,
               target_lufs: float = -14.0) -> np.ndarray:
    total = len(x) / SR
    s, e = plan["start"], plan["end"]
    xf = int(0.012 * SR)
    seg = x[int(s * SR): int(min(e, total) * SR)].copy()
    if e > total and plan.get("loop_from") is not None:  # lặp hook theo ô nhịp cho đủ thời lượng
        lp = x[int(plan["loop_from"] * SR): int(plan["loop_to"] * SR)]
        while len(seg) < int((e - s) * SR) and len(lp) > xf * 4:
            seg = _xfade(seg, lp, xf)
    seg = seg[: int((e - s) * SR)]
    if loop:
        # vòng lặp liền mạch: lấy thêm 1 phách sau điểm cuối, hoà vào đầu đoạn
        tail_n = int(min(0.5, (e - s) / 8) * SR)
        extra = x[int(e * SR): int(e * SR) + tail_n] if e < total else seg[:tail_n] * 0
        if len(extra) == tail_n and tail_n > 0:
            r = np.linspace(0, 1, tail_n)[:, None]
            seg[:tail_n] = seg[:tail_n] * np.sin(r * np.pi / 2) + extra * np.cos(r * np.pi / 2)
    else:
        fin = 0.01 if plan["mode"] != "peak_at" else 0.04
        seg = fx.fade(seg, fin, fade_out if fade_out is not None else min(1.2, max(0.25, (e - s) * 0.06)))
    y, _ = M.master(seg, target_lufs=target_lufs)
    return y


def markers(plan: dict, ear: dict) -> list[dict]:
    s = plan["start"]
    out = []
    for b in plan["beats"]:
        out.append({"time": round(b - s, 3), "type": "beat"})
    for b in plan["downbeats"]:
        out.append({"time": round(b - s, 3), "type": "bar"})
    if s <= plan["anchor"] < plan["end"]:
        out.append({"time": round(plan["anchor"] - s, 3), "type": "hook" if plan["mode"] == "hook" else "drop"})
    pk = ear.get("peak")
    if pk and s <= pk["start"] < plan["end"] and plan["mode"] == "hook":
        out.append({"time": round(pk["start"] - s, 3), "type": "drop"})
    for sec in ear.get("sections", []):
        if s < sec["start"] < plan["end"]:
            out.append({"time": round(sec["start"] - s, 3), "type": "section", "label": sec["kind"]})
    return sorted(out, key=lambda m: (m["time"], m["type"]))


def markers_csv(ms: list[dict]) -> str:
    lines = ["giay,loai,nhan"]
    names = {"beat": "phach", "bar": "o_nhip", "hook": "hook", "drop": "drop", "section": "doan"}
    for m in ms:
        lines.append(f"{m['time']:.3f},{names.get(m['type'], m['type'])},{m.get('label', '')}")
    return "\n".join(lines) + "\n"


def bravin_project(title: str, duration: float, audio_path: Path, mime: str = "audio/mpeg") -> dict:
    """Dự án Bravin (schema 2): khung 9:16 + track nhạc – thả vào Bravin để dựng video theo nhạc ngay."""
    data = base64.b64encode(Path(audio_path).read_bytes()).decode()
    return {"format": "bravin-project", "schema": 2, "generator": {"name": "Micow", "version": __version__},
            "canvas": {"width": 1080, "height": 1920, "background": "#131417"},
            "timeline": {"fps": 30, "duration": round(duration, 3), "trackOrder": "bottom-to-top"},
            "tracks": [{"id": "micow-music", "name": "Nhạc Micow", "index": 0, "enabled": True, "locked": False,
                        "clips": [{"id": "music", "name": title, "start": 0, "duration": round(duration, 3), "volume": 1,
                                   "media": {"type": "audio", "encoding": "data-url",
                                             "data": f"data:{mime};base64,{data}"}}]}]}


def blueprint_markers(bp) -> list[dict]:
    """Mốc nhịp của nhạc CapCut do Micow tự tạo (biết chính xác từ bản thiết kế)."""
    beat = 60.0 / bp.bpm
    dur = bp.duration
    out = [{"time": round(k * beat, 3), "type": "beat"} for k in range(int(dur / beat) + 1) if k * beat < dur]
    out += [{"time": round(b * bp.bar_seconds, 3), "type": "bar"} for b in range(bp.total_bars) if b * bp.bar_seconds < dur]
    for s in bp.sections:
        t = round(s.start_bar * bp.bar_seconds, 3)
        if t < dur:
            out.append({"time": t, "type": "drop" if s.kind == "drop" else "hook" if s.kind == "chorus" else "section",
                        "label": s.kind})
    return sorted(out, key=lambda m: (m["time"], m["type"]))


def finalize(folder: Path, out: dict, title: str, ms: list[dict]) -> dict:
    """Ghi mốc nhịp (CSV/JSON) + dự án Bravin cạnh bản nhạc đã lưu, cập nhật meta.json."""
    (folder / "markers.csv").write_text(markers_csv(ms), encoding="utf-8")
    (folder / "markers.json").write_text(json.dumps(ms, ensure_ascii=False), encoding="utf-8")
    audio = folder / (out["files"].get("mp3") or out["files"]["wav"])
    mime = "audio/mpeg" if audio.suffix == ".mp3" else "audio/wav"
    (folder / "capcut.bravin.json").write_text(json.dumps(bravin_project(title, out["duration"], audio, mime)), encoding="utf-8")
    out["files"].update({"markers": "markers.csv", "markers_json": "markers.json", "bravin": "capcut.bravin.json"})
    out["markers"] = ms
    (folder / "meta.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def save_cut(folder: Path, title: str, y: np.ndarray, plan: dict, ear: dict, meta: dict) -> dict:
    from ..outputs import save_result
    ms = markers(plan, ear)
    meta = dict(meta, capcut={k: v for k, v in plan.items() if k not in ("beats", "downbeats")})
    out = save_result(folder, meta, y)
    return finalize(folder, out, title, ms)
