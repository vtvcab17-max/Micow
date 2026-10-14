"""Đọc lời bài hát: thẻ đoạn ([Verse], [Điệp khúc]…), âm tiết, thanh điệu tiếng Việt, xuất LRC.

Cú pháp giống Suno/ACE-Step để dùng chung được:
    [Intro]
    [Verse 1]
    Dòng lời một
    Dòng lời hai
    [Chorus]
    ...
Không có thẻ nào → tự chia khổ theo dòng trống, khổ lặp lại nhiều nhất là điệp khúc.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

SECTION_ALIASES = {
    "intro": ["intro", "mo dau", "dao dau", "khoi dau"],
    "verse": ["verse", "phien khuc", "doan", "khổ", "kho", "v"],
    "prechorus": ["pre-chorus", "prechorus", "pre chorus", "tien diep khuc", "build"],
    "chorus": ["chorus", "diep khuc", "hook", "refrain", "dk"],
    "postchorus": ["post-chorus", "postchorus", "post chorus"],
    "bridge": ["bridge", "cau noi", "chuyen doan"],
    "drop": ["drop"],
    "break": ["break", "breakdown", "nghi"],
    "instrumental": ["instrumental", "interlude", "gian tau", "solo", "nhac"],
    "outro": ["outro", "ket", "ket thuc", "vi thanh", "end"],
}
CANON_VI = {"intro": "Mở đầu", "verse": "Phiên khúc", "prechorus": "Tiền điệp khúc", "chorus": "Điệp khúc",
            "postchorus": "Hậu điệp khúc", "bridge": "Cầu nối", "drop": "Drop", "break": "Nghỉ",
            "instrumental": "Gian tấu", "outro": "Kết"}
CANON_EN = {"intro": "Intro", "verse": "Verse", "prechorus": "Pre-Chorus", "chorus": "Chorus",
            "postchorus": "Post-Chorus", "bridge": "Bridge", "drop": "Drop", "break": "Break",
            "instrumental": "Instrumental", "outro": "Outro"}
VOCAL_SECTIONS = {"verse", "prechorus", "chorus", "postchorus", "bridge"}


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def canon_section(tag: str) -> str | None:
    t = strip_accents(tag).lower().strip()
    t = re.sub(r"[\d:]+.*$", "", t).strip(" -_")
    for canon, al in SECTION_ALIASES.items():
        for a in al:
            if t == strip_accents(a).lower():
                return canon
    for canon, al in SECTION_ALIASES.items():
        for a in al:
            a2 = strip_accents(a).lower()
            if len(a2) > 2 and t.startswith(a2):
                return canon
    return None


# ---------- thanh điệu tiếng Việt ----------
# ngang (không dấu), huyền (̀), sắc (́), hỏi (̉), ngã (̃), nặng (̣)
_TONE_MARKS = {"̀": "huyen", "́": "sac", "̉": "hoi", "̃": "nga", "̣": "nang"}
# Hướng cao độ tương đối dùng khi đặt giai điệu (để lời hát không bị "ngọng" thanh điệu)
TONE_CONTOUR = {"ngang": 0, "huyen": -1, "sac": 1, "hoi": -1, "nga": 1, "nang": -2}
_VI_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯ")


def vi_tone(syl: str) -> str | None:
    """Thanh điệu của một âm tiết tiếng Việt, None nếu không phải tiếng Việt rõ ràng."""
    d = unicodedata.normalize("NFD", syl)
    for ch in d:
        if ch in _TONE_MARKS:
            return _TONE_MARKS[ch]
    if any(c in _VI_CHARS for c in syl):
        return "ngang"
    return None


def main_vowel(syl: str) -> str:
    """Nguyên âm chính (để giọng mẫu ngân đúng màu nguyên âm): a e i o u (+ ư ơ → 'ɯ' 'ə')."""
    base = unicodedata.normalize("NFD", syl.lower())
    base = "".join(c for c in base if c not in _TONE_MARKS)
    base = unicodedata.normalize("NFC", base)
    order = ["ươ", "uô", "iê", "ưa", "ua", "ia", "ơ", "ư", "ô", "ê", "â", "ă", "a", "e", "o", "u", "i", "y"]
    for v in order:
        if v in base:
            return {"ươ": "ə", "uô": "o", "iê": "e", "ưa": "ɯ", "ua": "u", "ia": "i", "ơ": "ə", "ư": "ɯ", "ô": "o",
                    "ê": "e", "â": "ə", "ă": "a", "y": "i"}.get(v, v)
    return "a"


_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)


def syllables(line: str) -> list[str]:
    """Tách âm tiết. Tiếng Việt: mỗi chữ một âm tiết. Tiếng Anh: ước lượng theo cụm nguyên âm."""
    out: list[str] = []
    for w in _WORD.findall(line):
        if vi_tone(w) is not None or len(w) <= 3:
            out.append(w)
            continue
        groups = re.findall(r"[aeiouy]+", strip_accents(w).lower())
        n = len(groups)
        if n > 1 and w.lower().endswith("e") and not w.lower().endswith(("le", "ee")):
            n -= 1
        n = max(1, n)
        if n == 1:
            out.append(w)
        else:  # chia chữ thành n phần gần đều để gắn lên nốt
            k = len(w) / n
            out += [w[int(i * k): int((i + 1) * k)] for i in range(n)]
    return out


@dataclass
class LyricLine:
    text: str
    syls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"text": self.text, "syllables": len(self.syls)}


@dataclass
class LyricSection:
    kind: str                      # intro | verse | chorus | ...
    label: str = ""                # nhãn gốc người dùng viết
    lines: list[LyricLine] = field(default_factory=list)
    bars: int | None = None        # người dùng có thể ghi [Intro 8] = 8 ô nhịp

    @property
    def has_vocals(self) -> bool:
        return bool(self.lines)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label or CANON_VI.get(self.kind, self.kind),
                "lines": [l.to_dict() for l in self.lines], "bars": self.bars}


def _guess_structure(stanzas: list[list[str]]) -> list[LyricSection]:
    keyf = lambda st: " ".join(strip_accents(x).lower() for x in st)
    counts: dict[str, int] = {}
    for st in stanzas:
        counts[keyf(st)] = counts.get(keyf(st), 0) + 1
    chorus_key = max(counts, key=lambda k: counts[k]) if counts and max(counts.values()) > 1 else None
    out: list[LyricSection] = []
    seen_chorus = False
    for i, st in enumerate(stanzas):
        if chorus_key is not None and keyf(st) == chorus_key:
            kind = "chorus"
            seen_chorus = True
        elif chorus_key is None and len(stanzas) >= 2 and i % 2 == 1:
            kind = "chorus"  # không có khổ lặp: xen kẽ phiên khúc / điệp khúc
        elif seen_chorus and i == len(stanzas) - 1 and len(stanzas) > 3:
            kind = "bridge" if len(st) <= 4 else "verse"
        else:
            kind = "verse"
        out.append(LyricSection(kind, lines=[LyricLine(x, syllables(x)) for x in st]))
    return out


def parse_lyrics(text: str) -> list[LyricSection]:
    text = (text or "").replace("\r\n", "\n")
    sections: list[LyricSection] = []
    tagged = bool(re.search(r"^\s*\[[^\]]+\]\s*$", text, re.M))
    if not tagged:
        stanzas, cur = [], []
        for raw in text.split("\n"):
            s = raw.strip()
            if not s:
                if cur:
                    stanzas.append(cur)
                    cur = []
                continue
            if s.startswith("#"):
                continue
            cur.append(s)
        if cur:
            stanzas.append(cur)
        if len(stanzas) == 1 and len(stanzas[0]) > 8:  # một khối dài: cắt mỗi 4 dòng
            big = stanzas[0]
            stanzas = [big[i:i + 4] for i in range(0, len(big), 4)]
        return _guess_structure(stanzas)

    cur: LyricSection | None = None
    for raw in text.split("\n"):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", s)
        if m:
            tag = m.group(1).strip()
            kind = canon_section(tag) or "verse"
            nb = re.search(r"(\d+)\s*(?:bars?|o nhip|ô nhịp)?\s*$", tag)
            bars = None
            if nb and kind in ("intro", "outro", "instrumental", "break", "drop") and int(nb.group(1)) <= 64:
                bars = int(nb.group(1))
            cur = LyricSection(kind, label=tag, bars=bars)
            sections.append(cur)
            continue
        if cur is None:
            cur = LyricSection("verse")
            sections.append(cur)
        s = re.sub(r"\([^)]*\)", "", s).strip() or s  # bỏ ad-lib trong ngoặc khi tính âm tiết
        cur.lines.append(LyricLine(raw.strip(), syllables(s)))
    return sections


def language_of(text: str) -> str:
    """Đoán ngôn ngữ lời (vi/en/…) để báo cho engine ACE-Step."""
    words = _WORD.findall(text or "")
    if not words:
        return "unknown"
    vi = sum(1 for w in words if vi_tone(w) is not None and vi_tone(w) != "ngang") + \
        sum(1 for w in words if any(c in _VI_CHARS for c in w))
    if vi / len(words) > 0.15:
        return "vi"
    if re.search(r"[぀-ヿ]", text):
        return "ja"
    if re.search(r"[가-힯]", text):
        return "ko"
    if re.search(r"[一-鿿]", text):
        return "zh"
    return "en"


def to_engine_lyrics(sections: list[LyricSection]) -> str:
    """Chuẩn hoá về cú pháp thẻ tiếng Anh mà ACE-Step / Suno hiểu."""
    out, counts = [], {}
    for s in sections:
        counts[s.kind] = counts.get(s.kind, 0) + 1
        tag = CANON_EN.get(s.kind, s.kind.title())
        if s.kind == "verse":
            tag += f" {counts[s.kind]}"
        out.append(f"[{tag}]")
        out += [l.text for l in s.lines]
        out.append("")
    return "\n".join(out).strip()


def fmt_lrc_time(t: float) -> str:
    m, s = divmod(max(0.0, t), 60.0)
    return f"{int(m):02d}:{s:05.2f}"


def to_lrc(timed_lines: list[tuple[float, str]], title: str = "", artist: str = "Micow") -> str:
    out = []
    if title:
        out.append(f"[ti:{title}]")
    out.append(f"[ar:{artist}]")
    out.append("[by:Micow – Bravinall]")
    for t, line in timed_lines:
        out.append(f"[{fmt_lrc_time(t)}]{line}")
    return "\n".join(out) + "\n"
