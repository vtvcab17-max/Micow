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
                                "gender": args.gender, "guide_vocal": not args.no_vocal, "clips": clips})
    eng = get(req.engine)
    job = CliJob("generate", req.to_dict())
    loaded = []
    for c in req.clips:
        cl = load_clip(c["id"])
        cl["use"] = c["use"]
        loaded.append(cl)
    print(f"♪ {eng.name}: {mode} · seed {req.seed}")
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
        g.add_argument("--clip", "-c", action="append", help="tệp[:style|loop|chop|kit|cover|complete]")
        g.add_argument("--out", "-o", help="chép kết quả ra thư mục này")

    a = sub.add_parser("analyze", help="phân tích đoạn nhạc")
    a.add_argument("files", nargs="+")

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
