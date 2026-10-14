"use strict";
/* Trang Nhạc CapCut: Micow Ear nghe nhiều bài, tìm hook / peak, cắt đúng số giây; tạo nhạc ngắn hook-first. */
const KIND_COLOR = { intro: "#2e2f37", outro: "#2e2f37", verse: "#3a3470", prechorus: "#4a3f93", chorus: "#7b6cf6",
  postchorus: "#7b6cf6", drop: "#8e81f8", bridge: "#25403b", break: "#30333d", instrumental: "#30333d" };
const KIND_VI = { intro: "Mở đầu", verse: "Phiên khúc", prechorus: "Tiền ĐK", chorus: "Điệp khúc", postchorus: "Hậu ĐK",
  bridge: "Cầu nối", drop: "Drop", break: "Nghỉ", instrumental: "Gian tấu", outro: "Kết" };

const CC = {
  songs: [], sel: null, dur: 15, mode: "hook", peakAt: 7, genPeak: 7, loop: false, snap: false,
  genre: null, useSongs: false, useHook: false, audio: new Audio(), playing: null,

  init() {
    const drop = $("#ccDrop");
    drop.innerHTML = `${ico("upload")}<br><b>Thả nhiều bài vào đây</b> hoặc bấm để chọn<br><small>mp3, wav, m4a… – Micow Ear tìm cấu trúc, hook và đoạn peak của từng bài</small>`;
    const pick = () => { const fi = $("#fileIn"); fi.onchange = () => { this.add([...fi.files]); fi.value = ""; }; fi.click(); };
    drop.onclick = pick;
    drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } };
    for (const t of [drop, $("#page-capcut")]) {
      t.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
      t.addEventListener("dragleave", () => drop.classList.remove("over"));
      t.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); this.add([...e.dataTransfer.files].filter((f) => /audio|\.(mp3|wav|m4a|flac|ogg|aac)$/i.test(f.type + f.name))); });
    }
    const dur = $("#ccDur");
    for (const d of [10, 15, 30, 60]) dur.append(el("button", { class: "chip", "aria-pressed": String(d === this.dur), dataset: { d }, onclick: () => this.setDur(d) }, `${d} giây`));
    dur.append(el("input", { type: "number", min: 3, max: 120, step: 0.5, placeholder: "khác", style: "width:84px;padding:7px 10px", oninput: (e) => { if (+e.target.value) this.setDur(+e.target.value, true); } }));
    $$("#ccMode button").forEach((b) => (b.onclick = () => { this.mode = b.dataset.m; $$("#ccMode button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); $("#ccPeakField").hidden = this.mode !== "peak_at"; this.sync(); }));
    $("#ccPeak").oninput = (e) => { this.peakAt = +e.target.value; $("#ccPeakV").textContent = this.peakAt; };
    $("#ccGenPeak").oninput = (e) => { this.genPeak = +e.target.value; $("#ccGenPeakV").textContent = this.genPeak; };
    const tog = (id, key) => { const b = $(id); b.onclick = () => { this[key] = !this[key]; b.setAttribute("aria-pressed", String(this[key])); }; };
    tog("#ccLoop", "loop"); tog("#ccSnap", "snap"); tog("#ccUseSongs", "useSongs"); tog("#ccUseHook", "useHook");
    $("#ccGo").innerHTML = ico("scissors") + "Cắt nhạc CapCut";
    $("#ccGo").onclick = () => this.cut();
    $("#ccGen").innerHTML = ico("spark") + "Tạo nhạc CapCut";
    $("#ccGen").onclick = () => this.generate();
    this.audio.addEventListener("timeupdate", () => this.onTime());
    this.audio.addEventListener("pause", () => this.paintAll());
    addEventListener("resize", () => this.paintAll());
    this.renderGenres();
    this.restore();
  },

  renderGenres() {
    const host = $("#ccGenres");
    host.innerHTML = "";
    for (const g of [{ id: null, name: "Tự động" }, ...App.genres]) {
      host.append(el("button", { class: "chip", "aria-pressed": String(this.genre === g.id), onclick: () => { this.genre = g.id; this.renderGenres(); } }, g.name));
    }
  },

  setDur(d, custom) {
    this.dur = d;
    $$("#ccDur .chip").forEach((c) => c.setAttribute("aria-pressed", String(!custom && +c.dataset.d === d)));
    $("#ccPeak").max = Math.max(2, d - 1);
    $("#ccGenPeak").max = Math.max(2, d - 1);
    if (this.peakAt > d - 1) { this.peakAt = Math.max(1, Math.round(d / 2)); $("#ccPeak").value = this.peakAt; $("#ccPeakV").textContent = this.peakAt; }
    if (this.genPeak > d - 1) { this.genPeak = Math.max(2, Math.round(d / 2)); $("#ccGenPeak").value = this.genPeak; $("#ccGenPeakV").textContent = this.genPeak; }
    this.sync();
  },

  sync() {
    $("#ccGo").disabled = !(this.sel && this.sel.ear);
    $("#ccSel").textContent = this.sel ? this.sel.name : "chọn một bài bên trái";
    $("#ccCount").textContent = this.songs.length ? `${this.songs.length} bài` : "";
  },

  async restore() {
    if (!App.online || this.restoring) return;
    this.restoring = true;
    for (const id of store("cc-songs") || []) {
      if (this.songs.some((s) => s.id === id)) continue;
      try {
        const m = await API.get(`/api/uploads/${id}`);
        this.songs.push({ id, name: m.name, duration: m.duration, analysis: m.analysis, ear: m.ear || null, cand: 0 });
      } catch { /* bài đã xoá */ }
    }
    if (this.songs.length && !this.sel) this.sel = this.songs[0];
    const missing = this.songs.filter((s) => !s.ear).map((s) => s.id);
    if (missing.length) this.listen(missing);
    this.restoring = false;
    this.render();
  },

  async add(files) {
    if (!App.online) return App.showOffline(true);
    const ids = [];
    for (const f of files) {
      const s = { name: f.name, busy: "Đang chuẩn bị", cand: 0 };
      this.songs.unshift(s);
      this.render();
      try {
        const m = await API.upload(f, (st) => { s.busy = st; this.render(); });
        Object.assign(s, { id: m.id, duration: m.duration, analysis: m.analysis, busy: "Đang chờ nghe…" });
        ids.push(m.id);
      } catch (e) {
        this.songs.splice(this.songs.indexOf(s), 1);
        toast(`Không đọc được ${f.name}: ${e.message}`, 5000);
      }
      this.render();
    }
    store("cc-songs", this.songs.filter((s) => s.id).map((s) => s.id).slice(0, 40));
    if (ids.length) this.listen(ids);
  },

  async listen(ids) {
    let job;
    try { job = await API.post("/api/ear/listen", { ids }); } catch (e) { return toast(e.message); }
    const poll = async () => {
      const j = await API.get(`/api/jobs/${job.id}`).catch(() => null);
      if (!j) return setTimeout(poll, 1500);
      for (const s of this.songs) if (ids.includes(s.id) && !s.ear) s.busy = j.message || "Đang nghe…";
      if (j.status === "done") {
        for (const [id, r] of Object.entries(j.result.results)) {
          const s = this.songs.find((x) => x.id === id);
          if (!s) continue;
          s.busy = r.error ? "Lỗi: " + r.error : null;
          if (!r.error) s.ear = r;
        }
        if (!this.sel) this.sel = this.songs.find((s) => s.ear) || null;
        this.render();
        this.rank();
      } else if (j.status === "error") {
        toast("Lỗi khi nghe: " + j.error, 5000);
        for (const s of this.songs) if (ids.includes(s.id)) s.busy = "Lỗi";
        this.render();
      } else { this.render(); setTimeout(poll, 900); }
    };
    poll();
  },

  rank() {
    const done = this.songs.filter((s) => s.ear && s.ear.hook);
    if (done.length > 1) {
      const best = done.reduce((a, b) => ((a.ear.hook.score || 0) >= (b.ear.hook.score || 0) ? a : b));
      toast(`Hook mạnh nhất: ${best.name}`);
    }
  },

  render() {
    const host = $("#ccSongs");
    host.innerHTML = "";
    if (!this.songs.length) host.append(el("p", { class: "note" }, "Chưa có bài nào. Thả các bài bạn muốn làm nhạc nền video ngắn."));
    for (const s of this.songs) host.append(this.card(s));
    this.sync();
    requestAnimationFrame(() => this.paintAll());
  },

  card(s) {
    const c = el("div", { class: "song", "aria-selected": String(this.sel === s), dataset: { id: s.id || "" }, onclick: () => { this.sel = s; this.render(); } });
    const a = s.analysis || {}, e = s.ear;
    c.append(el("div", { class: "st" }, el("b", { title: s.name }, s.name),
      el("span", { class: "row", style: "gap:5px" }, e ? el("span", { class: "badge n" }, `${Math.round(e.bpm)} BPM`) : a.bpm ? el("span", { class: "badge n" }, `${Math.round(a.bpm)} BPM`) : null,
        (e || a).key ? el("span", { class: "badge n" }, (e || a).key.name_vi) : null, s.duration ? el("span", { class: "badge n" }, fmtTime(s.duration)) : null)));
    if (s.busy || !e) { c.append(el("div", { class: "busy" }, el("span", { class: "spin" }), s.busy || "Đang nghe…")); return c; }
    c.append(el("canvas", { "aria-label": "Cấu trúc bài: đoạn, hook, peak" }));
    const h = this.hook(s), p = e.peak;
    c.append(el("div", { class: "legend" },
      h ? el("span", {}, el("i", { style: "background:#fff" }), `Hook ${fmtTime(h.start)}–${fmtTime(h.end)}` + (e.candidates && e.candidates.length > 1 ? ` (${s.cand + 1}/${e.candidates.length})` : "")) : null,
      p ? el("span", {}, el("i", { style: "background:var(--acc-hi)" }), `Peak ${fmtTime(p.start)}`) : null,
      el("span", {}, `${e.sections.length} đoạn · ${e.model === "mlp+rule" ? "mô hình đã huấn luyện" : "thuật toán"}`)));
    const stop = (fn) => (ev) => { ev.stopPropagation(); fn(); };
    c.append(el("div", { class: "acts" },
      h ? el("button", { class: "tonal", html: ico("play") + "Nghe hook", onclick: stop(() => this.preview(s, h.start, h.end)) }) : null,
      p ? el("button", { html: ico("play") + "Nghe peak", onclick: stop(() => this.preview(s, p.start, p.end)) }) : null,
      e.candidates && e.candidates.length > 1 ? el("button", { html: ico("redo") + "Hook khác", onclick: stop(() => { s.cand = (s.cand + 1) % e.candidates.length; this.sel = s; this.render(); }) }) : null,
      h ? el("button", { html: ico("check") + "Đúng hook", title: "Ghi nhãn để lần huấn luyện sau Micow nghe chuẩn hơn", onclick: stop(() => this.label(s)) }) : null,
      el("button", { class: "ghost", html: ico("x"), "aria-label": "Bỏ bài", onclick: stop(() => { this.songs.splice(this.songs.indexOf(s), 1); if (this.sel === s) this.sel = this.songs[0] || null; store("cc-songs", this.songs.filter((x) => x.id).map((x) => x.id)); this.render(); }) })));
    return c;
  },

  hook(s) { const e = s.ear; return e && (e.candidates && e.candidates[s.cand]) || (e && e.hook); },

  paint(s) {
    const cv = $(`.song[data-id="${s.id}"] canvas`);
    if (!cv || !s.ear) return;
    const dpr = devicePixelRatio || 1, w = cv.clientWidth, H = cv.clientHeight;
    if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, H);
    const e = s.ear, D = e.duration || s.duration || 1, bars = e.bars, en = e.energy || [];
    const X = (t) => (t / D) * w;
    const kindAt = (t) => (e.sections.find((x) => x.start <= t && t < x.end) || {}).kind;
    for (let i = 0; i < bars.length - 1; i++) {
      const x0 = X(bars[i]), x1 = X(bars[i + 1]);
      const v = en[i] != null ? en[i] : 0.5, bh = 8 + v * (H - 16);
      g.fillStyle = KIND_COLOR[kindAt((bars[i] + bars[i + 1]) / 2)] || "#3a3470";
      g.fillRect(x0 + 0.5, H - bh, Math.max(1, x1 - x0 - 1), bh);
    }
    const h = this.hook(s);
    if (h) { g.strokeStyle = "#fff"; g.lineWidth = 2; g.strokeRect(X(h.start) + 1, 1, Math.max(2, X(h.end) - X(h.start) - 2), H - 2); g.fillStyle = "#fff"; g.font = "700 10px Plus Jakarta Sans, sans-serif"; g.fillText("HOOK", X(h.start) + 5, 12); }
    if (e.peak) { const px = X(e.peak.start); g.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--acc-hi"); g.beginPath(); g.moveTo(px - 6, 0); g.lineTo(px + 6, 0); g.lineTo(px, 9); g.fill(); g.fillText("PEAK", Math.min(w - 30, px + 8), 22); }
    if (this.playing && this.playing.s === s) { g.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--gold"); g.fillRect(X(this.audio.currentTime) - 1, 0, 2, H); }
  },
  paintAll() { for (const s of this.songs) this.paint(s); },

  preview(s, a, b) {
    const src = API.url(`/api/uploads/${s.id}/audio`);
    if (this.audio.src !== src) this.audio.src = src;
    this.playing = { s, end: b };
    const go = () => { this.audio.currentTime = a; this.audio.play().catch(() => {}); };
    if (this.audio.readyState >= 1) go(); else this.audio.addEventListener("loadedmetadata", go, { once: true });
    if (Player.a && !Player.a.paused) Player.a.pause();
  },
  onTime() {
    if (this.playing && this.audio.currentTime >= this.playing.end) { this.audio.pause(); this.playing = null; }
    if (this.playing) this.paint(this.playing.s);
  },

  async label(s) {
    const h = this.hook(s), p = s.ear.peak;
    try {
      await API.post("/api/ear/label", { id: s.id, hook_start: h.start, hook_end: h.end, peak_start: p ? p.start : null, peak_end: p ? p.end : null });
      toast("Đã ghi nhãn. Lần chạy “micow train ear” sau, Micow sẽ học từ bài này.");
    } catch (e) { toast(e.message); }
  },

  async cut() {
    const s = this.sel;
    if (!s || !s.ear) return toast("Chọn một bài đã nghe xong");
    const body = { id: s.id, duration: this.dur, mode: this.mode, peak_at: this.mode === "peak_at" ? this.peakAt : null, loop: this.loop, candidate: s.cand, snap_end: this.snap };
    try { App.trackJobHost($("#ccJobs"), await API.post("/api/capcut", body)); } catch (e) { toast(e.message, 5000); }
  },

  async generate() {
    if (!App.online) return App.showOffline(true);
    const clips = [];
    if (this.useSongs) for (const s of this.songs.filter((x) => x.id && !x.busy)) clips.push({ id: s.id, use: "style" });
    if (this.useHook && this.sel && this.sel.ear) clips.push({ id: this.sel.id, use: "hook" });
    const body = { mode: "capcut", engine: "micow-dsp", style: $("#ccStyle").value, genre: this.genre, duration: this.dur,
      peak_at: this.genPeak < this.dur ? this.genPeak : null, loop: this.loop, clips };
    try { App.trackJobHost($("#ccJobs"), await API.post("/api/generate", body)); } catch (e) { toast(e.message, 5000); }
  },
};

document.addEventListener("DOMContentLoaded", () => setTimeout(() => CC.init(), 0));
