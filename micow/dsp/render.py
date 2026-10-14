"""Dựng âm thanh từ Blueprint: sinh sự kiện → tổng hợp từng track → stem → mix → master.

Đây là engine "Micow Beat" (micow-dsp): chạy CPU, không cần tải mô hình, tạo được beat hoàn chỉnh
và bản demo bài hát (nhạc nền + giọng mẫu ngân theo giai điệu của lời).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..audio_io import SR
from ..planner import Blueprint
from . import fx, master, sampler, synth
from .melody import VNote, lrc_lines, make_melody
from .patterns import Arranger, Ev

PAN = {"chords": 0.0, "lead": 0.18, "vocal": 0.0}
LAYER_PAN = {"guitar": -0.35, "piano": 0.1, "epiano": -0.15, "strings": 0.3, "pad": 0.0, "bell": 0.4,
             "pluck": -0.25, "supersaw": 0.0, "organ": 0.2, "zither": -0.3, "flute": 0.2, "arp": 0.3}
DRUM_PAN = {"hat": 0.22, "ohat": 0.28, "shaker": -0.3, "rim": -0.12, "conga_hi": 0.35, "conga_lo": -0.25, "tom": -0.1, "crash": 0.15}


@dataclass
class RenderResult:
    mix: np.ndarray
    stems: dict[str, np.ndarray]
    events: list[Ev]
    melody: list[VNote]
    lrc: list[tuple[float, str]]
    stats: dict = field(default_factory=dict)


def _place(buf: np.ndarray, x: np.ndarray, t: float, gain: float = 1.0, p: float = 0.0):
    i = int(t * SR)
    if i >= len(buf) or len(x) == 0:
        return
    j = min(len(buf), i + len(x))
    seg = x[: j - i] * gain
    if buf.ndim == 2:
        a = (p + 1) * np.pi / 4
        buf[i:j, 0] += seg * np.cos(a) * 1.4142
        buf[i:j, 1] += seg * np.sin(a) * 1.4142
    else:
        buf[i:j] += seg


def _drum_sample(ev: Ev, kit: str, user_kit: dict[str, np.ndarray] | None) -> np.ndarray:
    v = round(min(1.2, ev.vel) * 8) / 8
    inst = ev.inst
    if user_kit:
        key = {"kick": "kick", "snare": "snare", "clap": "snare", "hat": "hat", "ohat": "hat"}.get(inst)
        if key and key in user_kit:
            synth_part = {"kick": synth.kick, "snare": synth.snare}.get(inst)
            s = user_kit[key] * v
            if synth_part is not None:  # trộn thêm 30% tiếng tổng hợp cho chắc
                b = synth_part(kit, 1.0) * v * 0.3
                L = max(len(s), len(b))
                s = np.pad(s, (0, L - len(s))) + np.pad(b, (0, L - len(b)))
            return s
    if inst == "kick":
        return synth.kick(kit, v)
    if inst == "snare":
        return synth.snare(kit, v)
    if inst == "clap":
        return synth.clap(v)
    if inst in ("hat", "ohat"):
        return synth.hat(inst == "ohat", v, kit)
    if inst == "rim":
        return synth.rim(v)
    if inst == "shaker":
        return synth.shaker(v)
    if inst == "tom":
        return synth.tom(float(ev.midi or 110.0), v, big=kit == "cinematic")
    if inst in ("conga_lo", "conga_hi"):
        return synth.conga(inst == "conga_hi", v)
    if inst == "crash":
        return synth.crash(v)
    return np.zeros(1, np.float32)


def render(bp: Blueprint, clips: list[dict] | None = None, gender: str | None = None,
           guide_vocal: bool = True, progress=None) -> RenderResult:
    """clips: [{"audio": ndarray (n,2) SR, "analysis": dict, "use": "style|loop|chop|kit"}]"""
    rng = np.random.default_rng(bp.seed)
    say = progress or (lambda p, m: None)
    gender = gender or (bp.style.vocal if bp.style.vocal != "none" else "female")
    total = int((bp.duration + 3.0) * SR)
    stems = {k: np.zeros((total, 2), np.float32) for k in ("drums", "bass", "chords", "lead", "vocal", "fx")}

    say(0.05, "Sắp xếp phần đệm")
    arr = Arranger(bp, rng)
    arr.drums()
    arr.bass()
    arr.chords()
    melody: list[VNote] = []
    if bp.mode == "song" and any(s.vocal for s in bp.sections):
        melody = make_melody(bp, gender=gender, seed=bp.seed)
    else:
        arr.hook()
    kit = bp.style.preset["drums"]

    user_kit = None
    clip_layers = []
    for c in clips or []:
        use = c.get("use", "style")
        a = c.get("analysis") or {}
        if use == "kit":
            user_kit = sampler.extract_kit(c["audio"], a) or None
        elif use == "loop":
            clip_layers.append(sampler.make_loop_layer(c["audio"], a, bp))
        elif use == "chop":
            clip_layers.append(sampler.make_chop_layer(c["audio"], a, bp, seed=bp.seed))

    say(0.15, "Tổng hợp trống và bass")
    kick_times = []
    for ev in arr.events:
        if ev.track == "drums":
            s = _drum_sample(ev, kit, user_kit)
            _place(stems["drums"], s, ev.t, 1.0, DRUM_PAN.get(ev.inst, 0.0))
            if ev.inst == "kick":
                kick_times.append(ev.t)
        elif ev.track == "bass":
            if ev.inst == "808":
                from ..theory import midi_to_hz
                y = synth.kick808(round(midi_to_hz(ev.midi), 2), round(ev.dur, 3), 1.0, round(ev.extra.get("glide", 0.0), 2))
            else:
                y = synth.bass_note(ev.inst, ev.midi, ev.dur, ev.vel)
            _place(stems["bass"], y, ev.t, ev.vel)
        elif ev.track == "fx":
            y = synth.riser(ev.dur) if ev.inst == "riser" else synth.impact()
            _place(stems["fx"], y, ev.t, ev.vel)

    say(0.35, "Tổng hợp hoà âm và giai điệu")
    cache: dict[tuple, np.ndarray] = {}
    for ev in arr.events:
        if ev.track not in ("chords", "lead"):
            continue
        k = (ev.inst, round(ev.midi, 2), round(ev.dur, 2), round(ev.vel, 1))
        y = cache.get(k)
        if y is None:
            y = synth.instrument(ev.inst, ev.midi, ev.dur, round(ev.vel, 1))
            cache[k] = y
        _place(stems[ev.track], y, ev.t, 1.0, LAYER_PAN.get(ev.inst, PAN[ev.track]))

    beat_s = 60.0 / bp.bpm
    if melody and guide_vocal:
        say(0.55, "Hát giọng mẫu theo giai điệu")
        for i, n in enumerate(melody):
            nxt = melody[i + 1].beat if i + 1 < len(melody) else n.beat + n.dur
            d = min(n.dur, max(0.1, nxt - n.beat)) * beat_s
            y, pre = synth.voice_note(n.midi, d, n.vowel, n.syl, 0.85, gender, seed=i)
            _place(stems["vocal"], y, max(0.0, n.beat * beat_s - pre), 1.0, 0.0)
    elif melody:
        lead = bp.style.lead
        for n in melody:
            _place(stems["lead"], synth.instrument(lead, n.midi, n.dur * beat_s, 0.7), n.beat * beat_s, 1.0, 0.1)

    say(0.7, "Xử lý hiệu ứng từng track")
    st = bp.style.preset
    if clip_layers:
        stems["sample"] = sum(clip_layers)[:total] if len(clip_layers) > 1 else clip_layers[0][:total]
        if len(stems["sample"]) < total:
            stems["sample"] = np.pad(stems["sample"], ((0, total - len(stems["sample"])), (0, 0)))
    if kit in ("lofi", "boombap"):
        stems["drums"] = fx.bitcrush(fx.lp(stems["drums"], 9000), 12, 1)
    stems["drums"] = fx.compress(stems["drums"], -18, 3.0, 3, 90)
    stems["bass"] = fx.lp(stems["bass"], 5000)
    stems["chords"] = fx.hp(stems["chords"], 160)
    stems["chords"] = fx.reverb(stems["chords"], 0.55, 0.5, st["reverb"])
    if "pad" in bp.style.layers or "strings" in bp.style.layers:
        stems["chords"] = fx.widen(stems["chords"], 11)
    stems["lead"] = fx.delay(fx.hp(stems["lead"], 250), beat_s * 0.75, 0.32, 0.22)
    stems["lead"] = fx.reverb(stems["lead"], 0.5, 0.5, st["reverb"] * 0.8)
    if melody:
        v = fx.hp(stems["vocal"], 120)
        v = fx.compress(v, -20, 3.0, 5, 120)
        v = fx.delay(v, beat_s * 0.5, 0.25, 0.12)
        stems["vocal"] = fx.reverb(v, 0.5, 0.45, 0.22 + st["reverb"] * 0.4)
    stems["fx"] = fx.reverb(stems["fx"], 0.8, 0.3, 0.4)
    if st.get("sidechain", 0) > 0 and kick_times:
        g = fx.sidechain_curve(total, kick_times, st["sidechain"], 0.6 * beat_s)[:, None]
        for name in ("bass", "chords", "lead", "sample"):
            if name in stems:
                stems[name] = stems[name] * (g if name != "bass" else g ** 0.7)
    if st.get("vinyl"):
        stems["vinyl"] = fx.vinyl(total, 0.6, bp.seed)

    say(0.85, "Mix và master")
    stems = {k: v for k, v in stems.items() if np.abs(v).max() > 1e-5}
    stems = master.balance(stems, bp.style.genre)
    # tự động hoá âm lượng theo năng lượng đoạn (nâng điệp khúc, hạ intro/outro)
    auto = np.ones(total, np.float32)
    for sec in bp.sections:
        i, j = int(sec.start_bar * bp.bar_seconds * SR), int((sec.start_bar + sec.bars) * bp.bar_seconds * SR)
        auto[i:j] = 0.75 + 0.3 * sec.energy
    auto = fx.one_pole(auto, np.exp(-1 / (SR * 0.25)))
    mix = sum(stems.values()) * auto[:, None]
    end = int((bp.duration + 1.8) * SR)
    mix = fx.fade(mix[:end], 0.0, 1.6)
    mix, mstats = master.master(mix, bp.style.genre)
    stems = {k: v[:end] for k, v in stems.items()}
    lrc = lrc_lines(bp, melody) if melody else []
    say(1.0, "Xong")
    return RenderResult(mix, stems, arr.events, melody, lrc, {**mstats, "events": len(arr.events), "notes": len(melody)})


def midi_tracks(res: RenderResult, bp: Blueprint) -> dict[str, list[dict]]:
    beat_s = 60.0 / bp.bpm
    tr: dict[str, list[dict]] = {"drums": [], "bass": [], "chords": [], "lead": [], "melody": []}
    for ev in res.events:
        if ev.track in tr:
            tr[ev.track].append({"beat": ev.t / beat_s, "dur": ev.dur / beat_s, "midi": ev.midi,
                                 "vel": min(1.0, ev.vel), "inst": ev.inst})
    for n in res.melody:
        tr["melody"].append({"beat": n.beat, "dur": n.dur, "midi": n.midi, "vel": 0.85, "inst": "voice", "lyric": n.syl})
    return tr
