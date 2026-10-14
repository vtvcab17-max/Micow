"""Huấn luyện Micow-LM trọn gói trên máy có GPU: `micow train all --music <thư mục nhạc>`.

Các bước (bước nào xong rồi thì bỏ qua, chạy lại lệnh là tiếp tục):
  1. quét thư mục nhạc → manifest.jsonl (lời/phong cách lấy từ tệp .txt/.lrc cùng tên nếu có)
  2. Micow Ear gán bpm, giọng, đoạn (intro/verse/chorus/drop…) + năng lượng
  3. huấn luyện codec → 4. token hoá → 5. huấn luyện Micow-LM (cỡ chọn theo VRAM)

Chỉ dùng nhạc bạn có quyền sử dụng.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import paths

AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}

# cỡ Micow-LM theo VRAM (GB): (ngưỡng, preset, batch)
PRESET_BY_VRAM = [(24.0, "base", 8), (8.0, "small", 8), (5.5, "small", 4)]


def choose_preset(gpu: dict) -> tuple[str, int, str]:
    """→ (preset, batch, ghi chú). Không có GPU đủ mạnh thì chỉ chạy `tiny` để thử quy trình."""
    if gpu.get("backend") in ("cuda", "mps"):
        for need, preset, batch in PRESET_BY_VRAM:
            if gpu.get("vram_gb", 0) >= need:
                return preset, batch, f"{gpu.get('name') or gpu['backend']} {gpu['vram_gb']} GB → {preset}, batch {batch}"
        return "tiny", 4, f"GPU {gpu.get('vram_gb', 0)} GB quá ít cho small (cần ≥ 5,5 GB) → tiny (chỉ để thử quy trình)"
    return "tiny", 2, "không thấy GPU (CUDA/MPS) → tiny trên CPU, chỉ để thử quy trình"


def _style_for(audio: Path, analysis: dict) -> str:
    side = audio.with_suffix(".style.txt")
    if side.exists():
        return side.read_text(encoding="utf-8").strip()
    from ..analysis import suggest_genre
    from ..styles import GENRES, detect_genre
    # tên tệp / thư mục thường đã ghi thể loại ("vinahouse/bai1.mp3", "drill_beat.wav") – tin hơn đoán từ âm thanh
    hint = " ".join([audio.stem, *[p.name for p in audio.parents][:2]]).replace("_", " ").replace("-", " ")
    g = detect_genre(hint) or suggest_genre(analysis)
    return GENRES[g]["name"] if g else ""


def build_manifest(music: str | Path, out_dir: str | Path, log=print) -> Path:
    """Quét `music` (đệ quy) → `out_dir/manifest.jsonl`. Giữ nguyên bài đã có trong manifest cũ."""
    from ..analysis import analyze
    from ..audio_io import SR, read_audio
    from ..ear import listen
    music, out = Path(music).expanduser().resolve(), Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    mf = out / "manifest.jsonl"
    old = {}
    if mf.exists():
        for line in mf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                it = json.loads(line)
                old[it["audio"]] = it
    files = sorted(p for p in music.rglob("*") if p.suffix.lower() in AUDIO_EXT and p.is_file())
    if not files:
        raise SystemExit(f"Không thấy tệp nhạc ({', '.join(sorted(AUDIO_EXT))}) trong {music}")
    items = []
    for i, f in enumerate(files):
        key = str(f)
        if key in old and old[key].get("sections"):
            items.append(old[key])
            continue
        try:
            x = read_audio(f, SR)
        except Exception as e:  # tệp hỏng / thiếu ffmpeg cho mp3, m4a…
            log(f"bỏ qua {f.name}: {e}")
            continue
        a = analyze(x, SR)
        r = listen(x, SR)
        it = {"audio": key, "style": _style_for(f, a), "bpm": round(r["bpm"]), "key": r["key"]["name"],
              "sections": [{"kind": s["kind"], "start": s["start"], "end": s["end"], "energy": s["energy"]}
                           for s in r["sections"]]}
        txt = f.with_suffix(".txt")
        if txt.exists():
            it["lyrics"] = txt.read_text(encoding="utf-8").strip()
        if f.with_suffix(".lrc").exists():
            it["lrc"] = str(f.with_suffix(".lrc"))
        items.append(it)
        log(f"[{i + 1}/{len(files)}] {f.name}: {it['style'] or '?'} · {it['bpm']} BPM · {it['key']} · {len(it['sections'])} đoạn")
    mf.write_text("\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n", encoding="utf-8")
    return mf


def run_all(music: str, name: str = "cua-toi", work: str | None = None, preset: str | None = None,
            codec_steps: int | None = None, lm_steps: int | None = None, device: str = "auto",
            dry_run: bool = False, log=print) -> dict:
    from ..system import gpu_info
    gpu = gpu_info()
    auto_preset, batch, note = choose_preset(gpu)
    preset = preset or auto_preset
    tiny = preset == "tiny"
    codec_steps = codec_steps or (300 if tiny else 100_000)
    lm_steps = lm_steps or (300 if tiny else {"small": 200_000, "base": 400_000, "large": 600_000}[preset])
    work_dir = Path(work).expanduser() if work else paths.home() / "train" / name
    model_dir = paths.home() / "models" / "micow-lm" / name
    plan = {"gpu": gpu, "note": note, "preset": preset, "batch": batch, "codec_steps": codec_steps,
            "lm_steps": lm_steps, "work": str(work_dir), "model": str(model_dir)}
    log("Micow-LM – huấn luyện trọn gói\n" + json.dumps(plan, ensure_ascii=False, indent=1))
    if dry_run:
        return plan

    from . import train as T
    cb = None if log is print else log
    mf = build_manifest(music, work_dir, log)
    model_dir.mkdir(parents=True, exist_ok=True)
    codec = model_dir / "codec.pt"
    if codec.exists():
        log(f"codec đã có ({codec}) – bỏ qua; xoá tệp này nếu muốn huấn luyện lại")
    else:
        T.train_codec(str(mf), str(codec), "tiny" if tiny else "default", codec_steps, batch, adv=not tiny,
                      device=device, log=cb)
    tokens = work_dir / "tokens"
    if (tokens / "index.json").exists():
        log(f"token đã có ({tokens}) – bỏ qua")
    else:
        T.tokenize(str(mf), str(codec), str(tokens), device, log=cb)
    lm = model_dir / "lm.pt"
    T.train_lm(str(tokens), str(lm), preset, lm_steps, batch, device=device, resume=lm.exists(), log=cb)
    plan["done"] = True
    log(f"Xong. Mở Micow → Mô hình: Micow-LM '{name}' sẵn sàng ({model_dir}).")
    return plan
