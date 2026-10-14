"""`micow bench` – đo Micow bằng số liệu thật cho việc làm nhạc CapCut, ghi docs/BENCHMARK.md + docs/benchmark.json.

Không tự chấm "điểm": mỗi chỉ số là một phép đo có thể lặp lại.
  A. Micow Ear trên bài có nhãn (tập kiểm tra, không dùng khi huấn luyện): phách, đầu ô nhịp, tempo, hook, peak, loại đoạn.
  B. Tạo nhạc CapCut (Micow Beat): độ dài, drop đúng giây (Micow Ear nghe lại để kiểm), hook vào ngay, loudness,
     đỉnh, độ liền mạch khi lặp, thời gian dựng.
  C. Cắt CapCut từ bài có sẵn: độ dài, điểm bắt đầu có trùng đầu ô nhịp thật, drop có rơi đúng giây yêu cầu.
"""
from __future__ import annotations

import glob
import json
import time
from pathlib import Path

import numpy as np

from . import __version__, paths
from .audio_io import SR


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def bench_ear(files: list[str]) -> dict:
    from .ear.train import evaluate
    out = {"rule_only": evaluate(files, use_model=False)}
    from .ear.nn import bar_model, beat_model
    if beat_model() is not None or bar_model() is not None:
        out["trained"] = evaluate(files, use_model=True)
    return out


def bench_generate(n_per: int = 1) -> dict:
    from .dsp import master as M
    from .dsp.render import render
    from .ear import listen
    from .planner import make_blueprint
    cases = []
    genres = ["trap", "vinahouse", "edm", "vpop", "house", "lofi", "ballad", "boombap"]
    for gi, g in enumerate(genres):
        for k in range(n_per):
            dur = [15, 30, 20, 15][(gi + k) % 4]
            peak = [7.0, 10.5, 8.0, 6.0][(gi + k) % 4]
            loop = (gi + k) % 2 == 0
            t0 = time.time()
            bp = make_blueprint("capcut", g, "", seed=100 + gi * 10 + k, duration=dur, peak_at=peak, loop=loop)
            r = render(bp)
            dt = time.time() - t0
            ear = listen(r.mix, SR)
            seam = float(np.abs(r.mix[-1] - r.mix[0]).max())
            w = int(0.05 * SR)  # bước nhảy ở mối nối so với bước nhảy bình thường quanh đó (p99) – >1 mới là "click"
            local = np.abs(np.diff(np.concatenate([r.mix[-w:], r.mix[:w]]), axis=0)).max(axis=1)
            seam_ratio = seam / (float(np.percentile(local, 99)) + 1e-9)
            jump = float(np.abs(np.diff(r.mix, axis=0)).max())
            lead_ev = [e.t for e in getattr(r, "events", []) if e.track == "lead"]
            first_hook_note = min(lead_ev) if lead_ev else (r.melody[0].beat * 60 / bp.bpm if r.melody else None)
            pre = r.mix[: int(peak * SR)]
            post = r.mix[int(peak * SR): int((peak + 4) * SR)]
            contrast = 20 * np.log10((np.sqrt(np.mean(post ** 2)) + 1e-9) / (np.sqrt(np.mean(pre ** 2)) + 1e-9))
            drop_true = next(s.start_bar * bp.bar_seconds for s in bp.sections if s.kind == "drop")
            cases.append({"genre": g, "duration": dur, "peak_at": peak, "loop": loop,
                          "len_err": abs(len(r.mix) / SR - dur), "drop_err_plan": abs(drop_true - peak),
                          "drop_err_heard": abs(ear["peak"]["start"] - peak) if ear.get("peak") else None,
                          "hook_start_heard": ear["hook"]["start"] if ear.get("hook") else None,
                          "lufs": M.lufs(r.mix), "peak_db": 20 * np.log10(np.abs(r.mix).max() + 1e-12),
                          "loop_seam": seam if loop else None, "loop_seam_ratio": seam_ratio if loop else None,
                          "max_step": jump, "first_hook_note_s": first_hook_note, "drop_contrast_db": contrast,
                          "render_s": dt})
    heard = [c["drop_err_heard"] for c in cases if c["drop_err_heard"] is not None]
    seams = [c["loop_seam"] for c in cases if c["loop_seam"] is not None]
    return {"cases": cases, "n": len(cases),
            "len_err_max_s": round(max(c["len_err"] for c in cases), 4),
            "drop_err_plan_max_s": round(max(c["drop_err_plan"] for c in cases), 4),
            "drop_heard_within_0.25s": round(float(np.mean([e <= 0.25 for e in heard])), 3) if heard else None,
            "drop_heard_median_err_s": round(float(np.median(heard)), 3) if heard else None,
            "first_hook_note_max_s": round(float(max(99 if c["first_hook_note_s"] is None else c["first_hook_note_s"]
                                                     for c in cases)), 3),
            "drop_contrast_db_min": round(float(min(c["drop_contrast_db"] for c in cases)), 2),
            "drop_contrast_db_mean": round(float(np.mean([c["drop_contrast_db"] for c in cases])), 2),
            "lufs_mean": round(float(np.mean([c["lufs"] for c in cases])), 2),
            "lufs_max_dev": round(float(max(abs(c["lufs"] + 14) for c in cases)), 2),
            "peak_db_max": round(float(max(c["peak_db"] for c in cases)), 2),
            "loop_seam_max": round(float(max(seams)), 4) if seams else None,
            "loop_seam_ratio_max": round(float(max(c["loop_seam_ratio"] for c in cases if c["loop_seam_ratio"] is not None)), 2) if seams else None,
            "render_s_mean": round(float(np.mean([c["render_s"] for c in cases])), 2)}


