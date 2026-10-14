"""Dòng lệnh Micow.

  micow serve [--open] [--port 5690] [--lan]      chạy giao diện web cục bộ
  micow beat  --style "trap tối 140 bpm" [--clip a.wav:kit] [--duration 90] [--out thu_muc]
  micow song  --style "ballad buồn piano" --lyrics loi.txt [--engine micow-dsp|ace-step|micow-lm]
  micow analyze clip.wav                          tempo, giọng, năng lượng của một đoạn nhạc
  micow plan  --style ... --lyrics loi.txt        xem bản thiết kế bài (cấu trúc, hợp âm)
  micow engines | micow info
  micow install ace-step [--with-base]           cài ACE-Step 1.5 + tải trọng số
  micow data synth --out data --n 50              dữ liệu tổng hợp để huấn luyện Micow-LM
  micow train codec|tokenize|lm ...               huấn luyện mô hình riêng
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from . import DEFAULT_PORT, __version__, paths


class CliJob:
    """Job chạy đồng bộ, in tiến độ ra màn hình."""

    def __init__(self, kind: str, params: dict | None = None):
        import threading
        self.id = time.strftime("%Y%m%d-%H%M%S-cli")
        self.kind = kind
        self.params = params or {}
        self.created = time.time()
        self.cancel = threading.Event()
        self._last = ""

    def update(self, progress=None, message=None):
        if message and message != self._last:
            pct = f"{int((progress or 0) * 100):3d}%" if progress is not None else "    "
            print(f"  {pct}  {message}", flush=True)
            self._last = message


def _load_text(v: str | None) -> str:
    if not v:
        return ""
    if v == "-":
        return sys.stdin.read()
    p = Path(v)
    return p.read_text(encoding="utf-8") if p.exists() else v.replace("\\n", "\n")


def _gen(args, mode: str):
    from .engines import GenRequest, get, load_clip
    from .uploads import add_upload_file
    clips = []
    for spec in args.clip or []:
        path, _, use = spec.partition(":")
        meta = add_upload_file(path)
        a = meta["analysis"]
        print(f"  clip {Path(path).name}: {a.get('bpm')} BPM, {a['key']['name_vi']}, loại {a.get('kind')} → dùng '{use or 'style'}'")
        clips.append({"id": meta["id"], "use": use or "style"})
    req = GenRequest.from_dict({"mode": mode, "engine": args.engine, "style": args.style or "", "genre": args.genre,
                                "title": args.title or "", "lyrics": _load_text(getattr(args, "lyrics", None)),
                                "duration": args.duration, "bpm": args.bpm, "key": args.key, "seed": args.seed,
                                "gender": args.gender, "guide_vocal": not args.no_vocal, "clips": clips,
                                "peak_at": getattr(args, "peak_at", None), "loop": getattr(args, "loop", False)})
    eng = get(req.engine)
    job = CliJob("generate", req.to_dict())
    loaded = []
    for c in req.clips:
        cl = load_clip(c["id"])
        cl["use"] = c["use"]
        if cl["use"] == "hook":
            from .ear import listen_upload
            cl["ear"] = listen_upload(c["id"])
        loaded.append(cl)
    print(f"♪ {eng.name}: {mode} · seed {req.seed}")
    if mode == "capcut" and eng.id != "micow-dsp":
        from .service import _capcut_via_cut
        meta = _capcut_via_cut(job, eng, req, loaded)
    else:
        meta = eng.generate(job, req, loaded)
    src = paths.library() / job.id
    out = src
    if args.out:
        out = Path(args.out)
        if out.exists():
            shutil.rmtree(out) if out.is_dir() else out.unlink()
        shutil.copytree(src, out)
    print(f"✓ {meta['title']} – {meta['duration']} giây, {meta.get('bpm')} BPM, {meta['key']['name_vi']}"
          f", {meta.get('stats', {}).get('lufs', '?')} LUFS")
    print(f"  Tệp: {out}")
    for s in meta.get("sections", []):
        print(f"   {s['start']:7.1f}s  {s['label']:<16} {s['bars']:>3} ô nhịp  {' '.join(s['chords'][:4])}")


def _capcut(args):
    from .ear.capcut import plan_cut, render_cut, save_cut
    if args.gen or not args.files:
        ns = argparse.Namespace(**vars(args))
        ns.genre = None
        ns.title = None
        ns.bpm = None
        ns.key = None
        ns.gender = None
        ns.no_vocal = False
        ns.clip = [f + ":style" for f in args.files]
        ns.mode_capcut = True
        return _gen(ns, "capcut")
    from .audio_io import SR, read_audio
    from .ear import listen
    mode = "peak_at" if args.peak_at is not None else args.mode
    for fpath in args.files:
        x = read_audio(fpath, SR)
        ear = listen(x, SR)
        plan = plan_cut(ear, len(x) / SR, args.duration, mode, args.peak_at, args.candidate, args.snap_end)
        y = render_cut(x, plan, loop=args.loop)
        name = Path(fpath).stem
        job = CliJob("capcut")
        folder = paths.library() / job.id
        meta = {"id": job.id, "title": f"{name} · {mode} {args.duration:g}s", "mode": "capcut", "engine": "micow-ear",
                "engine_name": "Micow Ear · cắt", "bpm": ear["bpm"], "key": ear["key"], "genre_name": "CapCut",
                "source": {"name": Path(fpath).name, "start": plan["start"], "end": plan["end"]}, "created": job.created}
        out = save_cut(folder, meta["title"], y, plan, ear, meta)
        dst = folder
        if args.out:
            dst = Path(args.out) / (name + f"_{mode}_{int(args.duration)}s")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(folder, dst)
        print(f"✓ {Path(fpath).name}: cắt {plan['start']:.2f}s → {plan['end']:.2f}s ({out['duration']} giây, {mode})"
              + (f" – {plan['note']}" if plan.get("note") else ""))
        print(f"  Tệp: {dst}  (mix.mp3/wav, markers.csv, capcut.bravin.json)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="micow", description="Micow – mô hình làm nhạc chạy trên máy (hệ sinh thái Bravinall)")
    ap.add_argument("--version", action="version", version=f"Micow {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="chạy giao diện web cục bộ")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--lan", action="store_true", help="mở cho máy khác trong mạng LAN (0.0.0.0)")
    s.add_argument("--open", action="store_true", help="tự mở trình duyệt")

    for name in ("beat", "song"):
        g = sub.add_parser(name, help="tạo beat" if name == "beat" else "tạo bài hát từ lời + phong cách")
        g.add_argument("--style", "-s", default="")
        g.add_argument("--genre")
        g.add_argument("--title")
        if name == "song":
            g.add_argument("--lyrics", "-l", help="tệp lời, '-' để đọc stdin, hoặc chuỗi (\\n xuống dòng)")
        g.add_argument("--engine", "-e", default="micow-dsp")
        g.add_argument("--duration", "-d", type=float)
        g.add_argument("--bpm", type=int)
        g.add_argument("--key")
        g.add_argument("--seed", type=int)
        g.add_argument("--gender", choices=["female", "male"])
        g.add_argument("--no-vocal", action="store_true", help="không hát giọng mẫu (dùng lead thay)")
        g.add_argument("--clip", "-c", action="append", help="tệp[:style|loop|chop|kit|hook|cover|complete]")
        g.add_argument("--out", "-o", help="chép kết quả ra thư mục này")

    a = sub.add_parser("analyze", help="phân tích đoạn nhạc")
    a.add_argument("files", nargs="+")

    e = sub.add_parser("ear", help="Micow Ear: nghe nhiều bài, tìm cấu trúc, hook, peak")
    e.add_argument("files", nargs="+")
    e.add_argument("--json", action="store_true")

    c = sub.add_parser("capcut", help="cắt nhạc CapCut từ bài có sẵn (hoặc --gen để tạo mới)")
    c.add_argument("files", nargs="*")
    c.add_argument("-d", "--duration", type=float, default=15)
    c.add_argument("--mode", choices=["hook", "peak", "peak_at"], default="hook")
    c.add_argument("--peak-at", type=float, help="drop rơi đúng giây này (bật chế độ peak_at)")
    c.add_argument("--candidate", type=int, default=0, help="chọn ứng viên hook thứ mấy (0, 1, 2)")
    c.add_argument("--loop", action="store_true", help="vòng lặp liền mạch")
    c.add_argument("--snap-end", action="store_true", help="kết thúc ở đầu ô nhịp gần nhất thay vì đúng số giây")
    c.add_argument("--gen", action="store_true", help="tạo nhạc CapCut mới bằng Micow Beat thay vì cắt")
    c.add_argument("-s", "--style", default="")
    c.add_argument("-l", "--lyrics", help="lời hook (tuỳ chọn)")
    c.add_argument("-e", "--engine", default="micow-dsp")
    c.add_argument("--seed", type=int)
    c.add_argument("-o", "--out", help="thư mục kết quả")

    bn = sub.add_parser("bench", help="đo đạc Micow (Ear + CapCut) và ghi docs/BENCHMARK.md")
    bn.add_argument("--data", help="thư mục dữ liệu có nhãn (mặc định ~/.micow/ear_data)")

    p = sub.add_parser("plan", help="xem bản thiết kế bài")
    p.add_argument("--mode", default="song", choices=["song", "beat"])
    p.add_argument("--style", "-s", default="")
    p.add_argument("--lyrics", "-l")
    p.add_argument("--duration", "-d", type=float)
    p.add_argument("--seed", type=int, default=0)

    sub.add_parser("engines", help="trạng thái các engine")
    sub.add_parser("info", help="thông tin máy")

    i = sub.add_parser("install", help="cài engine")
    i.add_argument("engine")
    i.add_argument("--with-base", action="store_true", help="ACE-Step: tải thêm model base (cho 'làm đầy')")

    d = sub.add_parser("data", help="dữ liệu huấn luyện")
    dsub = d.add_subparsers(dest="dcmd")
    dl = dsub.add_parser("label", help="dùng Micow Ear gán nhãn đoạn cho manifest nhạc thật")
    dl.add_argument("manifest")
    ds = dsub.add_parser("synth")
    ds.add_argument("--out", required=True)
    ds.add_argument("--n", type=int, default=50)
    ds.add_argument("--seed", type=int, default=0)
    ds.add_argument("--duration", type=float, default=40.0)

    t = sub.add_parser("train", help="huấn luyện Micow-LM")
    tsub = t.add_subparsers(dest="tcmd")
    tc = tsub.add_parser("codec")
    tc.add_argument("--data", required=True)
    tc.add_argument("--out", required=True)
    tc.add_argument("--preset", default="default", choices=["default", "tiny"])
    tc.add_argument("--steps", type=int, default=100_000)
    tc.add_argument("--batch", type=int, default=8)
    tc.add_argument("--no-adv", action="store_true")
    tc.add_argument("--device", default="auto")
    tc.add_argument("--resume", action="store_true")
    tt = tsub.add_parser("tokenize")
    tt.add_argument("--data", required=True)
    tt.add_argument("--codec", required=True)
    tt.add_argument("--out", required=True)
    tt.add_argument("--device", default="auto")
    te = tsub.add_parser("ear", help="huấn luyện mạng nghe phách + hook/peak trên dữ liệu tổng hợp có nhãn")
    te.add_argument("--data", help="thư mục dữ liệu (mặc định ~/.micow/ear_data)")
    te.add_argument("--n", type=int, default=260)
    te.add_argument("--beat-steps", type=int, default=3000)
    te.add_argument("--bar-steps", type=int, default=4000)
    tl = tsub.add_parser("lm")
    tl.add_argument("--tokens", required=True)
    tl.add_argument("--out", required=True)
    tl.add_argument("--preset", default="small", choices=["tiny", "small", "base", "large"])
    tl.add_argument("--steps", type=int, default=200_000)
    tl.add_argument("--batch", type=int, default=8)
    tl.add_argument("--window", type=float, help="giây mỗi cửa sổ huấn luyện")
    tl.add_argument("--lr", type=float, default=3e-4)
    tl.add_argument("--device", default="auto")
    tl.add_argument("--resume", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd in (None,):
        ap.print_help()
        return 0
    if args.cmd == "serve":
        from .server import serve
        serve("0.0.0.0" if args.lan else args.host, args.port, args.open)
    elif args.cmd in ("beat", "song"):
        _gen(args, args.cmd)
    elif args.cmd == "analyze":
        from .analysis import analyze
        from .audio_io import SR, read_audio
        for f in args.files:
            r = analyze(read_audio(f, SR), SR)
            r.pop("onsets", None)
            print(Path(f).name, json.dumps(r, ensure_ascii=False, indent=1))
    elif args.cmd == "ear":
        from .audio_io import SR, read_audio
        from .ear import listen
        rows = []
        for fpath in args.files:
            r = listen(read_audio(fpath, SR), SR)
            rows.append((fpath, r))
            if args.json:
                print(json.dumps({"file": fpath, **{k: v for k, v in r.items() if k not in ("beats", "bars", "hook_curve", "peak_curve")}}, ensure_ascii=False))
                continue
            h, p = r.get("hook"), r.get("peak")
            print(f"\n♪ {Path(fpath).name}: {r['bpm']} BPM · {r['key']['name_vi']} · {r['duration']:.0f} giây ({r['seconds']}s, {r['model']}/{r['beat_method']})")
            for s_ in r["sections"]:
                mark = " ← HOOK" if h and s_["start_bar"] <= h["start_bar"] < s_["end_bar"] else ""
                print(f"   {s_['start']:7.2f}s  {s_['kind']:<12} [{s_['label']}] {s_['end_bar'] - s_['start_bar']:>3} ô nhịp  năng lượng {s_['energy']:.2f}{mark}")
            if h:
                print(f"   HOOK  {h['start']:.2f}s → {h['end']:.2f}s ({h['bars']} ô nhịp, tin cậy {h.get('confidence', 0):.2f})")
            if p:
                print(f"   PEAK  {p['start']:.2f}s → {p['end']:.2f}s")
        if len(rows) > 1 and not args.json:
            print("\nXếp hạng độ mạnh của hook:")
            for fpath, r in sorted(rows, key=lambda t: -(t[1].get("hook") or {}).get("score", 0)):
                print(f"   {(r.get('hook') or {}).get('score', 0):.2f}  {Path(fpath).name}")
    elif args.cmd == "capcut":
        _capcut(args)
    elif args.cmd == "bench":
        from .bench import run_bench
        run_bench(args.data)
    elif args.cmd == "plan":
        from .planner import make_blueprint
        bp = make_blueprint(args.mode, args.style, _load_text(args.lyrics), duration=args.duration, seed=args.seed)
        print(json.dumps(bp.to_dict(), ensure_ascii=False, indent=1))
    elif args.cmd == "engines":
        from .service import engines_info
        for e in engines_info():
            mark = "✓" if e.get("ready") else "·"
            print(f" {mark} {e['id']:<10} {e['name']:<14} {e.get('message', '')}")
    elif args.cmd == "info":
        from .system import info
        print(json.dumps(info(), ensure_ascii=False, indent=1))
    elif args.cmd == "install":
        from .engines import get
        job = CliJob("install", {"with_base": args.with_base})
        print(json.dumps(get(args.engine).install(job), ensure_ascii=False))
    elif args.cmd == "data" and args.dcmd == "label":
        from .model.data import auto_label
        print("Đã gán nhãn:", auto_label(args.manifest))
    elif args.cmd == "data" and args.dcmd == "synth":
        from .model.data import synth_dataset
        print("Manifest:", synth_dataset(args.out, args.n, args.seed, args.duration))
    elif args.cmd == "train":
        from .model import train as T
        if args.tcmd == "codec":
            T.train_codec(args.data, args.out, args.preset, args.steps, args.batch, adv=not args.no_adv,
                          device=args.device, resume=args.resume)
        elif args.tcmd == "tokenize":
            T.tokenize(args.data, args.codec, args.out, args.device)
        elif args.tcmd == "ear":
            from .ear.train import run_all
            print(json.dumps(run_all(args.data, args.n, args.beat_steps, args.bar_steps), ensure_ascii=False, indent=1))
        elif args.tcmd == "lm":
            T.train_lm(args.tokens, args.out, args.preset, args.steps, args.batch, args.window, args.lr,
                       args.device, args.resume)
        else:
            t.print_help()
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
