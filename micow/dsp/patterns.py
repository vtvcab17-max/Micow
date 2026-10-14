"""Mẫu tiết tấu theo thể loại → danh sách sự kiện (Ev) cho trống, bass, hoà âm, lead.

Lưới 16 phần mỗi ô nhịp (4/4). Mỗi bộ trống có 3 mức: 0 (thưa – intro/break), 1 (verse), 2 (chorus/drop).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..planner import Blueprint, Section
from ..theory import Chord, voice_chord

V = {"X": 1.0, "x": 0.82, "o": 0.58, "g": 0.32, ".": 0.0}


@dataclass
class Ev:
    t: float
    dur: float
    inst: str
    track: str
    midi: float = 0.0
    vel: float = 1.0
    extra: dict = field(default_factory=dict)


def P(s: str) -> list[tuple[float, float]]:
    return [(i, V[c]) for i, c in enumerate(s) if c != "."]


# kit → mức → nhạc cụ → mẫu
KITS: dict[str, dict[int, dict[str, str]]] = {
    "pop": {0: {"kick": "x.......x.......", "hat": "..o...o...o...o."},
            1: {"kick": "x.....o.x.......", "snare": "....x.......x...", "hat": "x.o.x.o.x.o.x.o."},
            2: {"kick": "x.....x.x.x.....", "snare": "....X.......X...", "clap": "....x.......x...",
                "hat": "x.o.x.o.x.o.x.o.", "ohat": "..............o.", "shaker": "g.g.g.g.g.g.g.g."}},
    "ballad": {0: {"shaker": "....g.......g..."},
               1: {"kick": "x.......o.......", "rim": "....o.......o...", "hat": "o.g.o.g.o.g.o.g."},
               2: {"kick": "x.....o.x.......", "snare": "....x.......x...", "hat": "x.o.x.o.x.o.x.o."}},
    "rnb": {0: {"hat": "o...o...o...o...", "rim": "....g.......g..."},
            1: {"kick": "x..o......x.....", "snare": "....x..g....x..g", "hat": "o.g.o.ggo.g.o.gg"},
            2: {"kick": "x..x......x..o..", "clap": "....X.......X...", "snare": ".......g.......g", "hat": "xgogxgogxgogxgog"}},
    "trap": {0: {"hat": "o.o.o.o.o.o.o.o."},
             1: {"kick": "x.........x.....", "clap": "........X.......", "hat": "x.x.x.x.x.x.x.x."},
             2: {"kick": "x......x..x...o.", "clap": "........X.......", "hat": "x.x.x.x.x.x.x.x.", "ohat": "......o........."}},
    # drill: nửa nhịp (snare phách 3), hi-hat nhóm 3-3-2, kick lệch phách; snare "trễ" thêm ở ô nhịp lẻ (_drill_bar)
    "drill": {0: {"hat": "x..o..o.x..o..o."},
              1: {"kick": "x.........x.....", "snare": "........X.......", "hat": "x..x..x.x..x..x."},
              2: {"kick": "x.....x...x..x..", "snare": "........X.......", "hat": "x..x..x.x..x..x.",
                  "rim": "...g.......g...."}},
    "boombap": {0: {"hat": "o.o.o.o.o.o.o.o.", "rim": "....o.......o..."},
                1: {"kick": "x......x..x.....", "snare": "....x.......x...", "hat": "x.o.x.o.x.o.x.o."},
                2: {"kick": "x......x.xx.....", "snare": "....X.......X..g", "hat": "x.o.x.o.x.o.x.o.", "ohat": "......o........."}},
    "lofi": {0: {"hat": "o...o...o...o..."},
             1: {"kick": "x......x..x.....", "snare": "....o.......o...", "hat": "o.g.o.g.o.g.o.g."},
             2: {"kick": "x......x..x..o..", "snare": "....x.......x...", "hat": "x.o.x.o.x.o.x.o."}},
    "house": {0: {"hat": "..o...o...o...o.", "shaker": "g.g.g.g.g.g.g.g."},
              1: {"kick": "x...x...x...x...", "clap": "....x.......x...", "hat": "g.g.g.g.g.g.g.g.", "ohat": "..o...o...o...o."},
              2: {"kick": "X...X...X...X...", "clap": "....X.......X...", "hat": "g.g.g.g.g.g.g.g.", "ohat": "..x...x...x...x.",
                  "shaker": "gggggggggggggggg"}},
    "edm": {0: {},
            1: {"kick": "x.......x.......", "clap": "....x.......x...", "hat": "..o...o...o...o."},
            2: {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.", "hat": "g.g.g.g.g.g.g.g."}},
    "vinahouse": {0: {"hat": "..o...o...o...o."},
                  1: {"kick": "x...x...x...x...", "hat": "o.o.o.o.o.o.o.o.", "ohat": "..o...o...o...o."},
                  2: {"kick": "X...X...X...X...", "clap": "....X.......X...", "hat": "gxgxgxgxgxgxgxgx", "ohat": "..x...x...x...x.",
                      "shaker": "gggggggggggggggg"}},
    "bolero": {0: {"shaker": "o.g.o.g.o.g.o.g."},
               1: {"kick": "o.......o.......", "shaker": "o.g.o.g.o.g.o.g."},
               2: {"kick": "x.......x.......", "shaker": "x.g.x.g.x.g.x.g.", "rim": "............o..."}},
    "cinematic": {0: {},
                  1: {"kick": "x.......x.......", "tom": "x..o..o.x..o..o."},
                  2: {"kick": "X.......X.......", "snare": "....x.......x...", "tom": "x..x..x.x..x.xxx"}},
}
BOLERO_CONGA = [(0, "conga_lo", 0.9), (4, "conga_hi", 0.7), (5.333, "conga_hi", 0.55), (6.667, "conga_lo", 0.65),
                (8, "conga_lo", 0.85), (12, "conga_hi", 0.7)]
HAS_CRASH = {"pop", "ballad", "edm", "house", "vinahouse", "cinematic", "rnb", "boombap"}
HUMAN = {"ballad", "bolero", "lofi", "boombap", "rnb", "cinematic"}
BUILD_GENRES = {"edm", "house", "vinahouse", "pop"}

BASS_PAT: dict[str, dict[int, list[tuple[float, float, int]]]] = {
    "pop": {1: [(0, 6, 0), (6, 2, 0), (8, 6, 0), (14, 2, 7)], 2: [(0, 3, 0), (3, 1, 0), (6, 2, 0), (8, 3, 0), (11, 1, 0), (14, 2, 0)]},
    "ballad": {1: [(0, 16, 0)], 2: [(0, 6, 0), (6, 2, 0), (8, 8, 7)]},
    "rnb": {1: [(0, 3, 0), (3, 3, 0), (10, 2, 0), (12, 4, 7)], 2: [(0, 3, 0), (3, 3, 0), (10, 2, 0), (12, 2, 7), (14, 2, 10)]},
    "boombap": {1: [(0, 3, 0), (3, 2, 0), (7, 2, 7), (10, 6, 0)], 2: [(0, 3, 0), (3, 2, 0), (7, 2, 7), (10, 4, 0), (14, 2, 10)]},
    "lofi": {1: [(0, 6, 0), (7, 2, 7), (10, 6, 0)], 2: [(0, 3, 0), (3, 2, 0), (7, 2, 7), (10, 4, 0), (14, 2, 10)]},
    "house": {1: [(2, 2, 0), (6, 2, 0), (10, 2, 0), (14, 2, 0)], 2: [(2, 2, 0), (6, 2, 0), (10, 2, 0), (14, 2, 12)]},
    "edm": {1: [(0, 16, 0)], 2: [(0, 2, 0), (2, 2, 0), (4, 2, 0), (6, 2, 0), (8, 2, 0), (10, 2, 0), (12, 2, 0), (14, 2, 0)]},
    "vinahouse": {1: [(s, 1, 0) for s in (2, 6, 10, 14)], 2: [(s, 1, 0 if s % 4 != 3 else 12) for s in (1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15)]},
    "bolero": {1: [(0, 8, 0), (8, 8, 7)], 2: [(0, 6, 0), (6, 2, 7), (8, 6, 7), (14, 2, 0)]},
    "cinematic": {1: [(0, 16, 0)], 2: [(0, 8, 0), (8, 8, 0)]},
}


def level_for(sec: Section) -> int:
    if sec.kind in ("intro", "break", "outro") or sec.energy < 0.42:
        return 0
    return 2 if sec.energy >= 0.75 else 1


class Arranger:
    """Sinh sự kiện cho toàn bài từ Blueprint."""

    def __init__(self, bp: Blueprint, rng: np.random.Generator):
        self.bp = bp
        self.rng = rng
        self.kit = bp.style.preset["drums"]
        self.genre = bp.style.genre
        self.step = 60.0 / bp.bpm / 4
        self.bar_s = bp.bar_seconds
        self.swing = bp.style.swing
        self.events: list[Ev] = []

    # ---------- thời gian ----------
    def time(self, bar: int, step: float) -> float:
        s = step
        if self.swing and abs(step - round(step)) < 1e-6:
            k = int(round(step))
            if k % 2 == 1:
                s = step + self.swing          # trễ nốt móc kép lẻ (swing kiểu MPC ~60%)
            elif k % 4 == 2:
                s = step + self.swing * 0.5    # trễ nhẹ nốt móc đơn phách lẻ
        t = bar * self.bar_s + s * self.step
        if self.genre in HUMAN:
            t += float(self.rng.normal(0, 0.004))
        return max(0.0, t)

    def add(self, bar, step, inst, track, dur_steps=1.0, midi=0.0, vel=1.0, **extra):
        v = vel * (1 + float(self.rng.normal(0, 0.05))) if self.genre in HUMAN else vel
        self.events.append(Ev(self.time(bar, step), dur_steps * self.step, inst, track, midi, float(np.clip(v, 0.05, 1.2)), extra))

    # ---------- trống ----------
    def drums(self):
        bp = self.bp
        secs = bp.sections
        for si, sec in enumerate(secs):
            lvl = level_for(sec)
            nxt = secs[si + 1] if si + 1 < len(secs) else None
            build = (self.genre in BUILD_GENRES and nxt is not None and nxt.kind in ("chorus", "drop")
                     and sec.kind in ("prechorus", "break", "verse")) or (bp.mode == "capcut" and nxt is not None
                                                                          and nxt.kind == "drop")
            for b in range(sec.bars):
                bar = sec.start_bar + b
                pats = KITS[self.kit][lvl]
                last = b == sec.bars - 1
                build_zone = build and (sec.kind == "prechorus" and b >= sec.bars / 2 or
                                        b >= sec.bars - (1 if bp.mode == "capcut" and sec.bars <= 4 else 2))
                if sec.kind == "outro" and b >= sec.bars - 1:
                    pats = {}
                for inst, pat in pats.items():
                    if build_zone and inst in ("kick", "clap") and self.genre in ("edm", "vinahouse"):
                        continue
                    if last and nxt is not None and inst in ("hat", "ohat", "shaker") and lvl >= 1 and self.rng.random() < 0.5:
                        pat = pat[:12] + "...."
                    for st, v in P(pat):
                        if last and nxt is not None and st >= 12 and inst in ("snare", "clap") and not build:
                            continue
                        self.add(bar, st, inst, "drums", vel=v * (0.75 + 0.35 * sec.energy))
                if self.kit == "bolero" and lvl >= 1:
                    for st, inst, v in BOLERO_CONGA:
                        self.add(bar, st, inst, "drums", vel=v)
                if self.kit in ("trap", "drill") and lvl >= 1 and (b % 2 == 1 or self.rng.random() < 0.3):
                    self._trap_roll(bar)
                if self.kit == "drill" and lvl >= 1 and b % 2 == 1:
                    self._drill_bar(bar)
                if build_zone:
                    k0 = sec.bars // 2 if sec.kind == "prechorus" else sec.bars - (1 if bp.mode == "capcut" and sec.bars <= 4 else 2)
                    self._snare_build(bar, b - k0 + (2 if bp.mode == "capcut" and sec.bars <= 4 else 0), sec)
                elif last and nxt is not None and nxt.energy > sec.energy + 0.1 and lvl >= 1:
                    self._fill(bar)
            if self.kit in HAS_CRASH and sec.kind in ("chorus", "drop") or (sec.kind == "verse" and sec.index == 1 and si > 0 and self.kit in HAS_CRASH):
                self.add(sec.start_bar, 0, "crash", "drums", vel=0.8)
            if build and (self.genre in ("edm", "vinahouse", "house") or bp.mode == "capcut"):
                rb = 4 if sec.bars >= 8 else 2
                self.events.append(Ev((sec.start_bar + sec.bars - rb) * self.bar_s, rb * self.bar_s, "riser", "fx", vel=0.6))
            if sec.kind == "drop" or (sec.kind == "chorus" and self.genre in ("edm", "vinahouse", "cinematic")):
                self.events.append(Ev(sec.start_bar * self.bar_s, 2.5, "impact", "fx", vel=0.5))

    def _trap_roll(self, bar):
        start = float(self.rng.choice([12, 14, 6]))
        kind = self.rng.choice(["32", "trip", "16"])
        if kind == "32":
            pts = np.arange(start, start + 2, 0.5)
        elif kind == "trip":
            pts = np.arange(start, start + 2, 2 / 3)
        else:
            pts = np.arange(start, start + 2, 1)
        for i, p in enumerate(pts):
            self.add(bar, float(p), "hat", "drums", vel=0.45 + 0.1 * (i % 2))

    def _drill_bar(self, bar):
        """Snare "trễ" đặc trưng drill: thêm một phát lệch sau phách 3 ở ô nhịp lẻ (vị trí 13/14/15)."""
        st = float(self.rng.choice([13, 14, 15]))
        self.add(bar, st, "snare", "drums", vel=0.72)

    def _snare_build(self, bar, k, sec):
        dens = [4, 2, 1, 0.5][min(3, max(0, k))]
        for i, st in enumerate(np.arange(0, 16, dens)):
            self.add(bar, float(st), "snare", "drums", vel=0.35 + 0.5 * (st / 16) * (0.6 + 0.4 * k / 3))

    def _fill(self, bar):
        if self.kit in ("ballad", "pop", "cinematic", "bolero"):
            for st, f in ((12, 180.0), (13, 150.0), (14, 120.0), (15, 95.0)):
                self.add(bar, st, "tom", "drums", vel=0.7, midi=f)
        else:
            for st in (12, 13, 14, 15):
                self.add(bar, st, "snare", "drums", vel=0.4 + 0.12 * (st - 12))

    # ---------- bass ----------
    def bass(self):
        kind = self.bp.style.preset["bass"]
        for sec in self.bp.sections:
            lvl = level_for(sec)
            if lvl == 0 and sec.kind != "outro" and not (sec.kind == "intro" and self.genre in ("ballad", "bolero")):
                continue
            for b in range(sec.bars):
                bar = sec.start_bar + b
                ch = sec.chords[b]
                root = 28 + (ch.root_pc - 4) % 12  # E1..D#2
                if kind == "808":
                    self._bass808(bar, ch, lvl)
                    continue
                pat = BASS_PAT.get(self.kit, BASS_PAT["pop"]).get(max(1, lvl))
                fifth = 7 if ch.quality != "dim" else 6
                for st, ln, iv in pat:
                    iv2 = fifth if iv == 7 else iv
                    self.add(bar, st, kind, "bass", dur_steps=ln * 0.92, midi=root + iv2, vel=0.9)

    def _bass808(self, bar, ch, lvl):
        kit = self.kit if self.kit in ("trap", "drill") else "trap"
        kicks = [st for st, _ in P(KITS[kit][max(1, lvl)]["kick"])]
        root = 26 + (ch.root_pc - 2) % 12
        prev = None
        for i, st in enumerate(kicks):
            end = kicks[i + 1] if i + 1 < len(kicks) else 16
            if kit == "drill" and i > 0:
                # drill: 808 nhảy quãng (5, 7, quãng tám, xuống 2) rồi trượt cao độ về nốt mới
                m = root + int(self.rng.choice([0, 12, 7, 10, -2, 5]))
            else:
                m = root + (12 if (i == len(kicks) - 1 and self.rng.random() < 0.3) else 0)
            glide = 0.0
            if prev is not None and prev != m:
                from ..theory import midi_to_hz
                glide = midi_to_hz(prev)
            self.add(bar, st, "808", "bass", dur_steps=end - st, midi=m, vel=1.0, glide=glide)
            prev = m

    # ---------- hoà âm ----------
    def chords(self):
        layers = self.bp.style.layers
        prev_voice = None
        for sec in self.bp.sections:
            n_active = 1 + int(round(sec.energy * (len(layers) - 1) + 0.2))
            if sec.kind in ("intro", "outro", "break"):
                n_active = 1
            active = layers[:max(1, n_active)]
            lvl = level_for(sec)
            for b in range(sec.bars):
                bar = sec.start_bar + b
                ch = sec.chords[b]
                voice = voice_chord(ch, prev_voice, 55, 74)
                prev_voice = voice
                for li, layer in enumerate(active):
                    self._chord_layer(layer, bar, ch, voice, lvl, sec, li)

    def _chord_layer(self, layer, bar, ch: Chord, voice, lvl, sec, li):
        vel = 0.55 + 0.35 * sec.energy
        add = lambda st, ln, notes, v=vel, inst=layer: [self.add(bar, st, inst, "chords", ln, m, v) for m in notes]
        if layer in ("pad", "strings", "organ"):
            add(0, 16, voice, vel * 0.8)
        elif layer == "supersaw":
            if lvl == 2:
                for st, ln in ((0, 3), (3, 3), (6, 2), (8, 3), (11, 3), (14, 2)):
                    add(st, ln * 0.9, voice + [voice[0] + 12])
            else:
                add(0, 16, voice, vel * 0.6)
        elif layer == "piano":
            if lvl <= 1 or self.genre in ("ballad", "cinematic"):
                low = voice[0] - 12
                seq = [low, voice[1], voice[2], voice[0] + 12, voice[2], voice[1], voice[0] + 12, voice[2]]
                for i, m in enumerate(seq):
                    self.add(bar, i * 2, "piano", "chords", 3.5, m, vel * (0.9 if i == 0 else 0.7))
                if lvl == 2:
                    add(0, 8, voice[1:], vel * 0.55)
                    add(8, 8, voice[1:], vel * 0.5)
            else:
                add(0, 6, voice)
                add(6, 2, voice, vel * 0.75)
                add(8, 8, voice)
        elif layer == "epiano":
            if self.genre in ("lofi", "rnb"):
                add(0, 6, voice)
                add(7, 9, voice, vel * 0.8)
            elif lvl == 2:
                for st, ln in ((0, 3), (3, 3), (6, 2), (8, 3), (11, 3), (14, 2)):
                    add(st, ln, voice, vel * (0.85 if st % 4 else 1.0))
            else:
                add(0, 8, voice)
                add(8, 8, voice, vel * 0.85)
        elif layer == "guitar":
            low = [voice[0] - 12, voice[0] - 5] + voice
            if self.genre == "bolero":
                for st, part in ((0, "b"), (4, "c"), (6, "c"), (8, "b5"), (12, "c"), (14, "c")):
                    if part == "b":
                        self.add(bar, st, "guitar", "chords", 4, voice[0] - 12, vel)
                    elif part == "b5":
                        self.add(bar, st, "guitar", "chords", 4, voice[0] - 5, vel * 0.9)
                    else:
                        for k, m in enumerate(voice):
                            self.add(bar, st + k * 0.06, "guitar", "chords", 2, m, vel * 0.6)
            else:
                for st, d in ((0, "D"), (4, "D"), (6, "U"), (10, "U"), (12, "D"), (14, "U")):
                    notes = low if d == "D" else list(reversed(voice))
                    for k, m in enumerate(notes):
                        self.add(bar, st + k * 0.05, "guitar", "chords", 3.5, m, vel * (0.75 if d == "D" else 0.5))
        elif layer == "pluck":
            pat = ((2, 1), (6, 1), (10, 1), (14, 1)) if self.genre in ("house", "vinahouse") else ((0, 2), (3, 2), (6, 2), (8, 2), (11, 2), (14, 2))
            for st, ln in pat:
                add(st, ln, voice, vel * 0.8)
        elif layer == "bell":
            tones = [m + 12 for m in voice]
            for st, m in zip((0, 3, 6, 10), tones + tones):
                self.add(bar, st, "bell", "chords", 3, m, vel * 0.6)
        elif layer == "zither":
            tones = sorted(voice + [voice[0] + 12])
            for i, m in enumerate(tones):
                self.add(bar, i * 2, "zither", "chords", 2, m, vel * 0.7)
        elif layer == "arp":
            self._arp(bar, voice, vel)
        else:
            add(0, 16, voice, vel * 0.7, inst=layer)

    def _arp(self, bar, voice, vel, inst="arp"):
        tones = voice + [m + 12 for m in voice]
        seq = tones + tones[-2:0:-1]
        for i in range(16):
            self.add(bar, i, inst, "lead", 0.9, seq[i % len(seq)] + 12, vel * (0.85 if i % 4 == 0 else 0.6))

    # ---------- hook không lời (chế độ beat) ----------
    def hook(self):
        lead = self.bp.style.lead
        key = self.bp.key
        motif_cache: dict[int, list[tuple[float, float, int]]] = {}
        rhythms = [[(0, 2), (2, 2), (4, 4), (10, 2), (12, 4)], [(0, 3), (3, 3), (6, 2), (8, 4), (14, 2)],
                   [(0, 1), (2, 1), (4, 2), (6, 2), (8, 6), (14, 2)], [(0, 6), (6, 2), (8, 2), (10, 6)]]
        rhythm = rhythms[int(self.rng.integers(0, len(rhythms)))]
        for sec in self.bp.sections:
            if sec.vocal or sec.kind not in ("chorus", "drop", "instrumental", "postchorus"):
                continue
            if lead == "arp":
                for b in range(sec.bars):
                    ch = sec.chords[b]
                    self._arp(sec.start_bar + b, voice_chord(ch, None, 60, 76), 0.55 + 0.3 * sec.energy)
                continue
            for b in range(sec.bars):
                bar = sec.start_bar + b
                ch = sec.chords[b]
                slot = b % 2
                if slot not in motif_cache or (b == sec.bars - 1):
                    notes = []
                    pcs = ch.pcs()
                    for i, (st, ln) in enumerate(rhythm):
                        if i == 0 or st % 4 == 0:
                            pc = pcs[int(self.rng.integers(0, len(pcs)))]
                        else:
                            pc = key.degree_pc(int(self.rng.integers(0, 7)))
                        m = 72 + (pc - 72) % 12
                        notes.append((st, ln, m))
                    if b == sec.bars - 1:
                        notes[-1] = (notes[-1][0], notes[-1][1], 72 + (key.tonic - 72) % 12)
                    motif_cache[slot] = notes
                for st, ln, m in motif_cache[slot]:
                    # cho hook đi theo hợp âm hiện tại: kéo về nốt hợp âm gần nhất ở phách mạnh
                    if st % 8 == 0:
                        m = min((m + d for d in range(-2, 3)), key=lambda x: (x % 12 not in ch.pcs(), abs(x - m)))
                    self.add(bar, st, lead, "lead", ln * 0.95, m, 0.6 + 0.3 * sec.energy)
