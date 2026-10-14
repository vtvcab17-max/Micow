# python3 timing.py <giong.mp3> <loi.txt> <out.json>
# Chia lời thoại (ngăn bằng [pause]) thành đoạn và câu; ranh giới ước theo số chữ rồi bám vào khoảng lặng gần nhất.
import json, re, subprocess, sys
mp3, txt, out = sys.argv[1:4]
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3]))
log = subprocess.run(["ffmpeg", "-i", mp3, "-af", "silencedetect=n=-32dB:d=0.15", "-f", "null", "-"], capture_output=True, text=True).stderr
st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
gaps = [((a + b) / 2, b - a) for a, b in zip(st, en) if a > 0.3 and b < dur - 0.1]
# đầu và cuối giọng (bỏ khoảng lặng đầu/cuối file)
v0 = en[0] if st and st[0] < 0.05 else 0.0
v1 = st[-1] if st and en[-1] >= dur - 0.05 else dur
raw = open(txt, encoding="utf-8").read()
segs = [re.sub(r"\[[^\]]*\]", "", s).strip() for s in raw.split("[pause]")]
segs = [s for s in segs if s]
sents = [[x.strip() for x in re.split(r"(?<=[.?!])\s+", s) if x.strip()] for s in segs]
units = [(i, x) for i, ss in enumerate(sents) for x in ss]
w = [len(x) + 12 for _, x in units]          # +12: mỗi câu có khoảng ngắt riêng
tot = sum(w); acc = 0; bounds = []
for k in w[:-1]:
    acc += k; bounds.append(v0 + (v1 - v0) * acc / tot)
used = set(); snapped = []; prev = v0
for b in bounds:
    cand = [(abs(g - b) - min(ln, .6) * .5, g) for g, ln in gaps if g > prev + .4 and g not in used and abs(g - b) < 1.6]
    g = min(cand)[1] if cand else b
    used.add(g); snapped.append(g); prev = g
edges = [v0] + snapped + [v1]
res = []
for j, (i, x) in enumerate(units):
    if not res or res[-1]["i"] != i: res.append({"i": i, "start": edges[j], "sent": []})
    res[-1]["sent"].append({"start": round(edges[j], 3), "end": round(edges[j + 1], 3), "text": x})
    res[-1]["end"] = edges[j + 1]
for r in res: r["start"] = round(r["start"], 3); r["end"] = round(r["end"], 3); del r["i"]
json.dump({"dur": round(dur, 3), "segs": res}, open(out, "w"), ensure_ascii=False, indent=1)
for r in res: print(f'{r["start"]:6.2f}–{r["end"]:6.2f}  ' + " | ".join(s["text"][:40] for s in r["sent"]))