def bench_cut(files: list[str]) -> dict:
    from .ear import listen
    from .ear.capcut import plan_cut, render_cut
    from .ear.dataset import load
    rows = []
    for p in files:
        y, lab = load(p)
        x = np.stack([y, y], 1)
        from .audio_io import resample
        x = resample(x, 22050, SR)
        t0 = time.time()
        ear = listen(x, SR)
        t_ear = time.time() - t0
        total = len(x) / SR
        down = np.array(lab["downbeats"])
        peak_true = [s["start"] for s in lab["sections"] if s["peak"]]
        hook_secs = [(s["start"], s["end"]) for s in lab["sections"] if s["hook"]]
        for mode, pk in (("hook", None), ("peak_at", 7.0)):
            plan = plan_cut(ear, total, 15.0, mode, pk)
            out = render_cut(x, plan)
            on_bar = float(np.min(np.abs(down - plan["start"]))) if mode == "hook" else None
            in_hook = any(a - 0.3 <= plan["start"] < b for a, b in hook_secs) if mode == "hook" else None
            drop_err = (min(abs(t - (plan["start"] + 7.0)) for t in peak_true) if mode == "peak_at" and peak_true else None)
            rows.append({"file": Path(p).stem, "mode": mode, "len_err": abs(len(out) / SR - 15.0), "start_bar_err": on_bar,
                         "start_in_hook": in_hook, "drop_err": drop_err, "ear_s": t_ear, "song_s": total})
    hook = [r for r in rows if r["mode"] == "hook"]
    pa = [r for r in rows if r["mode"] == "peak_at" and r["drop_err"] is not None]
    return {"n": len(files),
            "len_err_max_s": round(max(r["len_err"] for r in rows), 4),
            "start_on_true_downbeat_70ms": round(float(np.mean([r["start_bar_err"] <= 0.07 for r in hook])), 3),
            "start_inside_true_hook": round(float(np.mean([r["start_in_hook"] for r in hook])), 3),
            "drop_within_0.5s_of_7s": round(float(np.mean([r["drop_err"] <= 0.5 for r in pa])), 3) if pa else None,
            "ear_seconds_per_minute": round(float(np.mean([r["ear_s"] / (r["song_s"] / 60) for r in hook])), 2)}


def run_bench(data_dir: str | None = None, n_eval: int = 39, out_dir: str | Path | None = None) -> dict:
    data = Path(data_dir) if data_dir else paths.home() / "ear_data"
    files = sorted(glob.glob(str(data / "*.npz")))
    report = {"version": __version__, "date": time.strftime("%Y-%m-%d %H:%M"), "machine": "CPU"}
    if files:
        from .ear.train import _split
        _, val = _split(files)
        val = val[:n_eval]
        print(f"A. Micow Ear trên {len(val)} bài kiểm tra…", flush=True)
        report["ear"] = bench_ear(val)
        print(f"C. Cắt CapCut trên {len(val)} bài…", flush=True)
        report["cut"] = bench_cut(val)
    else:
        print("(Chưa có dữ liệu có nhãn – chạy `micow train ear` để sinh; bỏ qua phần A, C)")
    print("B. Tạo nhạc CapCut…", flush=True)
    report["generate"] = bench_generate()
    out = Path(out_dir) if out_dir else paths.ROOT / "docs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    (out / "BENCHMARK.md").write_text(render_md(report), encoding="utf-8")
    print(f"Đã ghi {out / 'BENCHMARK.md'}")
    return report


