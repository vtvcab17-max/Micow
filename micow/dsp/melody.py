"""Sinh giai điệu hát từ lời: nhịp theo số âm tiết, cao độ theo hợp âm + đường cong câu nhạc
+ thanh điệu tiếng Việt (sắc/ngã đi lên, huyền/nặng/hỏi đi xuống) để lời hát không bị lệch dấu.

Câu lặp lại (điệp khúc) dùng lại đúng giai điệu; dòng thứ i của các phiên khúc dùng chung nhịp.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from ..lyrics import TONE_CONTOUR, main_vowel, strip_accents, vi_tone
from ..planner import Blueprint
from ..theory import Key


@dataclass
class VNote:
    beat: float          # phách tuyệt đối tính từ đầu bài
    dur: float           # số phách
    midi: int
    syl: str
    vowel: str
    line_id: int
    first_in_line: bool = False


def _rhythm(n_syl: int, beats: int, rng: np.random.Generator, start_off: float) -> list[tuple[float, float]]:
    """Trả về [(phách bắt đầu, độ dài)] cho n âm tiết trong `beats` phách (chừa chỗ lấy hơi)."""
    breath = 1.0 if beats <= 4 else 1.5
    avail = beats - start_off - breath
    grid = 0.5 if n_syl <= avail * 2 else 0.25
    slots = int(avail / grid)
    n = max(1, n_syl)
    if n > slots:  # quá dày: nén đều
        d = avail / n
        return [(start_off + i * d, d * 0.95) for i in range(n)]
    durs = [1] * n
    extra = slots - n
    # ưu tiên kéo dài âm tiết cuối, rồi các âm giữa câu (sau mỗi 3–4 âm tiết)
    take = min(extra, max(2, int(1.0 / grid)) * 2)
    durs[-1] += take
    extra -= take
    pivots = list(range(2, n - 1, 3 if n > 6 else 2))
    rng.shuffle(pivots)
    i = 0
    while extra > 0 and pivots:
        durs[pivots[i % len(pivots)]] += 1
        extra -= 1
        i += 1
    out, pos = [], start_off
    for d in durs:
        out.append((pos, d * grid * 0.96))
        pos += d * grid
    return out


def _nearest_chord_tone(m: int, pcs: list[int], within: int = 2) -> int:
    best = m
    for d in sorted(range(-within, within + 1), key=abs):
        if (m + d) % 12 in pcs:
            return m + d
    return best


def _scale_step(m: int, steps: int, key: Key) -> int:
    pcs = sorted({(key.tonic + s) % 12 for s in key.scale})
    if steps == 0:
        return m
    direction = 1 if steps > 0 else -1
    x = m
    for _ in range(abs(steps)):
        x += direction
        while x % 12 not in pcs:
            x += direction
    return x


def make_melody(bp: Blueprint, gender: str = "female", seed: int = 0) -> list[VNote]:
    rng = np.random.default_rng(seed + 1234)
    key = bp.key
    center = 67 if gender == "female" else 57          # G4 / A3
    lo, hi = (center - 8, center + 12)
    bpb = bp.beats_per_bar
    notes: list[VNote] = []
    line_cache: dict[str, list[tuple[float, float, int]]] = {}
    rhythm_cache: dict[tuple, list[tuple[float, float]]] = {}
    line_id = 0
    last_m = center
    for sec in bp.sections:
        if not sec.vocal:
            continue
        lift = {"chorus": 4, "postchorus": 3, "prechorus": 2, "bridge": 3}.get(sec.kind, 0)
        bar_cursor = sec.start_bar
        for li, (line, lb) in enumerate(zip(sec.lines, sec.line_bars)):
            syls = line.syls or ["la"]
            beats = lb * bpb
            norm = re.sub(r"\W+", " ", strip_accents(line.text).lower()).strip()
            abs_beat0 = bar_cursor * bpb
            if norm in line_cache and len(line_cache[norm]) == len(syls):
                pattern = line_cache[norm]
            else:
                rkey = (sec.kind, li, len(syls), lb)
                if rkey in rhythm_cache:
                    rhythm = rhythm_cache[rkey]
                else:
                    start_off = float(rng.choice([0.0, 0.5, 0.5, 1.0])) if beats >= 8 else 0.0
                    rhythm = _rhythm(len(syls), beats, rng, start_off)
                    rhythm_cache[rkey] = rhythm
                pattern = []
                n = len(syls)
                target = center + lift + int(rng.integers(-2, 3))
                m = _nearest_chord_tone(int(np.clip(last_m + (target - last_m) // 2, lo, hi)),
                                        sec.chords[min(len(sec.chords) - 1, (bar_cursor - sec.start_bar))].pcs())
                for i, (b, d) in enumerate(rhythm):
                    bar_in_sec = (bar_cursor - sec.start_bar) + int(b // bpb)
                    ch = sec.chords[min(len(sec.chords) - 1, bar_in_sec)]
                    if i > 0:
                        tone = vi_tone(syls[i])
                        tstep = TONE_CONTOUR.get(tone, 0) if tone else int(rng.integers(-1, 2))
                        arc = 1 if i < n * 0.45 else -1 if i > n * 0.7 else 0
                        step = tstep + (arc if rng.random() < 0.45 else 0)
                        if step == 0 and rng.random() < 0.25:
                            step = int(rng.choice([-1, 1]))
                        m = _scale_step(m, int(np.clip(step, -3, 3)), key)
                        if m > hi:
                            m = _scale_step(m, -3, key)
                        if m < lo:
                            m = _scale_step(m, 3, key)
                    on_beat = abs(b - round(b)) < 1e-6
                    if on_beat or d >= 1.0:
                        m = _nearest_chord_tone(m, ch.pcs())
                    if i == n - 1:  # cuối câu về nốt hợp âm ổn định
                        pcs = ch.pcs()
                        prefer = [pcs[0], pcs[1]] if li == len(sec.lines) - 1 else pcs
                        m = min((m + dd for dd in range(-4, 5)), key=lambda x: (x % 12 not in prefer, abs(x - m)))
                        if li == len(sec.lines) - 1 and sec.kind == "chorus":
                            m = min((m + dd for dd in range(-5, 6)), key=lambda x: (x % 12 != key.tonic, abs(x - m)))
                    pattern.append((b, d, int(m)))
                line_cache[norm] = pattern
            for i, ((b, d, m), syl) in enumerate(zip(pattern, syls)):
                notes.append(VNote(abs_beat0 + b, d, m, syl, main_vowel(syl), line_id, i == 0))
                last_m = m
            line_id += 1
            bar_cursor += lb
    return notes


def lrc_lines(bp: Blueprint, notes: list[VNote]) -> list[tuple[float, str]]:
    """Mốc thời gian từng dòng lời (giây) để xuất .lrc cho Bravin làm video lời bài hát."""
    beat_s = 60.0 / bp.bpm
    texts = [l.text for s in bp.sections for l in s.lines]
    out = []
    for n in notes:
        if n.first_in_line and n.line_id < len(texts):
            out.append((n.beat * beat_s, texts[n.line_id]))
    return out
