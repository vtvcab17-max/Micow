"""Planner – "bộ não" của Micow: biến (phong cách + lời + clip mẫu) thành bản thiết kế bài hát.

Bản thiết kế (Blueprint) gồm tempo, giọng, chuỗi đoạn (Intro/Verse/Chorus…), số ô nhịp mỗi đoạn,
hợp âm từng ô nhịp, năng lượng từng đoạn và lời gắn vào đoạn. Mọi engine (DSP, Micow-LM, ACE-Step)
đều nhận cùng bản thiết kế này, nên giao diện vẽ được cấu trúc bài trước khi tạo.
Tương đương bước "LM planner" của ACE-Step 1.5 và bước hiểu prompt/meta-tag của Suno.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .analysis import fit_tempo, suggest_genre
from .lyrics import CANON_VI, VOCAL_SECTIONS, LyricLine, LyricSection, parse_lyrics
from .styles import GENRES, StyleSpec, parse_style
from .theory import Chord, Key, progression

BASE_ENERGY = {"intro": 0.35, "verse": 0.55, "prechorus": 0.68, "chorus": 0.92, "postchorus": 0.8,
               "bridge": 0.5, "drop": 1.0, "break": 0.28, "instrumental": 0.72, "outro": 0.32}
# tốc độ hát điển hình (âm tiết/giây) theo thể loại – rap nhanh, ballad chậm
SING_RATE = {"ballad": 2.0, "bolero": 1.9, "cinematic": 2.0, "lofi": 2.5, "rnb": 2.6, "vpop": 2.8,
             "house": 2.8, "edm": 2.8, "vinahouse": 3.0, "trap": 4.6, "boombap": 4.4}
# cấu trúc beat mặc định (không lời): (loại, số ô nhịp)
BEAT_FORMS = {
    "trap": [("intro", 4), ("chorus", 8), ("verse", 16), ("chorus", 8), ("verse", 16), ("chorus", 8), ("outro", 4)],
    "boombap": [("intro", 4), ("verse", 16), ("chorus", 8), ("verse", 16), ("chorus", 8), ("outro", 4)],
    "lofi": [("intro", 4), ("verse", 8), ("chorus", 8), ("verse", 8), ("chorus", 8), ("outro", 4)],
    "house": [("intro", 8), ("verse", 16), ("prechorus", 8), ("drop", 16), ("break", 8), ("prechorus", 8), ("drop", 16), ("outro", 8)],
    "edm": [("intro", 8), ("verse", 8), ("prechorus", 8), ("drop", 16), ("break", 8), ("prechorus", 8), ("drop", 16), ("outro", 4)],
    "vinahouse": [("intro", 8), ("verse", 8), ("prechorus", 8), ("drop", 16), ("break", 8), ("prechorus", 8), ("drop", 16), ("outro", 8)],
    "_default": [("intro", 4), ("verse", 8), ("chorus", 8), ("verse", 8), ("chorus", 8), ("bridge", 8), ("chorus", 8), ("outro", 4)],
}


@dataclass
class Section:
    kind: str
    label: str
    bars: int
    start_bar: int = 0
    energy: float = 0.6
    chords: list[Chord] = field(default_factory=list)   # mỗi ô nhịp một hợp âm
    lines: list[LyricLine] = field(default_factory=list)
    line_bars: list[int] = field(default_factory=list)  # số ô nhịp cho từng dòng lời
    index: int = 0                                      # lần xuất hiện thứ mấy của loại đoạn này

    @property
    def vocal(self) -> bool:
        return bool(self.lines)


@dataclass
class Blueprint:
    title: str
    mode: str                     # beat | song
    style: StyleSpec
    sections: list[Section]
    seed: int = 0
    beats_per_bar: int = 4
    reference: dict | None = None
    lyrics_text: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def bpm(self) -> int:
        return self.style.bpm

    @property
    def key(self) -> Key:
        return self.style.key

    @property
    def bar_seconds(self) -> float:
        return 60.0 / self.bpm * self.beats_per_bar

    @property
    def total_bars(self) -> int:
        return sum(s.bars for s in self.sections)

    @property
    def duration(self) -> float:
        return self.total_bars * self.bar_seconds

    def section_at_bar(self, bar: int) -> Section | None:
        for s in self.sections:
            if s.start_bar <= bar < s.start_bar + s.bars:
                return s
        return None

    def to_dict(self) -> dict:
        bs = self.bar_seconds
        return {
            "title": self.title, "mode": self.mode, "seed": self.seed, "bpm": self.bpm,
            "key": self.key.to_dict(), "beats_per_bar": self.beats_per_bar,
            "duration": round(self.duration, 2), "total_bars": self.total_bars,
            "style": self.style.to_dict(), "notes": self.notes,
            "sections": [{
                "kind": s.kind, "label": s.label, "bars": s.bars, "start_bar": s.start_bar,
                "start": round(s.start_bar * bs, 3), "end": round((s.start_bar + s.bars) * bs, 3),
                "energy": round(s.energy, 2), "chords": [c.name() for c in s.chords],
                "lines": [l.text for l in s.lines],
            } for s in self.sections],
        }


def _line_bars(line: LyricLine, bpm: float, genre: str) -> int:
    rate = SING_RATE.get(genre, 2.6)
    bar_s = 240.0 / bpm
    need = len(line.syls) / (rate * bar_s) + 0.35   # + chỗ lấy hơi
    b = max(1, math.ceil(need))
    return 1 if b == 1 else 2 if b == 2 else 4 if b <= 4 else 8


def _round4(n: int) -> int:
    return max(4, int(math.ceil(n / 4.0)) * 4)


def _section_prog(style: StyleSpec, kind: str, idx: int, rng: np.random.Generator) -> list[Chord]:
    progs = style.preset["progs"]
    main = progs[0]
    if kind in ("chorus", "drop", "postchorus", "instrumental"):
        romans = main
    elif kind == "verse":
        romans = progs[1] if len(progs) > 1 else main
    elif kind == "bridge":
        romans = progs[2] if len(progs) > 2 else main[2:] + main[:2]
    elif kind == "prechorus":
        romans = ["IV", "V"] * 2 if not style.key.is_minor else ["VI", "VII"] * 2
    else:
        romans = main
    return progression(style.key, romans)


def _harmonic_rhythm(style: StyleSpec) -> int:
    if style.preset.get("half_time") or style.bpm >= 130:
        return 2
    return 1


def make_blueprint(mode: str = "song", style_text: str = "", lyrics: str = "", title: str = "",
                   genre: str | None = None, bpm: int | None = None, key: str | None = None,
                   duration: float | None = None, energy: float | None = None, seed: int = 0,
                   reference: dict | None = None) -> Blueprint:
    rng = np.random.default_rng(seed)
    notes: list[str] = []
    # 1) phong cách – clip mẫu được dùng khi người dùng không ghi rõ
    ref_genre = suggest_genre(reference) if reference else None
    style = parse_style(style_text, genre=genre or (None if style_text.strip() else ref_genre), bpm=bpm, key=key,
                        energy=energy, seed=seed)
    if reference and reference.get("bpm"):
        if not style.explicit_bpm:
            lo, hi = style.preset["bpm"]
            style.bpm = int(round(fit_tempo(reference["bpm"], lo, hi)))
            notes.append(f"Tempo lấy theo clip mẫu: {style.bpm} BPM")
        if not style.explicit_key and reference.get("key_confidence", 0) >= 0.15:
            k = reference["key"]
            kmode = k["mode"]
            if kmode == "minor" and style.preset["mode"] in ("harmonic_minor", "dorian"):
                kmode = style.preset["mode"]
            style.key = Key(k["tonic"], kmode)
            notes.append(f"Giọng lấy theo clip mẫu: {style.key.name_vi()}")
        if energy is None and reference.get("energy") is not None:
            style.energy = float(np.clip(0.5 * style.energy + 0.5 * reference["energy"], 0.15, 1))

    # 2) cấu trúc
    lyr_secs: list[LyricSection] = parse_lyrics(lyrics) if (mode == "song" and lyrics.strip()) else []
    plan: list[tuple[str, str, int, list[LyricLine], list[int]]] = []
    if lyr_secs:
        if lyr_secs[0].kind != "intro":
            plan.append(("intro", "", 8 if style.genre in ("edm", "vinahouse", "house") else 4, [], []))
        for s in lyr_secs:
            if s.lines:
                lb = [_line_bars(l, style.bpm, style.genre) for l in s.lines]
                # các dòng trong một đoạn nên dài bằng nhau cho cân câu
                common = max(set(lb), key=lb.count)
                lb = [max(common, b) if abs(b - common) <= 1 else b for b in lb]
                bars = _round4(sum(lb))
                if s.kind == "chorus" and bars < 8 and style.bpm > 110:
                    bars = 8
                plan.append((s.kind, s.label, s.bars or bars, s.lines, lb))
            else:
                plan.append((s.kind, s.label, s.bars or (4 if s.kind in ("intro", "outro", "break") else 8), [], []))
        if lyr_secs[-1].kind != "outro":
            plan.append(("outro", "", 4, [], []))
    else:
        form = BEAT_FORMS.get(style.genre, BEAT_FORMS["_default"])
        plan = [(k, "", b, [], []) for k, b in form]

    # 3) khớp thời lượng mong muốn
    bar_s = 240.0 / style.bpm
    if duration and duration > 5:
        target_bars = max(8, int(round(duration / bar_s)))
        cur = sum(p[2] for p in plan)
        if not lyr_secs:
            scale = target_bars / cur
            plan = [(k, l, max(4, int(round(b * scale / 4)) * 4), ln, lb) for k, l, b, ln, lb in plan]
            # cắt / thêm cho khớp
            while sum(p[2] for p in plan) > target_bars + 2 and len(plan) > 3:
                big = max(range(1, len(plan) - 1), key=lambda i: plan[i][2])
                k, l, b, ln, lb = plan[big]
                if b > 4:
                    plan[big] = (k, l, b - 4, ln, lb)
                else:
                    plan.pop(big)
        elif cur < target_bars - 4:
            # bài có lời ngắn hơn yêu cầu: thêm gian tấu trước điệp khúc cuối + nhân đôi điệp khúc cuối
            last_ch = max((i for i, p in enumerate(plan) if p[0] == "chorus"), default=None)
            if last_ch is not None:
                gap = target_bars - cur
                if gap >= 8:
                    plan.insert(last_ch, ("instrumental", "", 8, [], []))
                    gap -= 8
                    last_ch += 1
                if gap >= 4:
                    k, l, b, ln, lb = plan[last_ch]
                    plan.insert(last_ch + 1, (k, l, b, ln, lb))
                    notes.append("Lặp lại điệp khúc cuối để đủ thời lượng")
        elif cur > target_bars + 8:
            notes.append(f"Lời dài hơn thời lượng yêu cầu: bài sẽ dài khoảng {cur * bar_s:.0f} giây")

    # 4) dựng Section: hợp âm, năng lượng
    hr = _harmonic_rhythm(style)
    sections: list[Section] = []
    counts: dict[str, int] = {}
    bar = 0
    escale = 0.6 + 0.8 * style.energy
    for kind, label, bars, lines, lb in plan:
        counts[kind] = counts.get(kind, 0) + 1
        prog = _section_prog(style, kind, counts[kind], rng)
        chords = [prog[(i // hr) % len(prog)] for i in range(bars)]
        e = BASE_ENERGY.get(kind, 0.6) * escale + 0.05 * (counts[kind] - 1) * (kind in VOCAL_SECTIONS)
        lab = label or (CANON_VI.get(kind, kind) + (f" {counts[kind]}" if kind in ("verse", "drop") else ""))
        sections.append(Section(kind, lab, bars, bar, float(np.clip(e, 0.1, 1.0)), chords, list(lines), list(lb),
                                counts[kind]))
        bar += bars
    title = title.strip() or default_title(style, seed)
    return Blueprint(title, mode if lyr_secs else ("beat" if mode == "beat" else "song"), style, sections, seed,
                     reference=reference, lyrics_text=lyrics, notes=notes)


_TITLE_A = ["Đêm", "Phố", "Mưa", "Nắng", "Gió", "Sóng", "Mây", "Sao", "Lửa", "Biển"]
_TITLE_B = ["Tím", "Vàng", "Xa", "Cuối Ngày", "Đầu Hạ", "Không Ngủ", "Lấp Lánh", "Thầm", "Mới", "Rơi"]


def default_title(style: StyleSpec, seed: int) -> str:
    return f"{_TITLE_A[seed % 10]} {_TITLE_B[(seed // 10 + seed * 3) % 10]} · {GENRES[style.genre]['name']}"
