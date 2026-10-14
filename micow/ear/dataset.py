"""Dữ liệu huấn luyện cho Micow Ear: bài tổng hợp có nhãn chính xác tuyệt đối.

Mỗi bài do Micow Beat dựng nên biết chắc: phách, đầu ô nhịp, từng đoạn (intro/verse/chorus/drop…),
năng lượng từng đoạn, đoạn hook và đoạn peak. Để mô hình không học thuộc âm sắc của bộ tổng hợp,
mỗi bài được **trộn lại ngẫu nhiên từ stem** (±7 dB từng stem, có thể tắt hẳn vài stem), lọc EQ,
thêm nhiễu và tự động hoá âm lượng chậm, rồi master lại.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from ..audio_io import SR, resample
from ..styles import GENRES

A_SR = 22050
WORDS = ("mưa rơi phố vắng em đi anh về nắng lên trời xanh gió bay mây trôi tim đau nhớ thương "
         "ngày mai đêm nay bên nhau xa xôi con đường ánh đèn câu ca giấc mơ hôm qua mãi mãi "
         "yêu thương lặng im chờ mong bước chân đôi tay nụ cười").split()
FORMS = [
    "IVCVCBCO", "VCVCBCC", "IVPCVPCBCO", "IVCVCO", "VVCVCC", "ICVCBCO", "IVPCVPCCO", "IVCICVCO",
    "VCVCIC", "IVVCVCBCO", "IVPCCVPCCBCO",
]
KIND = {"I": "Intro", "V": "Verse", "P": "Pre-Chorus", "C": "Chorus", "B": "Bridge", "O": "Outro", "N": "Instrumental", "D": "Drop", "K": "Break"}
BEAT_FORMS = ["IVCVCBCO", "IVDKDO", "IVPDKPDO", "ICVCO", "IVCVCNCO", "IKDKDO", "IVPCVPCO", "VCVCC"]


def _line(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(n)).capitalize()


def random_lyrics(rng: random.Random, vocal: bool) -> str:
    form = rng.choice(FORMS if vocal else BEAT_FORMS)
    chorus = [_line(rng, rng.randint(5, 9)) for _ in range(rng.choice([2, 4]))]
    pre = [_line(rng, rng.randint(5, 8)) for _ in range(2)]
    bridge = [_line(rng, rng.randint(5, 8)) for _ in range(rng.choice([2, 4]))]
    out = []
    for ch in form:
        out.append(f"[{KIND[ch]}]")
        if not vocal or ch in "IONDK":
            continue
        if ch == "C":
            out += chorus
        elif ch == "P":
            out += pre
        elif ch == "B":
            out += bridge
        else:
            out += [_line(rng, rng.randint(6, 10)) for _ in range(rng.choice([2, 4, 4]))]
    return "\n".join(out)


def make_song(seed: int) -> tuple[np.ndarray, dict]:
    """Dựng một bài + nhãn. Trả (audio mono 22,05 kHz, nhãn)."""
    from ..dsp import fx
    from ..dsp import master as M
    from ..dsp.render import render
    from ..planner import make_blueprint

    rng = random.Random(seed)
    g = rng.choice(list(GENRES))
    vocal = rng.random() < 0.6
    lyr = random_lyrics(rng, vocal)
    lo, hi = GENRES[g]["bpm"]
    bpm = int(rng.uniform(lo - 4, hi + 4))
    mood = rng.choice(["", "", "buồn", "vui", "chill", "sôi động"])
    bp = make_blueprint("song", f"{GENRES[g]['name']} {mood}", lyr, seed=seed, bpm=bpm)
    res = render(bp, gender=rng.choice(["female", "male"]), guide_vocal=rng.random() < 0.85)
    # trộn lại ngẫu nhiên từ stem
    mix = None
    for name, x in res.stems.items():
        gdb = rng.uniform(-7, 5)
        if name in ("fx", "vinyl") or (name in ("lead", "chords") and rng.random() < 0.1):
            gdb -= rng.choice([0, 0, 10, 30])
        y = x * 10 ** (gdb / 20)
        mix = y if mix is None else mix + y
    n = len(mix)
    if rng.random() < 0.5:
        mix = fx.lp(mix, rng.uniform(5000, 16000))
    if rng.random() < 0.4:
        mix = fx.hp(mix, rng.uniform(25, 140))
    if rng.random() < 0.3:  # tự động hoá âm lượng chậm (giống bản mix/radio edit)
        t = np.linspace(0, 1, n)
        mix = mix * (10 ** ((rng.uniform(-3, 3) * np.sin(2 * np.pi * rng.uniform(0.2, 1.5) * t + rng.random() * 6)) / 20))[:, None]
    mix = mix + np.random.default_rng(seed).standard_normal(mix.shape).astype(np.float32) * 10 ** (rng.uniform(-60, -38) / 20)
    mix, _ = M.master(mix, g, target_lufs=rng.uniform(-16, -9))
    mono = resample(mix.mean(axis=1), SR, A_SR)
    bs = bp.bar_seconds
    beat = 60.0 / bp.bpm
    total = bp.duration
    emax = max(s.energy for s in bp.sections)
    labels = {
        "seed": seed, "genre": g, "bpm": bp.bpm, "vocal": vocal, "duration": round(len(mono) / A_SR, 3),
        "beats": [round(k * beat, 4) for k in range(int(total / beat) + 1)],
        "downbeats": [round(k * bs, 4) for k in range(bp.total_bars + 1)],
        "sections": [{"kind": s.kind, "start": round(s.start_bar * bs, 4), "end": round((s.start_bar + s.bars) * bs, 4),
                      "energy": round(s.energy, 3), "vocal": s.vocal,
                      "hook": s.kind in ("chorus", "drop", "postchorus"),
                      "peak": s.energy >= emax - 0.035} for s in bp.sections],
    }
    return mono.astype(np.float32), labels


def _one(args):
    seed, out = args
    p = Path(out) / f"{seed:06d}.npz"
    if p.exists():
        return str(p)
    y, lab = make_song(seed)
    np.savez_compressed(p, audio=(np.clip(y, -1, 1) * 32767).astype(np.int16), labels=json.dumps(lab, ensure_ascii=False))
    return str(p)


def build(out: str | Path, n: int = 200, start: int = 0, workers: int = 4, log=print) -> list[str]:
    from multiprocessing import get_context
    Path(out).mkdir(parents=True, exist_ok=True)
    jobs = [(start + i, str(out)) for i in range(n)]
    done = []
    with get_context("spawn").Pool(workers) as pool:
        for i, p in enumerate(pool.imap_unordered(_one, jobs)):
            done.append(p)
            if (i + 1) % 10 == 0:
                log(f"dữ liệu Ear: {i + 1}/{n}")
    return sorted(done)


def load(path: str | Path) -> tuple[np.ndarray, dict]:
    d = np.load(path)
    return d["audio"].astype(np.float32) / 32767, json.loads(str(d["labels"]))
