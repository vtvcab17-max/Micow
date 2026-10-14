"""Bộ mã hoá văn bản của Micow-LM: byte UTF-8 (không âm vị, không từ điển).

Theo hướng "end-to-end, càng ít giả định càng tốt" mà CEO Suno mô tả: mô hình tự học cách đọc
phong cách và lời (cả tiếng Việt có dấu) từ byte. 256 byte + các token đặc biệt.
"""
from __future__ import annotations

SPECIALS = ["<pad>", "<style>", "<lyrics>", "<meta>", "<ref>", "</ref>", "<audio>", "<end>"]
VOCAB = 256 + len(SPECIALS)
SP = {s: 256 + i for i, s in enumerate(SPECIALS)}


def encode_text(style: str = "", lyrics: str = "", meta: str = "", max_len: int = 2048) -> list[int]:
    """[<style> bytes <meta> bytes <lyrics> bytes] – cắt bớt lời nếu quá dài."""
    s = list(style.encode("utf-8"))[:512]
    m = list(meta.encode("utf-8"))[:128]
    budget = max(0, max_len - len(s) - len(m) - 3)
    l = list(lyrics.encode("utf-8"))[:budget]
    return [SP["<style>"]] + s + [SP["<meta>"]] + m + [SP["<lyrics>"]] + l


def empty_text() -> list[int]:
    """Điều kiện rỗng cho classifier-free guidance."""
    return [SP["<style>"], SP["<meta>"], SP["<lyrics>"]]


def meta_string(bpm: int | None = None, key: str | None = None, duration: float | None = None,
                start: float | None = None) -> str:
    parts = []
    if bpm:
        parts.append(f"bpm:{int(bpm)}")
    if key:
        parts.append(f"key:{key}")
    if duration:
        parts.append(f"dur:{int(duration)}")
    if start is not None:
        parts.append(f"t:{int(start)}")
    return " ".join(parts)
