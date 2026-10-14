"""Phong cách (style): thể loại có sẵn + bộ đọc mô tả phong cách tiếng Việt / tiếng Anh.

`parse_style("ballad buồn piano giọng nữ 72 bpm La thứ")` → StyleSpec với thể loại, tempo, giọng,
năng lượng, nhạc cụ, giới tính giọng hát và một caption tiếng Anh cho các mô hình AI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .theory import Key, _strip_accents, parse_key

# Mỗi thể loại: tempo, điệu (mode), vòng hoà âm, bộ trống, bass, lớp hoà âm, lead, hiệu ứng.
GENRES: dict[str, dict] = {
    "vpop": dict(name="V-Pop", desc="Pop Việt tươi sáng, piano điện + pad + guitar",
                 bpm=(92, 112), mode="major", swing=0.0,
                 progs=[["I", "V", "vi", "IV"], ["vi", "IV", "I", "V"], ["I", "vi", "IV", "V"], ["IV", "V", "iii", "vi"]],
                 drums="pop", bass="synth", layers=["epiano", "pad", "guitar"], lead="pluck",
                 reverb=0.22, sidechain=0.0, caption="v-pop, modern pop, catchy, polished production",
                 kw=["pop", "vpop", "v-pop", "kpop", "k-pop", "tuoi sang", "nhac tre"]),
    "ballad": dict(name="Ballad", desc="Ballad chậm, piano + dây, cảm xúc",
                   bpm=(64, 80), mode="major", swing=0.0,
                   progs=[["I", "V", "vi", "iii", "IV", "I", "IV", "V"], ["vi", "IV", "I", "V"], ["I", "vi", "IV", "V"]],
                   drums="ballad", bass="soft", layers=["piano", "strings"], lead="flute",
                   reverb=0.38, sidechain=0.0, caption="emotional ballad, piano, strings, heartfelt",
                   kw=["ballad", "tinh ca", "tam trang", "piano ballad", "cham", "slow"]),
    "rnb": dict(name="R&B", desc="R&B / neo soul, hợp âm 7-9, groove lơi",
                bpm=(70, 95), mode="minor", swing=0.12,
                progs=[["i9", "iv7", "VII7", "III7"], ["VI7", "v7", "i7", "i7"], ["i7", "VI7", "iv7", "v7"]],
                drums="rnb", bass="synth", layers=["epiano", "pad"], lead="bell",
                reverb=0.3, sidechain=0.0, caption="r&b, neo soul, smooth, jazzy chords",
                kw=["rnb", "r&b", "r n b", "soul", "neo soul"]),
    "trap": dict(name="Trap", desc="Trap: 808 dài, hi-hat cuộn, giai điệu tối",
                 bpm=(130, 150), mode="harmonic_minor", swing=0.0,
                 progs=[["i", "VI", "III", "VII"], ["i", "iv", "VI", "V:maj"], ["i", "i", "VI", "VII"]],
                 drums="trap", bass="808", layers=["pad", "bell"], lead="pluck",
                 reverb=0.25, sidechain=0.0, half_time=True, caption="trap beat, heavy 808, rolling hi-hats, dark",
                 kw=["trap", "808", "rap viet", "rapviet", "rap"]),
    "drill": dict(name="Drill", desc="Drill (UK/NY/Việt): 808 trượt, hi-hat 3-3-2, snare lệch phách 3",
                  bpm=(138, 146), mode="harmonic_minor", swing=0.0,
                  progs=[["i", "VI", "iv", "V:maj"], ["i", "i", "VI", "V:maj"], ["i", "iv", "VI", "VII"]],
                  drums="drill", bass="808", layers=["strings", "piano", "pad"], lead="bell",
                  reverb=0.24, sidechain=0.0, half_time=True,
                  caption="drill beat, sliding 808 glides, syncopated hi-hats, dark strings, half-time",
                  kw=["drill", "uk drill", "ny drill", "drill viet", "drill vn", "808 truot", "808 slide"]),
    "boombap": dict(name="Boom Bap", desc="Hip hop cổ điển: trống mộc, swing, piano mẫu",
                    bpm=(84, 96), mode="minor", swing=0.18,
                    progs=[["i7", "iv7", "i7", "v7"], ["i", "VI", "iv", "v"], ["i7", "VII", "VI", "v7"]],
                    drums="boombap", bass="pluck_bass", layers=["piano", "strings"], lead="bell",
                    reverb=0.18, sidechain=0.0, caption="boom bap hip hop, dusty drums, jazzy sample",
                    kw=["boom bap", "boombap", "hip hop", "hiphop", "old school", "oldschool"]),
    "lofi": dict(name="Lo-fi", desc="Lo-fi chill: piano điện, đĩa than, swing nhẹ",
                 bpm=(70, 88), mode="major", swing=0.2,
                 progs=[["ii7", "V7", "I7", "vi7"], ["IV7", "iii7", "ii7", "I7"], ["vi7", "ii7", "V7", "I7"]],
                 drums="lofi", bass="pluck_bass", layers=["epiano", "pad"], lead="bell",
                 reverb=0.3, sidechain=0.0, vinyl=True, caption="lofi hip hop, chill, vinyl crackle, warm rhodes",
                 kw=["lofi", "lo-fi", "lo fi", "chillhop", "chill hop", "study", "hoc bai"]),
    "house": dict(name="House", desc="House 4/4, bass nảy, hi-hat mở phách lẻ",
                  bpm=(118, 126), mode="minor", swing=0.0,
                  progs=[["vi", "IV", "I", "V"], ["i", "VII", "VI", "VII"], ["i7", "iv7", "i7", "iv7"]],
                  drums="house", bass="synth", layers=["pad", "pluck"], lead="arp",
                  reverb=0.25, sidechain=0.45, caption="deep house, four on the floor, groovy bassline",
                  kw=["house", "deep house", "tech house", "disco"]),
    "edm": dict(name="EDM", desc="EDM / future bass: supersaw, sidechain mạnh, drop",
                bpm=(124, 150), mode="minor", swing=0.0,
                progs=[["VI", "VII", "i", "i"], ["i", "VI", "III", "VII"], ["IV", "V", "vi", "vi"]],
                drums="edm", bass="synth", layers=["supersaw", "pad"], lead="arp",
                reverb=0.3, sidechain=0.6, caption="edm, future bass, big supersaw chords, festival drop",
                kw=["edm", "future bass", "big room", "dance", "festival", "electronic", "dien tu"]),
    "vinahouse": dict(name="Vinahouse", desc="Nhạc sàn Việt: 4/4 nhanh, bass cuộn, sáo/lead nổi",
                      bpm=(132, 140), mode="harmonic_minor", swing=0.0,
                      progs=[["i", "VI", "VII", "i"], ["i", "iv", "V:maj", "i"], ["i", "VII", "VI", "V:maj"]],
                      drums="vinahouse", bass="rolling", layers=["pad", "pluck"], lead="flute",
                      reverb=0.22, sidechain=0.55, caption="vinahouse, vietnamese club music, rolling bass, energetic",
                      kw=["vinahouse", "vina house", "nhac san", "bay phong", "remix"]),
    "bolero": dict(name="Bolero", desc="Bolero / trữ tình: guitar, sáo, nhịp bolero",
                   bpm=(64, 76), mode="harmonic_minor", swing=0.0,
                   progs=[["i", "iv", "V:maj", "i"], ["i", "VI", "iv", "V:maj"], ["i", "III", "iv", "V:maj"]],
                   drums="bolero", bass="soft", layers=["guitar", "strings"], lead="flute",
                   reverb=0.35, sidechain=0.0, caption="vietnamese bolero, nostalgic, acoustic guitar, flute",
                   kw=["bolero", "tru tinh", "nhac vang", "que huong", "nhac xua"]),
    "cinematic": dict(name="Cinematic", desc="Điện ảnh / hùng tráng: dây, trống lớn, chuông",
                      bpm=(80, 100), mode="minor", swing=0.0,
                      progs=[["i", "VI", "III", "VII"], ["i", "iv", "VI", "V:maj"], ["VI", "VII", "i", "i"]],
                      drums="cinematic", bass="sub", layers=["strings", "pad", "bell"], lead="strings_lead",
                      reverb=0.45, sidechain=0.0, caption="cinematic, epic orchestral, big drums, strings",
                      kw=["cinematic", "epic", "orchestral", "phim", "hung trang", "soundtrack", "trailer"]),
}

DEFAULT_GENRE = "vpop"

MOODS = {
    "sad": (["buon", "sad", "melancholy", "tam trang", "co don", "chia tay", "that tinh", "khoc"], dict(mode="minor", bpm=0.94, energy=-0.15)),
    "happy": (["vui", "happy", "tuoi", "upbeat", "yeu doi", "hanh phuc", "cheerful", "rang ro"], dict(mode="major", bpm=1.05, energy=0.12)),
    "energetic": (["soi dong", "energetic", "manh", "cuong chay", "hype", "quay", "bung no"], dict(bpm=1.06, energy=0.25)),
    "chill": (["chill", "thu gian", "nhe nhang", "soft", "relax", "em diu", "mellow"], dict(bpm=0.95, energy=-0.2)),
    "dark": (["dark", "toi", "u am", "ma mi", "bi an", "gangster"], dict(mode="minor", energy=0.05)),
    "romantic": (["lang man", "romantic", "tinh yeu", "love", "ngot ngao"], dict(energy=-0.05)),
    "epic": (["epic", "hung trang", "hoanh trang", "anh hung"], dict(energy=0.25)),
}

INSTRUMENT_KW = {
    "piano": ["piano", "duong cam", "dan piano"],
    "epiano": ["rhodes", "epiano", "e-piano", "piano dien"],
    "guitar": ["guitar", "ghi ta", "ghita", "acoustic"],
    "strings": ["strings", "violin", "cello", "dan day", "vi o lon"],
    "flute": ["flute", "sao", "sao truc"],
    "zither": ["dan tranh", "zither", "dan bau", "dan toc", "nhac cu dan toc"],
    "bell": ["bell", "chuong", "glockenspiel", "music box"],
    "pad": ["pad", "synth pad", "ambient"],
    "supersaw": ["supersaw", "synth", "synthwave"],
    "arp": ["arp", "arpeggio", "rai not"],
    "organ": ["organ", "dan organ"],
}
INSTR_CAPTION = {"piano": "piano", "epiano": "rhodes electric piano", "guitar": "acoustic guitar",
                 "strings": "strings", "flute": "bamboo flute", "zither": "vietnamese dan tranh zither",
                 "bell": "bells", "pad": "warm synth pads", "supersaw": "supersaw synths", "arp": "arpeggiated synth",
                 "organ": "organ", "pluck": "synth plucks"}


@dataclass
class StyleSpec:
    genre: str = DEFAULT_GENRE
    bpm: int = 100
    key: Key = field(default_factory=lambda: Key(9, "minor"))
    energy: float = 0.6                  # 0..1
    swing: float = 0.0
    layers: list[str] = field(default_factory=list)
    lead: str = "pluck"
    moods: list[str] = field(default_factory=list)
    vocal: str = "female"                # female | male | none
    explicit_bpm: bool = False
    explicit_key: bool = False
    text: str = ""

    @property
    def preset(self) -> dict:
        return GENRES[self.genre]

    def caption(self, instrumental: bool = False) -> str:
        """Caption tiếng Anh cho ACE-Step / MusicGen (các mô hình học bằng thẻ tiếng Anh)."""
        p = self.preset
        parts = [p["caption"]]
        parts += [m for m in self.moods]
        parts += [INSTR_CAPTION.get(i, i) for i in self.layers[:4]]
        if not instrumental and self.vocal != "none":
            parts.append(f"{self.vocal} vocal")
        if instrumental:
            parts.append("instrumental")
        parts.append(f"{self.bpm} bpm")
        parts.append(self.key.name())
        user = self.text.strip()
        cap = ", ".join(dict.fromkeys(parts))
        return f"{cap}. {user}" if user else cap

    def to_dict(self) -> dict:
        return {"genre": self.genre, "genre_name": self.preset["name"], "bpm": self.bpm, "key": self.key.to_dict(),
                "energy": round(self.energy, 2), "swing": self.swing, "layers": self.layers, "lead": self.lead,
                "moods": self.moods, "vocal": self.vocal, "caption": self.caption()}


def detect_genre(text: str) -> str | None:
    t = " " + _strip_accents(text).lower() + " "
    best, score = None, 0
    for gid, g in GENRES.items():
        for kw in g["kw"]:
            if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", t):
                s = len(kw) + (5 if kw == gid else 0)
                if s > score:
                    best, score = gid, s
    return best


def parse_style(text: str = "", genre: str | None = None, bpm: int | None = None, key: str | Key | None = None,
                energy: float | None = None, seed: int = 0) -> StyleSpec:
    text = text or ""
    plain = " " + _strip_accents(text).lower() + " "
    gid = genre if genre in GENRES else (detect_genre(text) or DEFAULT_GENRE)
    g = GENRES[gid]
    spec = StyleSpec(genre=gid, text=text, swing=g["swing"], layers=list(g["layers"]), lead=g["lead"])

    # tâm trạng
    mode_override, bpm_mul, e = None, 1.0, 0.6
    for mid, (kws, eff) in MOODS.items():
        if any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", plain) for k in kws):
            spec.moods.append(mid)
            mode_override = eff.get("mode", mode_override)
            bpm_mul *= eff.get("bpm", 1.0)
            e += eff.get("energy", 0.0)
    if gid in ("edm", "vinahouse", "trap", "drill"):
        e += 0.15
    if gid in ("ballad", "lofi", "bolero"):
        e -= 0.1
    spec.energy = float(min(1.0, max(0.15, energy if energy is not None else e)))

    # tempo
    m = re.search(r"(\d{2,3})\s*(?:bpm|nhip/phut|nhip)", plain)
    lo, hi = g["bpm"]
    if bpm:
        spec.bpm, spec.explicit_bpm = int(bpm), True
    elif m:
        spec.bpm, spec.explicit_bpm = int(m.group(1)), True
    else:
        base = lo + (hi - lo) * (0.35 + 0.3 * ((seed * 7919) % 100) / 100.0)
        spec.bpm = int(round(min(hi + 6, max(lo - 6, base * bpm_mul))))

    # giọng (key)
    k = key if isinstance(key, Key) else parse_key(key) if key else None
    if k is None:
        k = parse_key(text) if re.search(r"\b[A-G][#b]?\s*(m|min|minor|maj|major)\b|\b(truong|thu)\b", text + " " + plain) else None
    if k is not None:
        spec.key, spec.explicit_key = k, True
    else:
        tonics = [9, 4, 2, 7, 0, 5, 11] if g["mode"] != "major" else [0, 7, 2, 9, 5, 4]
        tonic = tonics[(seed * 31) % len(tonics)]
        mode = g["mode"]
        if mode_override == "minor" and mode == "major":
            mode = "minor"
        elif mode_override == "major" and mode in ("minor",):
            mode = "major"
        spec.key = Key(tonic, mode)

    # nhạc cụ được nhắc tới → thêm lớp
    for inst, kws in INSTRUMENT_KW.items():
        if any(re.search(r"(?<![a-z])" + re.escape(k2) + r"(?![a-z])", plain) for k2 in kws):
            if inst in ("flute", "zither"):
                spec.lead = inst
            if inst not in spec.layers and inst not in ("flute",):
                spec.layers.insert(0, inst)
    spec.layers = spec.layers[:4]

    # giọng hát
    if re.search(r"giong nam|male|nam ca si|boy", plain) and not re.search(r"female|giong nu", plain):
        spec.vocal = "male"
    elif re.search(r"khong loi|instrumental|beat only|khong hat", plain):
        spec.vocal = "none"
    return spec


def genre_list() -> list[dict]:
    return [{"id": k, "name": v["name"], "desc": v["desc"], "bpm": list(v["bpm"]), "mode": v["mode"]}
            for k, v in GENRES.items()]
