"""Dữ liệu huấn luyện Micow-LM.

Định dạng manifest (JSONL), mỗi dòng một bài:
  {"audio": "bai1.wav", "style": "ballad buồn, piano, giọng nữ", "lyrics": "[Verse]\\n...", "bpm": 72, "key": "A minor",
   "lrc": "bai1.lrc"}          # lrc tuỳ chọn: có mốc thời gian thì mỗi đoạn cắt chỉ kèm lời đúng đoạn đó

`micow data synth` tạo bộ dữ liệu tổng hợp bằng Micow Beat (biết chính xác phong cách, lời, LRC) để
chạy thử toàn bộ quy trình và làm dữ liệu khởi động – ACE-Step 1.5 cũng dùng âm thanh tổng hợp khi huấn luyện.
Chỉ huấn luyện trên nhạc bạn có quyền sử dụng.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import numpy as np

from ..audio_io import read_audio, write_wav

SAMPLE_LYRICS = [
    "Chiều nay phố vắng mưa rơi trên vai\nEm đi qua đây nghe tim nhói đau",
    "Ngày mai nắng sẽ lên thôi\nThôi đừng khóc nữa em ơi",
    "Đèn đường vàng hắt hiu trong đêm dài\nAnh vẫn đứng đây chờ em quay lại",
    "Mình cùng nhau đi qua bao con phố\nTay trong tay ta hát câu ca cũ",
    "Gió mang mùa thu về trên mái nhà\nLá rơi nhẹ như lời ru của mẹ",
    "Hold me close tonight under city lights\nWe can dance until the morning comes",
]


def parse_lrc(text: str) -> list[tuple[float, str]]:
    out = []
    for line in text.splitlines():
        m = re.match(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$", line.strip())
        if m:
            out.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()))
    return out


def lyrics_in_window(item: dict, base: Path, t0: float, t1: float) -> str:
    """Lời của đoạn [t0, t1) nếu có LRC, ngược lại cả bài."""
    lrc = item.get("lrc")
    if lrc:
        p = base / lrc
        if p.exists():
            lines = parse_lrc(p.read_text(encoding="utf-8"))
            sel = [l for t, l in lines if t0 - 1.0 <= t < t1]
            return "\n".join(sel)
    return item.get("lyrics", "")


def synth_dataset(out_dir: str | Path, n: int = 50, seed: int = 0, duration: float = 40.0) -> Path:
    """Tạo n bài bằng Micow Beat + manifest.jsonl."""
    from ..dsp.render import render
    from ..lyrics import to_lrc
    from ..planner import make_blueprint
    from ..styles import GENRES

    out = Path(out_dir)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    lines = []
    for i in range(n):
        g = rng.choice(list(GENRES))
        mood = rng.choice(["", "buồn", "vui", "chill", "sôi động"])
        song = rng.random() < 0.6
        lyr = ""
        if song:
            a, b = rng.sample(SAMPLE_LYRICS, 2)
            lyr = f"[Verse]\n{a}\n[Chorus]\n{b}\n[Verse]\n{rng.choice(SAMPLE_LYRICS)}\n[Chorus]\n{b}"
        style = f"{GENRES[g]['name']} {mood}".strip()
        bp = make_blueprint("song" if song else "beat", style, lyr, seed=seed * 1000 + i, duration=None if song else duration)
        res = render(bp, gender=rng.choice(["female", "male"]))
        name = f"s{i:05d}"
        write_wav(out / "audio" / f"{name}.wav", res.mix)
        bs = bp.bar_seconds
        item = {"audio": f"audio/{name}.wav", "style": bp.style.caption(not song) + f" ({style})",
                "lyrics": lyr, "bpm": bp.bpm, "key": bp.key.name(),
                "sections": [{"kind": x.kind, "start": round(x.start_bar * bs, 3), "end": round((x.start_bar + x.bars) * bs, 3),
                              "energy": round(x.energy, 3)} for x in bp.sections]}
        if res.lrc:
            (out / "audio" / f"{name}.lrc").write_text(to_lrc(res.lrc), encoding="utf-8")
            item["lrc"] = f"audio/{name}.lrc"
        lines.append(json.dumps(item, ensure_ascii=False))
    (out / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out / "manifest.jsonl"


def read_manifest(path: str | Path) -> tuple[list[dict], Path]:
    path = Path(path)
    items = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return items, path.parent


def load_mono(path: Path, sr: int) -> np.ndarray:
    return read_audio(path, sr, mono=True)


def section_track(sections: list[dict] | None, n_frames: int, frame_rate: float, start_s: float = 0.0):
    """Nhãn cấu trúc từng khung: (kind_idx (n,), energy_bin (n,)). Không có nhãn → None."""
    if not sections:
        return None
    from ..ear.nn import KINDS
    kind = np.full(n_frames, len(KINDS), np.int64)
    en = np.zeros(n_frames, np.int64)
    t = start_s + np.arange(n_frames) / frame_rate
    for s in sections:
        m = (t >= s["start"]) & (t < s["end"])
        kind[m] = KINDS.index(s["kind"]) if s["kind"] in KINDS else len(KINDS)
        en[m] = int(np.clip(round(float(s.get("energy", 0.5)) * 7), 0, 7))
    return kind, en


def auto_label(manifest: str | Path, log=print) -> Path:
    """Dùng Micow Ear gán nhãn đoạn (intro/verse/chorus/drop…) + năng lượng cho mọi bài trong manifest."""
    from ..audio_io import SR, read_audio
    from ..ear import listen
    items, base = read_manifest(manifest)
    for i, it in enumerate(items):
        if it.get("sections"):
            continue
        r = listen(read_audio(base / it["audio"], SR), SR)
        it["sections"] = [{"kind": s["kind"], "start": s["start"], "end": s["end"], "energy": s["energy"]} for s in r["sections"]]
        it.setdefault("bpm", round(r["bpm"]))
        it.setdefault("key", r["key"]["name"])
        log(f"gán nhãn {i + 1}/{len(items)}: {it['audio']} – {len(it['sections'])} đoạn")
    out = Path(manifest)
    out.write_text("\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n", encoding="utf-8")
    return out
