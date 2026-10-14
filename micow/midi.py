"""Ghi tệp MIDI chuẩn (SMF type 1) không cần thư viện: trống, bass, hoà âm, lead, giai điệu kèm lời."""
from __future__ import annotations

import struct
from pathlib import Path

GM_DRUM = {"kick": 36, "snare": 38, "clap": 39, "hat": 42, "ohat": 46, "rim": 37, "tom": 45, "crash": 49,
           "shaker": 70, "conga_lo": 64, "conga_hi": 63}
GM_PROGRAM = {"piano": 0, "epiano": 4, "bell": 14, "organ": 16, "guitar": 25, "strings": 48, "strings_lead": 48,
              "pad": 89, "supersaw": 81, "pluck": 84, "arp": 81, "flute": 73, "zither": 107,
              "synth": 38, "sub": 38, "soft": 33, "pluck_bass": 33, "rolling": 38, "808": 38, "voice": 53}
PPQ = 480


def _vlq(n: int) -> bytes:
    n = max(0, int(n))
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]], name: str) -> bytes:
    events = [(0, b"\xff\x03" + _vlq(len(name.encode())) + name.encode())] + sorted(events, key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))
    data, last = b"", 0
    for tick, msg in events:
        data += _vlq(tick - last) + msg
        last = tick
    data += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + data


def write_midi(path: str | Path, bpm: float, tracks: dict[str, list[dict]], key_tonic: int = 0, minor: bool = False) -> Path:
    """tracks: {tên: [{"beat": float, "dur": float, "midi": int, "vel": 0..1, "inst": str, "lyric": str?}]}"""
    beat_ticks = lambda b: int(round(b * PPQ))
    tempo = int(60_000_000 / bpm)
    sharps = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}
    k = (key_tonic + (3 if minor else 0)) % 12
    meta = [(0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")), (0, b"\xff\x58\x04\x04\x02\x18\x08"),
            (0, b"\xff\x59\x02" + struct.pack("b", sharps[k]) + (b"\x01" if minor else b"\x00"))]
    chunks = [_track(meta, "Micow")]
    ch_next = 0
    for name, notes in tracks.items():
        if not notes:
            continue
        drums = name == "drums"
        ch = 9 if drums else ch_next
        if not drums:
            ch_next += 1
            if ch_next == 9:
                ch_next += 1
        evs: list[tuple[int, bytes]] = []
        if not drums:
            prog = GM_PROGRAM.get(notes[0].get("inst", ""), 0)
            evs.append((0, bytes([0xC0 | ch, prog])))
        for n in notes:
            pitch = GM_DRUM.get(n.get("inst", ""), 0) if drums else int(round(n["midi"]))
            if not (0 < pitch < 128):
                continue
            t0 = beat_ticks(n["beat"])
            t1 = max(t0 + 1, beat_ticks(n["beat"] + max(0.05, n["dur"])))
            v = max(1, min(127, int(n.get("vel", 0.8) * 110)))
            if n.get("lyric"):
                lb = n["lyric"].encode("utf-8")
                evs.append((t0, b"\xff\x05" + _vlq(len(lb)) + lb))
            evs.append((t0, bytes([0x90 | ch, pitch, v])))
            evs.append((t1, bytes([0x80 | ch, pitch, 0])))
        chunks.append(_track(evs, name))
    head = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ)
    path = Path(path)
    path.write_bytes(head + b"".join(chunks))
    return path
