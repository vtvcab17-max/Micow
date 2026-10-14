"""Nhạc lý tối thiểu: nốt, giọng (key), âm giai, hợp âm, vòng hoà âm, dẫn giọng."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B", "Fb": "E"}
# Tên nốt tiếng Việt (Đô Rê Mi Fa Son La Si)
_VN_NOTES = {"do": "C", "re": "D", "mi": "E", "fa": "F", "son": "G", "sol": "G", "la": "A", "si": "B"}

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}


def midi_to_hz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69.0) / 12.0)


DISPLAY_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]  # cách viết thông dụng trong pop


def note_name(pc: int) -> str:
    return DISPLAY_NAMES[pc % 12]


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


@dataclass
class Key:
    tonic: int = 9          # A
    mode: str = "minor"     # major | minor | harmonic_minor | dorian | mixolydian

    @property
    def scale(self) -> list[int]:
        # thứ hoà âm: giai điệu dùng âm giai tự nhiên, nốt nâng (bậc 7) chỉ xuất hiện qua hợp âm V trưởng
        if self.mode == "harmonic_minor":
            return SCALES["minor"]
        return SCALES.get(self.mode, SCALES["minor"])

    @property
    def is_minor(self) -> bool:
        return self.mode in ("minor", "harmonic_minor", "dorian")

    def name(self) -> str:
        return f"{note_name(self.tonic)} {'minor' if self.is_minor else 'major'}"

    def name_vi(self) -> str:
        vn = {"C": "Đô", "D": "Rê", "E": "Mi", "F": "Fa", "G": "Son", "A": "La", "B": "Si"}
        n = note_name(self.tonic)
        base = vn[n[0]] + (" thăng" if "#" in n else " giáng" if n.endswith("b") else "")
        return f"{base} {'thứ' if self.is_minor else 'trưởng'}"

    def to_dict(self) -> dict:
        return {"tonic": self.tonic, "mode": self.mode, "name": self.name(), "name_vi": self.name_vi()}

    def degree_pc(self, degree: int) -> int:
        """Bậc (0-based, có thể âm/vượt 7) → pitch class."""
        sc = self.scale
        octave, idx = divmod(degree, 7)
        return (self.tonic + sc[idx] + 12 * octave) % 12

    def degree_midi(self, degree: int, base_octave: int = 4) -> int:
        sc = self.scale
        octave, idx = divmod(degree, 7)
        return 12 * (base_octave + 1) + self.tonic + sc[idx] + 12 * octave


def parse_key(text: str) -> Key | None:
    """'C major', 'Am', 'F#m', 'Bb minor', 'La thứ', 'Đô trưởng', 'Son thăng thứ'…"""
    if not text:
        return None
    t = text.strip()
    short = len(t) <= 5  # ô nhập giọng riêng ("Am", "F#", "c#m") được phép viết thường / thiếu chất lượng
    pat = r"(?<![A-Za-z])([A-G" + ("a-g" if short else "") + r"])([#b♯♭]?)\s*(maj(?:or)?|min(?:or)?|m(?![a-z]))?(?![A-Za-z#])"
    cands = list(re.finditer(pat, t))
    with_q = [c for c in cands if c.group(3)]
    m = with_q[0] if with_q else (cands[0] if cands and short else None)
    plain = _strip_accents(t).lower()
    vn = re.search(r"\b(do|re|mi|fa|son|sol|la|si)\s*(thang|giang)?\s*(truong|thu)\b", plain)
    if vn:
        n = _VN_NOTES[vn.group(1)]
        pc = NOTE_NAMES.index(n) + (1 if vn.group(2) == "thang" else -1 if vn.group(2) == "giang" else 0)
        return Key(pc % 12, "minor" if vn.group(3) == "thu" else "major")
    if not m:
        return None
    letter = m.group(1).upper()
    acc = m.group(2).replace("♯", "#").replace("♭", "b")
    name = letter + acc
    name = _FLATS.get(name, name)
    if name not in NOTE_NAMES:
        return None
    q = (m.group(3) or "").lower()
    mode = "minor" if q.startswith("m") and not q.startswith("maj") else "major"
    if not q and m.group(1).islower():
        mode = "minor"
    return Key(NOTE_NAMES.index(name), mode)


# ---------------- hợp âm ----------------
@dataclass
class Chord:
    root_pc: int
    quality: str           # maj | min | dim | aug | sus2 | sus4
    sevenths: int = 0      # 0 = tam hợp; 7 = thêm quãng 7; 9 = thêm 7 + 9
    degree: int = 0        # bậc trong giọng (0-based)
    seventh_iv: int = 10   # quãng của nốt 7 (11 = maj7, 10 = 7 thường, 9 = 7 giảm) – lấy theo âm giai

    def intervals(self) -> list[int]:
        base = {"maj": [0, 4, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
                "sus2": [0, 2, 7], "sus4": [0, 5, 7]}[self.quality]
        if self.sevenths >= 7:
            base = base + [self.seventh_iv]
        if self.sevenths >= 9:
            base = base + [14]
        return base

    def pcs(self) -> list[int]:
        return [(self.root_pc + i) % 12 for i in self.intervals()]

    def name(self) -> str:
        r = note_name(self.root_pc)
        if not self.sevenths:
            return r + {"maj": "", "min": "m", "dim": "dim", "aug": "aug", "sus2": "sus2", "sus4": "sus4"}[self.quality]
        ext = "9" if self.sevenths >= 9 else "7"
        if self.quality == "maj":
            return r + ("maj" + ext if self.seventh_iv == 11 else ext)
        if self.quality == "min":
            return r + "m" + ("maj" + ext if self.seventh_iv == 11 else ext)
        if self.quality == "dim":
            return r + ("dim7" if self.seventh_iv == 9 else "m7b5")
        return r + {"aug": "aug", "sus2": "sus2", "sus4": "sus4"}[self.quality] + ext


def diatonic_chord(key: Key, degree: int, sevenths: int = 0) -> Chord:
    # Thứ hoà âm: hợp âm lấy từ thứ tự nhiên (tránh III+ và VII°), riêng bậc V là trưởng (át chủ)
    harm = key.mode == "harmonic_minor"
    sc = SCALES["minor"] if harm else key.scale
    d = degree % 7
    root = (key.tonic + sc[d]) % 12
    third = (sc[(d + 2) % 7] - sc[d]) % 12
    fifth = (sc[(d + 4) % 7] - sc[d]) % 12
    seventh = (sc[(d + 6) % 7] - sc[d]) % 12
    if third == 4 and fifth == 7:
        q = "maj"
    elif third == 3 and fifth == 7:
        q = "min"
    elif third == 3 and fifth == 6:
        q = "dim"
    else:
        q = "aug"
    if harm and d == 4:
        q, seventh = "maj", 10
    return Chord(root, q, sevenths, d, seventh)


_ROMAN = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}


def parse_roman(key: Key, token: str) -> Chord:
    """'I', 'vi', 'IV7', 'V', 'bVII', 'V/maj' … theo giọng. Chữ hoa/thường chỉ để dễ đọc;
    chất lượng hợp âm lấy theo âm giai, trừ khi có hậu tố :maj/:min (ví dụ 'V:maj' trong giọng thứ)."""
    t = token.strip()
    force = None
    if ":" in t:
        t, force = t.split(":", 1)
    sev = 9 if t.endswith("9") else 7 if t.endswith("7") else 0
    t = t.rstrip("79")
    flat = t.startswith("b")
    t = t.lstrip("b")
    deg = _ROMAN[t.lower()]
    ch = diatonic_chord(key, deg, sev)
    if flat:
        ch.root_pc = (ch.root_pc - 1) % 12
    if force:
        ch.quality = force
    return ch


def progression(key: Key, romans: list[str]) -> list[Chord]:
    return [parse_roman(key, r) for r in romans]


def voice_chord(ch: Chord, prev: list[int] | None, low: int = 52, high: int = 76) -> list[int]:
    """Chọn thế bấm (inversion) gần thế trước nhất để dẫn giọng mượt."""
    ints = ch.intervals()
    cands = []
    for base in range(low - 12, high):
        if base % 12 != ch.root_pc:
            continue
        notes = sorted(base + i for i in ints)
        for inv in range(len(notes)):
            v = sorted(notes[inv:] + [n + 12 for n in notes[:inv]])
            if v[0] >= low and v[-1] <= high + 4:
                cands.append(v)
    if not cands:
        b = 60 + (ch.root_pc - 60) % 12
        return [b + i for i in ints]
    if not prev:
        center = (low + high) / 2
        return min(cands, key=lambda v: abs(sum(v) / len(v) - center))

    def cost(v):
        return sum(min(abs(a - b) for b in prev) for a in v) + 0.5 * abs(len(v) - len(prev))
    return min(cands, key=cost)


def nearest_in_scale(midi: int, key: Key) -> int:
    pcs = {(key.tonic + s) % 12 for s in key.scale}
    for d in (0, -1, 1, -2, 2):
        if (midi + d) % 12 in pcs:
            return midi + d
    return midi