def render_md(r: dict) -> str:
    L = [f"# Micow – số đo cho nhạc CapCut (bản {r['version']}, {r['date']})", "",
         "Mọi con số dưới đây do `micow bench` đo lại được trên máy (CPU). Không có điểm tự chấm.", ""]
    if "ear" in r:
        e = r["ear"]
        L += ["## A. Micow Ear – nghe và tìm hook / peak", "",
              f"Tập kiểm tra: {e['rule_only']['n']} bài tổng hợp có nhãn chính xác, **không dùng khi huấn luyện**, đã trộn lại stem, EQ, nhiễu.", "",
              "| Chỉ số | Chỉ thuật toán | Sau huấn luyện |", "|---|---|---|"]
        names = [("beat", "Phách đúng (±70 ms)"), ("downbeat", "Đầu ô nhịp đúng (±70 ms)"), ("tempo", "Tempo đúng (±4%, cho phép ×2/÷2)"),
                 ("hook", "Đoạn hook chọn ra nằm trong điệp khúc/drop thật (≥50%)"), ("peak", "Đoạn peak nằm trong đoạn cao trào thật (≥50%)"),
                 ("kind", "Nhãn loại đoạn đúng")]
        for k, n in names:
            a = e["rule_only"].get(k)
            b = e.get("trained", {}).get(k)
            L.append(f"| {n} | {_pct(a) if a is not None else '–'} | {_pct(b) if b is not None else '–'} |")
        L.append("")
    g = r["generate"]
    L += ["## B. Tạo nhạc CapCut mới (Micow Beat)", "",
          f"{g['n']} bài (8 thể loại, 15–30 giây, drop yêu cầu ở giây 6–10,5).", "",
          "| Chỉ số | Kết quả |", "|---|---|",
          f"| Sai số độ dài | tối đa {g['len_err_max_s']} giây |",
          f"| Drop theo bản thiết kế lệch giây yêu cầu | tối đa {g['drop_err_plan_max_s']} giây |",
          f"| Micow Ear nghe lại: drop nằm trong ±0,25 giây | {_pct(g['drop_heard_within_0.25s'])} (trung vị lệch {g['drop_heard_median_err_s']} giây) |",
          f"| Nốt hook đầu tiên vang lúc | chậm nhất {g['first_hook_note_max_s']} giây |",
          f"| Độ bùng của drop (4 giây sau drop so với trước drop) | trung bình +{g['drop_contrast_db_mean']} dB, thấp nhất +{g['drop_contrast_db_min']} dB |",
          f"| Loudness | trung bình {g['lufs_mean']} LUFS, lệch tối đa {g['lufs_max_dev']} LU so với −14 |",
          f"| Đỉnh mẫu cao nhất | {g['peak_db_max']} dBFS |",
          f"| Mối nối vòng lặp: bước nhảy so với p99 bước nhảy quanh đó | tối đa {g['loop_seam_ratio_max']}× (≤ 1 là không có tiếng click) |",
          f"| Thời gian dựng trung bình (CPU) | {g['render_s_mean']} giây/bài |", ""]
    if "cut" in r:
        c = r["cut"]
        L += ["## C. Cắt CapCut từ bài có sẵn", "", f"{c['n']} bài, mỗi bài cắt 15 giây kiểu hook và kiểu drop@7s.", "",
              "| Chỉ số | Kết quả |", "|---|---|",
              f"| Sai số độ dài | tối đa {c['len_err_max_s']} giây |",
              f"| Điểm bắt đầu trùng đầu ô nhịp thật (±70 ms) | {_pct(c['start_on_true_downbeat_70ms'])} |",
              f"| Điểm bắt đầu nằm trong điệp khúc/drop thật | {_pct(c['start_inside_true_hook'])} |",
              f"| Drop thật rơi trong ±0,5 giây quanh giây 7 | {_pct(c['drop_within_0.5s_of_7s']) if c['drop_within_0.5s_of_7s'] is not None else '–'} |",
              f"| Tốc độ nghe | {c['ear_seconds_per_minute']} giây cho mỗi phút nhạc |", ""]
    L += ["## Giới hạn của phép đo", "",
          "* Bài kiểm tra là nhạc tổng hợp có nhãn tuyệt đối (do chính Micow dựng rồi trộn lại); chưa đo trên bộ nhạc thật có nhãn.",
          "  Nút **Đúng hook** trên trang Nhạc CapCut ghi nhãn bài thật của bạn, `micow train ear` sẽ học thêm từ đó.",
          "* Phần B, C đo độ chính xác thời gian/âm lượng – không đo \"hay\" hay không; cái đó cần người nghe.", ""]
    return "\n".join(L)
