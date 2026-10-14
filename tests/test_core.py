"""Kiểm thử lõi Micow (unittest, không cần thư viện ngoài ngoài numpy/scipy; phần mô hình cần torch).

Chạy: python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = tempfile.mkdtemp(prefix="micow-test-")
os.environ["MICOW_HOME"] = TMP

from micow.analysis import analyze  # noqa: E402
from micow.audio_io import SR, read_audio, write_wav  # noqa: E402
from micow.dsp import master  # noqa: E402
from micow.dsp.render import render  # noqa: E402
from micow.lyrics import language_of, main_vowel, parse_lyrics, syllables, to_engine_lyrics, vi_tone  # noqa: E402
from micow.planner import make_blueprint  # noqa: E402
from micow.styles import parse_style  # noqa: E402
from micow.theory import Key, parse_key, progression  # noqa: E402

LYRICS = """[Verse 1]
Chiều nay phố vắng mưa rơi trên vai
Em đi qua đây nghe tim nhói đau
[Điệp khúc]
Thôi đừng khóc nữa em ơi
Ngày mai nắng sẽ lên thôi
[Verse 2]
Đèn đường vàng hắt hiu trong đêm dài
Anh vẫn đứng đây chờ em quay lại
[Chorus]
Thôi đừng khóc nữa em ơi
Ngày mai nắng sẽ lên thôi"""


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class TheoryStyle(unittest.TestCase):
    def test_parse_key(self):
        cases = {"Am": "A minor", "C": "C major", "c#m": "C# minor", "Bb minor": "Bb minor", "La thứ": "A minor",
                 "Son thăng thứ": "Ab minor", "Đô trưởng": "C major", "F# major": "F# major"}
        for text, want in cases.items():
            self.assertEqual(parse_key(text).name(), want, text)
        self.assertIsNone(parse_key("I am happy today"))

    def test_harmonic_minor_chords_are_singable(self):
        names = [c.name() for c in progression(Key(9, "harmonic_minor"), ["i", "III", "V", "VII"])]
        self.assertEqual(names, ["Am", "C", "E", "G"])

    def test_style_parse(self):
        s = parse_style("ballad buồn, piano, giọng nam, 72 bpm, La thứ")
        self.assertEqual((s.genre, s.bpm, s.key.name(), s.vocal), ("ballad", 72, "A minor", "male"))
        self.assertIn("sad", s.moods)
        self.assertEqual(parse_style("nhạc sàn bay phòng").genre, "vinahouse")
        self.assertEqual(parse_style("trap 808 tối").genre, "trap")
        self.assertEqual(parse_style("UK drill tối, 808 trượt").genre, "drill")
        self.assertEqual(parse_style("vinahouse remix").genre, "vinahouse")

    def test_drill_pattern(self):
        from micow.dsp.patterns import Arranger
        bp = make_blueprint("beat", "drill", seed=3, duration=40)
        self.assertEqual(bp.style.genre, "drill")
        arr = Arranger(bp, np.random.default_rng(3))
        arr.drums(); arr.bass()
        b808 = [e for e in arr.events if e.inst == "808"]
        self.assertTrue(b808 and any(e.extra.get("glide") for e in b808), "drill cần 808 trượt")
        bar_s, step = bp.bar_seconds, 60.0 / bp.bpm / 4
        snares = {round((e.t % bar_s) / step) for e in arr.events if e.inst == "snare"}
        self.assertIn(8, snares)                       # snare phách 3 (nửa nhịp)
        self.assertTrue(snares & {13, 14, 15})         # snare "trễ" kiểu drill


class Lyrics(unittest.TestCase):
    def test_sections_and_tones(self):
        secs = parse_lyrics(LYRICS)
        self.assertEqual([s.kind for s in secs], ["verse", "chorus", "verse", "chorus"])
        self.assertEqual(len(secs[0].lines[0].syls), 8)
        self.assertEqual([vi_tone(w) for w in ["vắng", "chiều", "nhói", "nữa", "đây", "phố"]],
                         ["sac", "huyen", "sac", "nga", "ngang", "sac"])
        self.assertEqual(main_vowel("mưa"), "ɯ")
        self.assertEqual(language_of(LYRICS), "vi")
        self.assertEqual(language_of("Hold me close tonight"), "en")
        self.assertIn("[Chorus]", to_engine_lyrics(secs))

    def test_untagged_guesses_chorus(self):
        text = "a b c\nd e f\n\nla la la\nla la\n\ng h i\nj k\n\nla la la\nla la"
        kinds = [s.kind for s in parse_lyrics(text)]
        self.assertEqual(kinds.count("chorus"), 2)

    def test_english_syllables(self):
        self.assertEqual(len(syllables("beautiful morning")), 5)


class Planner(unittest.TestCase):
    def test_song_structure(self):
        bp = make_blueprint("song", "ballad buồn", LYRICS, seed=1)
        kinds = [s.kind for s in bp.sections]
        self.assertEqual(kinds[0], "intro")
        self.assertEqual(kinds[-1], "outro")
        self.assertEqual(kinds.count("chorus"), 2)
        self.assertTrue(all(s.bars % 4 == 0 for s in bp.sections))
        self.assertTrue(all(len(s.chords) == s.bars for s in bp.sections))

    def test_beat_duration_target(self):
        bp = make_blueprint("beat", "house", duration=120, seed=2)
        self.assertLess(abs(bp.duration - 120), 20)

    def test_reference_clip_sets_tempo(self):
        bp = make_blueprint("beat", "", reference={"bpm": 87.0, "key": Key(2, "minor").to_dict(), "key_confidence": 0.6,
                                                   "energy": 0.5, "percussive": 0.3, "brightness": 1500})
        self.assertEqual(bp.key.tonic, 2)
        self.assertIn(bp.bpm, (87, 174, 58, 130, 131))


class Audio(unittest.TestCase):
    def test_render_beat_and_analyze(self):
        bp = make_blueprint("beat", "house 124 bpm", duration=30, seed=3)
        r = render(bp)
        self.assertTrue(np.isfinite(r.mix).all())
        self.assertLessEqual(float(np.abs(r.mix).max()), 10 ** (-0.9 / 20))
        self.assertLess(abs(master.lufs(r.mix) + 14.0), 1.0)
        a = analyze(r.mix, SR)
        ratio = a["bpm"] / 124.0
        self.assertTrue(min(abs(ratio - k) for k in (0.5, 1, 2)) < 0.03, a["bpm"])

    def test_render_song_has_vocal_and_lrc(self):
        bp = make_blueprint("song", "vpop vui", LYRICS, seed=4)
        r = render(bp)
        self.assertIn("vocal", r.stems)
        self.assertEqual(len(r.lrc), 8)
        times = [t for t, _ in r.lrc]
        self.assertEqual(times, sorted(times))
        # dòng điệp khúc lặp lại phải cùng giai điệu
        by_line: dict[str, list[int]] = {}
        texts = [l.text for s in bp.sections for l in s.lines]
        for n in r.melody:
            by_line.setdefault(texts[n.line_id] + f"#{n.line_id}", []).append(n.midi)
        ch = [v for k, v in by_line.items() if k.startswith("Thôi đừng khóc")]
        self.assertEqual(ch[0], ch[1])

    def test_wav_roundtrip(self):
        x = (np.random.default_rng(0).standard_normal((SR, 2)) * 0.1).astype(np.float32)
        p = Path(TMP) / "rt.wav"
        write_wav(p, x, SR, bits=24)
        y = read_audio(p, SR)
        self.assertLess(float(np.abs(x - y).max()), 1e-4)

    def test_midi_with_lyrics(self):
        from micow.dsp.render import midi_tracks
        from micow.midi import write_midi
        bp = make_blueprint("song", "ballad", LYRICS, seed=5)
        r = render(bp)
        p = write_midi(Path(TMP) / "s.mid", bp.bpm, midi_tracks(r, bp), bp.key.tonic, bp.key.is_minor)
        data = p.read_bytes()
        self.assertTrue(data.startswith(b"MThd"))
        self.assertIn("vắng".encode(), data)


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from micow.server import make_server
        cls.srv = make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, data=None, headers=None, method=None):
        body = json.dumps(data).encode() if isinstance(data, dict) else data
        req = urllib.request.Request(self.base + path, data=body, headers=headers or {"Content-Type": "application/json"},
                                     method=method)
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw

    def test_health_ui_and_origin_guard(self):
        self.assertTrue(self.call("/api/health")["ok"])
        self.assertIn(b"Micow", self.call("/"))
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.call("/api/library", headers={"Origin": "https://evil.example"})
        self.assertEqual(cm.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError):
            self.call("/files/../../etc/passwd")

    def test_upload_generate_download(self):
        bp = make_blueprint("beat", "boom bap 90 bpm", duration=16, seed=6)
        p = Path(TMP) / "clip.wav"
        write_wav(p, render(bp).mix)
        up = self.call("/api/upload", p.read_bytes(), {"X-Filename": "clip.wav"})
        self.assertAlmostEqual(up["analysis"]["bpm"] / 90, 1, delta=0.05)
        plan = self.call("/api/plan", {"mode": "beat", "style": "", "clips": [{"id": up["id"], "use": "kit"}]})
        self.assertTrue(plan["sections"])
        job = self.call("/api/generate", {"mode": "beat", "style": "lofi", "duration": 20, "seed": 1,
                                          "clips": [{"id": up["id"], "use": "kit"}, {"id": up["id"], "use": "chop"}]})
        for _ in range(240):
            j = self.call(f"/api/jobs/{job['id']}")
            if j["status"] in ("done", "error"):
                break
            time.sleep(0.5)
        self.assertEqual(j["status"], "done", j.get("error"))
        files = j["result"]["files"]
        wav = self.call(f"/files/{job['id']}/{files['wav']}")
        self.assertTrue(wav[:4] == b"RIFF")
        self.assertIn("drums", files["stems"])
        lib = self.call("/api/library")
        self.assertTrue(any(it["id"] == job["id"] for it in lib))
        z = self.call(f"/api/library/{job['id']}/zip")
        self.assertTrue(z[:2] == b"PK")
        # Micow Ear nghe + cắt CapCut qua API
        lj = self.call("/api/ear/listen", {"ids": [up["id"]]})
        cj = self.call("/api/capcut", {"id": up["id"], "duration": 8, "mode": "hook"})
        for jid in (lj["id"], cj["id"]):
            for _ in range(240):
                j = self.call(f"/api/jobs/{jid}")
                if j["status"] in ("done", "error"):
                    break
                time.sleep(0.5)
            self.assertEqual(j["status"], "done", j.get("error"))
        self.assertIn("markers", j["result"]["files"])
        self.assertEqual(j["result"]["duration"], 8.0)
        bravin = self.call(f"/files/{cj['id']}/capcut.bravin.json")
        self.assertEqual(bravin["format"], "bravin-project")


class TrainPipeline(unittest.TestCase):
    def test_choose_preset_by_vram(self):
        from micow.model.pipeline import choose_preset
        self.assertEqual(choose_preset({"backend": "cpu", "vram_gb": 0})[0], "tiny")
        self.assertEqual(choose_preset({"backend": "cuda", "name": "RTX 4060 Laptop", "vram_gb": 8.0})[:2], ("small", 8))
        self.assertEqual(choose_preset({"backend": "cuda", "name": "RTX 3050", "vram_gb": 6.0})[:2], ("small", 4))
        self.assertEqual(choose_preset({"backend": "cuda", "name": "RTX 4090", "vram_gb": 24.0})[0], "base")
        self.assertEqual(choose_preset({"backend": "cuda", "name": "MX450", "vram_gb": 2.0})[0], "tiny")

    def test_manifest_from_folder(self):
        from micow.model.pipeline import build_manifest
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "nhac" / "drill").mkdir(parents=True)
            write_wav(tmp / "nhac" / "drill" / "bai1.wav", render(make_blueprint("beat", "drill", duration=20, seed=1)).mix, SR)
            (tmp / "nhac" / "drill" / "bai1.txt").write_text("[Verse]\nxin chào", encoding="utf-8")
            (tmp / "nhac" / "ghi_chu.md").write_text("không phải nhạc", encoding="utf-8")
            mf = build_manifest(tmp / "nhac", tmp / "work", log=lambda *_: None)
            items = [json.loads(l) for l in mf.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(items), 1)
            it = items[0]
            self.assertEqual(it["style"], "Drill")          # thể loại lấy từ tên thư mục
            self.assertIn("xin chào", it["lyrics"])
            self.assertTrue(it["sections"] and it["bpm"] > 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class EarCapCut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bp = make_blueprint("song", "vpop vui", LYRICS, seed=11)
        cls.mix = render(cls.bp).mix

    def test_ear_finds_hook_in_chorus(self):
        from micow.ear import listen
        r = listen(self.mix, SR)
        bs = self.bp.bar_seconds
        chorus = [(s.start_bar * bs, (s.start_bar + s.bars) * bs) for s in self.bp.sections if s.kind == "chorus"]
        h = r["hook"]
        ov = sum(max(0, min(h["end"], b) - max(h["start"], a)) for a, b in chorus) / (h["end"] - h["start"])
        self.assertGreaterEqual(ov, 0.5, (h, chorus))
        self.assertTrue(r["sections"] and r["peak"])
        true_down = np.arange(self.bp.total_bars + 1) * bs
        self.assertLess(min(abs(true_down - h["start"])), 0.08)

    def test_capcut_generate_exact_and_drop_on_time(self):
        from micow.ear import listen
        bp = make_blueprint("capcut", "vinahouse", "", seed=3, duration=20, peak_at=8.0, loop=True)
        r = render(bp)
        self.assertEqual(len(r.mix), int(20 * SR))
        drop = next(s.start_bar * bp.bar_seconds for s in bp.sections if s.kind == "drop")
        self.assertLess(abs(drop - 8.0), 1e-6)
        heard = listen(r.mix, SR)["peak"]["start"]
        self.assertLess(abs(heard - 8.0), 0.3)
        self.assertLess(abs(master.lufs(r.mix) + 14), 1.0)

    def test_cut_exact_length_and_peak_at(self):
        from micow.ear import listen
        from micow.ear.capcut import markers, plan_cut, render_cut
        ear = listen(self.mix, SR)
        total = len(self.mix) / SR
        plan = plan_cut(ear, total, 15.0, "peak_at", 6.0)
        y = render_cut(self.mix, plan)
        self.assertEqual(len(y), int(15 * SR))
        self.assertAlmostEqual(plan["anchor"] - plan["start"], 6.0, places=3)
        ms = markers(plan, ear)
        self.assertTrue(any(m["type"] == "drop" and abs(m["time"] - 6.0) < 1e-3 for m in ms))
        plan2 = plan_cut(ear, total, 60.0, "hook", None)  # dài hơn phần còn lại → lặp hook
        self.assertEqual(len(render_cut(self.mix, plan2)), int(60 * SR))

    def test_aggregate_many_clips(self):
        from micow.analysis import aggregate_reference
        a = [{"bpm": 70, "key": Key(9, "minor").to_dict(), "key_confidence": 0.5, "energy": 0.4},
             {"bpm": 141, "key": Key(9, "minor").to_dict(), "key_confidence": 0.6, "energy": 0.8},
             {"bpm": 72, "key": Key(0, "major").to_dict(), "key_confidence": 0.1, "energy": 0.6}]
        r = aggregate_reference(a)
        self.assertEqual(r["key"]["name"], "A minor")
        self.assertLess(abs(r["bpm"] - 70.5), 1.5)
        self.assertEqual(r["n_clips"], 3)


try:
    import torch  # noqa: F401
    HAS_TORCH = True
except Exception:
    HAS_TORCH = False


@unittest.skipUnless(HAS_TORCH, "cần PyTorch")
class Model(unittest.TestCase):
    def test_codec_and_lm(self):
        import torch
        from micow.model.codec import CodecConfig, MicowCodec
        from micow.model.lm import LMConfig, MicowLM, delay, undelay
        from micow.model.tokenizer import empty_text, encode_text
        torch.manual_seed(0)
        cc = CodecConfig.tiny()
        codec = MicowCodec(cc)
        wav = torch.randn(1, 1, cc.sample_rate) * 0.1
        y, codes, _ = codec(wav)
        self.assertEqual(y.shape, wav.shape)
        self.assertEqual(codes.shape, (1, cc.n_q, cc.sample_rate // cc.hop))
        lm = MicowLM(LMConfig.preset("tiny", n_q=cc.n_q, card=cc.codebook_size)).eval()
        self.assertTrue(torch.equal(undelay(delay(codes, lm.PAD), codes.shape[2]), codes))
        loss, _ = lm([encode_text("trap", "xin chào", "bpm:140")], codes)
        self.assertTrue(torch.isfinite(loss))
        # KV-cache khớp forward đầy đủ
        with torch.no_grad():
            pre, pm = lm.prefix([encode_text("lofi", "", ""), empty_text()], [codes[0][:, :5], None], "cpu")
            d = delay(codes, lm.PAD).expand(2, -1, -1)
            inp = torch.cat([torch.full((2, cc.n_q, 1), lm.BOS), d[:, :, :-1]], 2)
            full = lm._run(torch.cat([pre, lm.embed_frames(inp, 2)], 1),
                           torch.cat([pm, torch.ones(2, inp.shape[2], dtype=torch.bool)], 1))[:, pre.shape[1]:]
            caches = [dict() for _ in lm.blocks]
            v = torch.cat([pm, torch.ones(2, 1, dtype=torch.bool)], 1)
            hs = [lm._run(torch.cat([pre, lm.embed_frames(inp[:, :, :1], 2)], 1), v, caches)[:, -1]]
            for s in range(1, inp.shape[2]):
                v = torch.cat([v, torch.ones(2, 1, dtype=torch.bool)], 1)
                hs.append(lm._run(lm.embed_frames(inp[:, :, s:s + 1], 2), v, caches)[:, -1])
            self.assertLess(float((full - torch.stack(hs, 1)).abs().max()), 1e-4)
        loss2, _ = lm([encode_text("x")], codes, None, torch.randint(0, 10, (1, codes.shape[2])),
                      torch.randint(0, 8, (1, codes.shape[2])))
        self.assertTrue(torch.isfinite(loss2))
        out = lm.generate(encode_text("x"), 260, prompt=codes[0][:, :10], top_k=10,
                          struct=torch.randint(0, 10, (260,)), energy=torch.randint(0, 8, (260,)))
        self.assertEqual(out.shape, (cc.n_q, 260))
        self.assertTrue(bool((out >= 0).all()))
        self.assertTrue(torch.equal(out[:, :10], codes[0][:, :10]))


if __name__ == "__main__":
    unittest.main()
