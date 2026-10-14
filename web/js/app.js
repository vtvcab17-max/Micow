"use strict";
/* Micow – giao diện chính: Tạo bài hát, Tạo beat, Thư viện, Mô hình. HTML/CSS/JS thuần, không cần build. */
const FALLBACK_GENRES = [
  ["vpop", "V-Pop", "Pop Việt tươi sáng", [92, 112]], ["ballad", "Ballad", "Ballad chậm, piano + dây", [64, 80]],
  ["rnb", "R&B", "Hợp âm 7-9, groove lơi", [70, 95]], ["trap", "Trap", "808 dài, hi-hat cuộn", [130, 150]],
  ["drill", "Drill", "808 trượt, hi-hat 3-3-2", [138, 146]],
  ["boombap", "Boom Bap", "Hip hop cổ điển", [84, 96]], ["lofi", "Lo-fi", "Chill, đĩa than", [70, 88]],
  ["house", "House", "4/4, bass nảy", [118, 126]], ["edm", "EDM", "Supersaw, drop", [124, 150]],
  ["vinahouse", "Vinahouse", "Nhạc sàn Việt", [132, 140]], ["bolero", "Bolero", "Guitar, sáo, trữ tình", [64, 76]],
  ["cinematic", "Cinematic", "Dây, trống lớn", [80, 100]],
].map(([id, name, desc, bpm]) => ({ id, name, desc, bpm }));
const WORDS = ["buồn", "vui", "chill", "sôi động", "lãng mạn", "tối", "hùng tráng", "piano", "guitar", "dàn dây", "sáo", "đàn tranh", "808", "synth", "chuông", "giọng nữ", "giọng nam"];
const BEAT_WORDS = ["tối", "chill", "sôi động", "buồn", "hùng tráng", "piano", "guitar", "dàn dây", "sáo", "đàn tranh", "808", "synth", "chuông", "arp"];
const TAGS = [["Intro", "Mở đầu"], ["Verse", "Phiên khúc"], ["Pre-Chorus", "Tiền điệp khúc"], ["Chorus", "Điệp khúc"], ["Bridge", "Cầu nối"], ["Instrumental", "Gian tấu"], ["Outro", "Kết"]];
const USE = {
  style: ["Học phong cách", "Lấy tempo, giọng, năng lượng (ACE-Step: làm audio tham chiếu)"],
  loop: ["Vòng lặp", "Cắt 2–4 ô nhịp đẹp nhất, khớp tempo + giọng, trải suốt bài"],
  chop: ["Cắt lát (chop)", "Cắt theo nhịp đánh rồi xếp lại thành pattern mới"],
  kit: ["Lấy tiếng trống", "Tách kick / snare / hat trong clip làm bộ trống"],
  hook: ["Lấy hook (Micow Ear)", "Micow Ear tìm hook của clip rồi dùng đúng đoạn đó làm vòng lặp"],
  cover: ["Cover", "Giữ giai điệu / cấu trúc clip, đổi phong cách và lời (ACE-Step)"],
  complete: ["Làm đầy / nối dài", "Thêm nhạc cụ, giọng cho đoạn dang dở (ACE-Step base, Micow-LM)"],
};
const KEYS = (() => {
  const n = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"], vn = { C: "Đô", D: "Rê", E: "Mi", F: "Fa", G: "Son", A: "La", B: "Si" };
  const out = [];
  for (const m of ["minor", "major"]) for (const x of n) out.push([`${x} ${m}`, `${vn[x[0]]}${x[1] === "#" ? " thăng" : x[1] === "b" ? " giáng" : ""} ${m === "minor" ? "thứ" : "trưởng"} (${x}${m === "minor" ? "m" : ""})`]);
  return out;
})();
const SAMPLE_LYRICS = `[Verse 1]
Chiều nay phố vắng mưa rơi trên vai
Em đi qua đây nghe tim nhói đau
Đèn đường vàng hắt hiu trong đêm dài
Anh vẫn đứng đây chờ em quay lại

[Chorus]
Thôi đừng khóc nữa em ơi
Ngày mai nắng sẽ lên thôi
Mình cùng nhau đi qua bao con phố
Tay trong tay ta hát câu ca cũ

[Verse 2]
Gió mang mùa thu về trên mái nhà
Lá rơi nhẹ như lời ru của mẹ
Có những ngày ta lạc giữa phố xa
Vẫn nhớ về nơi bình yên rất nhẹ

[Chorus]
Thôi đừng khóc nữa em ơi
Ngày mai nắng sẽ lên thôi
Mình cùng nhau đi qua bao con phố
Tay trong tay ta hát câu ca cũ

[Outro]`;
const SUGGEST = {
  song: ["ballad buồn, piano, dàn dây, giọng nữ", "v-pop tươi sáng, guitar, synth, giọng nam", "r&b chill, rhodes, giọng nữ ngọt", "bolero trữ tình, guitar, sáo, giọng nam", "vinahouse sôi động, sáo, giọng nữ", "lofi chill, piano điện, giọng nữ nhẹ"],
  beat: ["trap tối, 808 nặng, chuông, 145 bpm", "lofi chill, piano điện, đĩa than", "boom bap, piano, dàn dây", "vinahouse sôi động, sáo", "house, pluck, 124 bpm", "cinematic hùng tráng, dàn dây"],
};

const App = {
  genres: FALLBACK_GENRES,
  engines: [],
  online: false,
  st: {},
  jobs: {},
  lib: [],

  async init() {
    hydrateIcons();
    API.init();
    Player.init();
    for (const b of $$("#nav button, #tabs button")) b.onclick = () => this.go(b.dataset.page);
    addEventListener("hashchange", () => this.go(location.hash.slice(1) || "song", false));
    $("#conn").onclick = () => this.showOffline(true);
    this.setupDownload();
    $("#srvRetry").onclick = () => { const u = $("#srvUrl").value.trim(); if (u) { API.base = u; store("server", u); } this.connect(); };
    for (const sec of $$(".page[data-mode]")) this.setupStudio(sec);
    this.setupLibrary();
    await this.connect();
    this.go(location.hash.slice(1) || "song", false);
  },

  async connect() {
    try {
      const h = await API.get("/api/health");
      this.online = true;
      $("#offline").hidden = true;
      $("#conn").className = "conn ok";
      $("#connTxt").textContent = `Đã kết nối · ${h.app} ${h.version}`;
      API.get("/api/system").then((s) => { this.sys = s; $("#connSub").textContent = s.gpu.backend === "cpu" ? "Chạy bằng CPU" : `${s.gpu.name} · ${s.gpu.vram_gb} GB`; this.renderSystem(); }).catch(() => {});
      const st = await API.get("/api/styles").catch(() => null);
      if (st && st.genres) this.genres = st.genres;
      await this.loadEngines();
      for (const sec of $$(".page[data-mode]")) { this.renderGenres(sec); this.refreshPlan(sec); }
      this.loadLibrary();
    } catch (e) {
      this.online = false;
      $("#conn").className = "conn bad";
      $("#connTxt").textContent = "Chưa kết nối máy chủ";
      $("#connSub").textContent = API.base;
      this.showOffline(true);
      for (const sec of $$(".page[data-mode]")) this.renderGenres(sec);
    }
  },
  setupDownload() {
    const pick = (os) => {
      for (const b of $$("#dlOs button")) b.setAttribute("aria-pressed", String(b.dataset.os === os));
      for (const d of $$(".dl-os")) d.hidden = d.dataset.os !== os;
      $("#dlZip").hidden = os !== "win";
    };
    const ua = navigator.userAgent;
    pick(/Windows/i.test(ua) ? "win" : /Mac OS X|Macintosh/i.test(ua) && !/iPhone|iPad/i.test(ua) ? "mac" : /Linux/i.test(ua) && !/Android/i.test(ua) ? "linux" : "win");
    for (const b of $$("#dlOs button")) b.onclick = () => pick(b.dataset.os);
    for (const b of $$("#offline .copy")) b.onclick = async () => {
      const txt = b.previousElementSibling.textContent.trim();
      try { await navigator.clipboard.writeText(txt); b.textContent = "Đã chép"; } catch { b.textContent = "Chọn và chép"; }
      setTimeout(() => { b.textContent = "Chép"; }, 1800);
    };
  },
  showOffline(force) { if (!this.online || force === true && !this.online) { $("#srvUrl").value = API.base; $("#offline").hidden = false; } else if (force) this.go("models"); },

  go(page, push = true) {
    if (!["song", "beat", "capcut", "library", "models"].includes(page)) page = "song";
    for (const p of $$(".page")) p.hidden = p.id !== "page-" + page;
    for (const b of $$("#nav button, #tabs button")) b.setAttribute("aria-current", b.dataset.page === page ? "page" : "false");
    if (push && location.hash !== "#" + page) history.replaceState(null, "", "#" + page);
    $("#main").scrollTop = 0;
    if (page === "library") this.loadLibrary();
    if (page === "models") this.renderModels();
    document.title = { song: "Tạo bài hát", beat: "Tạo beat", capcut: "Nhạc CapCut", library: "Thư viện", models: "Mô hình" }[page] + " · Micow";
    if (page === "capcut" && window.CC && !CC.songs.length) CC.restore();
  },

  // =============================== STUDIO (bài hát + beat) ===============================
  setupStudio(sec) {
    const mode = sec.dataset.mode;
    const saved = store("st-" + mode) || {};
    const S = this.st[mode] = { mode, genre: saved.genre || null, engine: saved.engine || "micow-dsp", clips: [],
      bpm: "", key: "", duration: mode === "beat" ? 90 : "", gender: saved.gender || "female", seed: "", guide: saved.guide !== false, energy: null };
    const styleEl = $("textarea.style", sec);
    styleEl.value = saved.style || "";
    const lyrEl = $("[data-lyrics]", sec);
    if (lyrEl) lyrEl.value = saved.lyrics ?? "";
    const save = debounce(() => store("st-" + mode, { genre: S.genre, engine: S.engine, style: styleEl.value, lyrics: lyrEl ? lyrEl.value : "", gender: S.gender, guide: S.guide }), 400);
    const replan = debounce(() => this.refreshPlan(sec), 450);
    S.changed = () => { save(); replan(); };
    styleEl.addEventListener("input", () => { this.syncWordChips(sec); S.changed(); });
    if (lyrEl) lyrEl.addEventListener("input", () => { this.lyrInfo(sec); S.changed(); });

    // chip tâm trạng / nhạc cụ
    const wc = $("[data-chips=words]", sec);
    for (const w of mode === "beat" ? BEAT_WORDS : WORDS) {
      wc.append(el("button", { class: "chip", "aria-pressed": "false", dataset: { w }, onclick: () => {
        const words = styleEl.value.split(/\s*,\s*/).filter(Boolean);
        const i = words.findIndex((x) => x.toLowerCase() === w);
        if (i >= 0) words.splice(i, 1); else words.push(w);
        styleEl.value = words.join(", ");
        this.syncWordChips(sec); S.changed();
      } }, w));
    }
    this.syncWordChips(sec);

    // tuỳ chỉnh nâng cao
    const adv = $("[data-adv]", sec);
    const keySel = el("select", { onchange: (e) => { S.key = e.target.value; S.changed(); } }, el("option", { value: "" }, "Tự động"), KEYS.map(([v, l]) => el("option", { value: v }, l)));
    const f = (label, ctrl) => el("div", { class: "field" }, el("label", {}, label), ctrl);
    const grid = el("div", { class: "fields" },
      f("Tempo (BPM)", el("input", { type: "number", min: 40, max: 220, placeholder: "tự động", oninput: (e) => { S.bpm = e.target.value; S.changed(); } })),
      f("Giọng (key)", keySel),
      mode === "song" ? f("Thời lượng", el("select", { onchange: (e) => { S.duration = e.target.value; S.changed(); } },
        el("option", { value: "" }, "Theo lời"), [60, 90, 120, 150, 180, 240].map((s) => el("option", { value: s }, `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`)))) : null,
      f("Seed", el("input", { type: "number", min: 0, placeholder: "ngẫu nhiên", oninput: (e) => { S.seed = e.target.value; S.changed(); } })));
    adv.append(grid);
    if (mode === "song") {
      const seg = el("div", { class: "seg" }, ["female", "male"].map((g) => el("button", { "aria-pressed": String(S.gender === g), onclick: (e) => {
        S.gender = g; $$("button", seg).forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget))); S.changed();
      } }, g === "female" ? "Giọng nữ" : "Giọng nam")));
      adv.append(el("div", { class: "row" }, el("span", { class: "muted" }, "Giọng hát"), seg));
      const tog = el("button", { class: "tog", "aria-pressed": String(S.guide), onclick: () => { S.guide = !S.guide; tog.setAttribute("aria-pressed", String(S.guide)); S.changed(); } }, "Micow Beat: hát giọng mẫu theo giai điệu");
      adv.append(tog);
      adv.append(el("p", { class: "note" }, "Giọng mẫu ngân nguyên âm theo giai điệu (demo). Giọng hát thật phát âm rõ lời: chọn engine ACE-Step 1.5."));
    }

    // năng lượng + thời lượng (beat)
    const en = $("[data-energy]", sec);
    if (en) en.oninput = () => { S.energy = +en.value ? +en.value / 100 : null; $("[data-rv=energy]", sec).textContent = S.energy == null ? "tự động" : `${en.value}%`; S.changed(); };
    const du = $("[data-dur]", sec);
    if (du) du.oninput = () => { S.duration = +du.value; $("[data-rv=dur]", sec).textContent = `${fmtTime(+du.value)}`; S.changed(); };

    // thẻ đoạn
    const tb = $("[data-tagbar]", sec);
    if (tb) for (const [en_, vi] of TAGS) tb.append(el("button", { class: "tag", title: `Chèn [${en_}]`, onclick: () => this.insertTag(lyrEl, en_) }, vi));
    $$("[data-act=sample]", sec).forEach((b) => (b.onclick = () => { if (lyrEl.value.trim() && !confirm("Thay lời hiện tại bằng lời mẫu?")) return; lyrEl.value = SAMPLE_LYRICS; this.lyrInfo(sec); S.changed(); }));
    $$("[data-act=suggest]", sec).forEach((b) => (b.onclick = () => { const a = SUGGEST[mode]; styleEl.value = a[Math.floor(Math.random() * a.length)]; this.syncWordChips(sec); S.changed(); }));

    // clip mẫu
    this.setupClips(sec, S);

    // cột phải: bản thiết kế + engine + nút tạo + công việc
    const side = $("[data-side]", sec);
    side.append(
      el("div", { class: "card plan" }, el("div", { class: "ch" }, el("span", {}, "Bản thiết kế"), el("span", { class: "sub", dataset: { planSub: "" } }, "cập nhật khi bạn gõ")),
        el("div", { class: "chips", dataset: { planChips: "" } }), el("div", { class: "tl", dataset: { tl: "" } }), el("div", { class: "ruler", dataset: { ruler: "" } }),
        el("div", { class: "chords", dataset: { chords: "" } }), el("div", { class: "note", dataset: { planNotes: "" } })),
      el("div", { class: "card" }, el("div", { class: "ch" }, el("span", {}, "Engine"), el("button", { class: "ghost", onclick: () => this.go("models") }, "Quản lý")), el("div", { class: "engs", dataset: { engs: "" } })),
      el("button", { class: "primary go", dataset: { go: "" }, html: ico("spark") + (mode === "song" ? "Tạo bài hát" : "Tạo beat"), onclick: () => this.generate(sec) }),
      el("div", { class: "jobs", dataset: { jobs: "" } }));
    this.renderGenres(sec);
    this.lyrInfo(sec);
  },

  syncWordChips(sec) {
    const words = $("textarea.style", sec).value.toLowerCase().split(/\s*,\s*/);
    $$("[data-chips=words] .chip", sec).forEach((c) => c.setAttribute("aria-pressed", String(words.includes(c.dataset.w))));
  },

  insertTag(ta, tag) {
    const s = ta.selectionStart ?? ta.value.length;
    const before = ta.value.slice(0, s), after = ta.value.slice(s);
    const pre = before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
    const ins = `${pre}[${tag}]\n`;
    ta.value = before + ins + after;
    ta.focus();
    ta.selectionStart = ta.selectionEnd = (before + ins).length;
    ta.dispatchEvent(new Event("input"));
  },

  lyrInfo(sec) {
    const ta = $("[data-lyrics]", sec), out = $("[data-lyrinfo]", sec);
    if (!ta || !out) return;
    const lines = ta.value.split("\n").map((l) => l.trim()).filter((l) => l && !/^\[.*\]$/.test(l) && !l.startsWith("#"));
    const words = lines.join(" ").split(/\s+/).filter(Boolean).length;
    out.textContent = lines.length ? `${lines.length} câu · ${words} chữ` : "";
  },

  renderGenres(sec) {
    const S = this.st[sec.dataset.mode];
    const host = $("[data-chips=genre]", sec) || $("[data-gtiles]", sec);
    if (!host) return;
    host.innerHTML = "";
    const tiles = host.hasAttribute("data-gtiles");
    const auto = { id: null, name: "Tự động", desc: "Đoán theo mô tả / clip", bpm: null };
    for (const g of [auto, ...this.genres]) {
      const pressed = String((S.genre || null) === g.id);
      const onclick = () => { S.genre = g.id; this.renderGenres(sec); S.changed(); };
      host.append(tiles
        ? el("button", { class: "gtile", "aria-pressed": pressed, onclick }, el("b", {}, g.name), el("small", {}, g.desc), g.bpm ? el("span", { class: "tc" }, `${g.bpm[0]}–${g.bpm[1]} BPM`) : null)
        : el("button", { class: "chip", "aria-pressed": pressed, title: g.desc, onclick }, g.name));
    }
  },

  // ---------- clip mẫu ----------
  setupClips(sec, S) {
    const card = $("[data-clips-card]", sec);
    card.append(el("div", { class: "ch" }, el("span", {}, "Đoạn nhạc mẫu"), el("span", { class: "sub" }, "tuỳ chọn · tối đa 8 phút mỗi đoạn")));
    const drop = el("div", { class: "drop", tabindex: "0", role: "button", html: `${ico("upload")}<br><b>Thả đoạn nhạc vào đây</b> hoặc bấm để chọn<br><small>mp3, wav, m4a, flac… – Micow đo tempo, giọng, năng lượng và dùng làm nguyên liệu</small>` });
    const list = el("div", { class: "clips", dataset: { clipList: "" } });
    card.append(drop, list);
    const pick = () => { const fi = $("#fileIn"); fi.onchange = () => { this.addFiles(sec, [...fi.files]); fi.value = ""; }; fi.click(); };
    drop.onclick = pick;
    drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } };
    for (const t of [drop, card]) {
      t.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
      t.addEventListener("dragleave", () => drop.classList.remove("over"));
      t.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); this.addFiles(sec, [...e.dataTransfer.files].filter((f) => /audio|\.(mp3|wav|m4a|flac|ogg|aac)$/i.test(f.type + f.name))); });
    }
  },

  async addFiles(sec, files) {
    if (!this.online) return this.showOffline(true);
    const S = this.st[sec.dataset.mode];
    for (const f of files) {
      const c = { tmp: Math.random(), name: f.name, busy: "Đang chuẩn bị", use: "style" };
      S.clips.push(c);
      this.renderClips(sec);
      try {
        const m = await API.upload(f, (stage) => { c.busy = stage; this.renderClips(sec); });
        Object.assign(c, m, { busy: null });
        const kind = m.analysis && m.analysis.kind;
        c.use = S.mode === "beat" ? (kind === "drums" ? "kit" : "loop") : "style";
        toast(`${m.name}: ${m.analysis.bpm ? Math.round(m.analysis.bpm) + " BPM, " : ""}${m.analysis.key ? m.analysis.key.name_vi : ""}`);
      } catch (e) {
        S.clips.splice(S.clips.indexOf(c), 1);
        toast("Không đọc được " + f.name + ": " + e.message, 5000);
      }
      this.renderClips(sec);
      S.changed();
    }
  },

  async addClipFromItem(item, mode) {
    const sec = $(`#page-${mode}`);
    const blob = await (await fetch(API.file(item.id, item.files.wav))).blob();
    this.go(mode);
    await this.addFiles(sec, [new File([blob], item.title + ".wav", { type: "audio/wav" })]);
  },

  renderClips(sec) {
    const S = this.st[sec.dataset.mode], list = $("[data-clip-list]", sec);
    list.innerHTML = "";
    const eng = S.engine;
    for (const c of S.clips) {
      if (c.busy) { list.append(el("div", { class: "clip" }, el("span", { class: "spin" }), el("div", {}, el("div", { class: "cn" }, c.name), el("small", { class: "muted" }, c.busy)), el("span"))); continue; }
      const a = c.analysis || {};
      const uses = Object.keys(USE).filter((u) => eng === "micow-dsp" ? ["style", "loop", "chop", "kit", "hook"].includes(u) : eng === "micow-lm" ? ["style", "complete"].includes(u) : u !== "hook");
      if (!uses.includes(c.use)) c.use = uses[0];
      const sel = el("select", { title: USE[c.use][1], onchange: (e) => { c.use = e.target.value; sel.title = USE[c.use][1]; S.changed(); } },
        uses.map((u) => el("option", { value: u, selected: u === c.use }, USE[u][0])));
      const cv = el("canvas", { class: "cw" });
      const audio = new Audio(API.url(`/api/uploads/${c.id}/audio`));
      const play = el("button", { class: "round", "aria-label": "Nghe thử", html: ico("play"), onclick: () => {
        if (audio.paused) { audio.play(); play.innerHTML = ico("pause"); } else { audio.pause(); play.innerHTML = ico("play"); }
      } });
      audio.onended = () => (play.innerHTML = ico("play"));
      audio.ontimeupdate = () => drawWave(cv, c.peaks, audio.currentTime / (audio.duration || 1));
      list.append(el("div", { class: "clip" }, play,
        el("div", { style: "min-width:0" }, el("div", { class: "cn", title: c.name }, c.name), cv,
          el("div", { class: "cm" }, a.bpm ? el("span", { class: "badge n" }, `${Math.round(a.bpm)} BPM`) : null, a.key ? el("span", { class: "badge n" }, a.key.name_vi) : null,
            el("span", { class: "badge n" }, fmtTime(c.duration)), el("span", { class: "badge n" }, { drums: "trống", music: "nhạc", tonal: "giai điệu" }[a.kind] || ""))),
        el("div", { class: "cx row" }, sel, el("button", { class: "icon ghost", "aria-label": "Bỏ clip", html: ico("x"), onclick: () => { audio.pause(); S.clips.splice(S.clips.indexOf(c), 1); this.renderClips(sec); S.changed(); } }))));
      requestAnimationFrame(() => drawWave(cv, c.peaks, -1));
    }
  },

  // ---------- engine ----------
  async loadEngines() {
    this.engines = await API.get("/api/engines").catch(() => []);
    for (const sec of $$(".page[data-mode]")) this.renderEngines(sec);
  },
  renderEngines(sec) {
    const S = this.st[sec.dataset.mode], host = $("[data-engs]", sec);
    if (!host) return;
    host.innerHTML = "";
    const list = this.engines.length ? this.engines : [{ id: "micow-dsp", name: "Micow Beat", ready: true, description: "Có sẵn, chạy CPU." }];
    if (!list.find((e) => e.id === S.engine && e.ready)) S.engine = "micow-dsp";
    for (const e of list) {
      const st = e.ready ? (e.running ? el("span", { class: "badge ok" }, "Đang chạy") : el("span", { class: "badge ok" }, e.needs_install === false ? "Có sẵn" : "Sẵn sàng"))
        : el("span", { class: "badge warn" }, e.installed ? "Chưa có mô hình" : "Chưa cài");
      host.append(el("button", { class: "eng" + (e.ready ? "" : " off"), "aria-pressed": String(S.engine === e.id), onclick: () => {
        if (!e.ready) { toast(e.message || "Engine chưa sẵn sàng"); this.go("models"); return; }
        S.engine = e.id; this.renderEngines(sec); this.renderClips(sec); S.changed();
      } }, el("span", { class: "rd" }), el("span", {}, el("b", {}, e.name), e.vocals ? el("span", { class: "badge", style: "margin-left:8px" }, "giọng hát thật") : null,
        el("small", {}, e.description || ""), el("div", { class: "st" }, st))));
    }
  },

  // ---------- bản thiết kế ----------
  request(sec) {
    const S = this.st[sec.dataset.mode];
    const lyr = $("[data-lyrics]", sec);
    return { mode: S.mode, engine: S.engine, style: $("textarea.style", sec).value, genre: S.genre, lyrics: lyr ? lyr.value : "",
      duration: S.duration ? +S.duration : null, bpm: S.bpm ? +S.bpm : null, key: S.key || null, energy: S.energy,
      seed: S.seed !== "" ? +S.seed : null, gender: S.gender, guide_vocal: S.guide,
      clips: S.clips.filter((c) => c.id && !c.busy).map((c) => ({ id: c.id, use: c.use })) };
  },
  async refreshPlan(sec) {
    if (!this.online) return;
    const req = this.request(sec);
    req.seed = req.seed ?? 0;
    try {
      const p = await API.post("/api/plan", req);
      this.renderPlan(sec, p);
    } catch (e) { $("[data-plan-notes]", sec).textContent = e.message; }
  },
  renderPlan(sec, p) {
    const chips = $("[data-plan-chips]", sec);
    chips.innerHTML = "";
    const lang = { vi: "Tiếng Việt", en: "Tiếng Anh", ja: "Tiếng Nhật", ko: "Tiếng Hàn", zh: "Tiếng Trung" }[p.language];
    for (const t of [p.style.genre_name, `${p.bpm} BPM`, p.key.name_vi, fmtTime(p.duration), p.mode === "song" && lang ? lang : null, p.mode === "song" ? (p.style.vocal === "male" ? "giọng nam" : "giọng nữ") : "không lời"])
      if (t) chips.append(el("span", { class: "badge" + (t === p.style.genre_name ? "" : " n") }, t));
    const tl = $("[data-tl]", sec);
    tl.innerHTML = "";
    for (const s of p.sections) {
      tl.append(el("div", { class: "sec " + s.kind, style: `flex:${s.bars}`, title: `${s.label} · ${s.bars} ô nhịp · ${fmtTime(s.start)}–${fmtTime(s.end)}${s.lines.length ? "\n" + s.lines.join("\n") : ""}` },
        el("span", {}, s.label), el("small", {}, `${s.bars}`), el("i", { class: "en", style: `width:${Math.round(s.energy * 100)}%` })));
    }
    const r = $("[data-ruler]", sec);
    r.innerHTML = "";
    for (let i = 0; i <= 4; i++) r.append(el("span", {}, fmtTime(p.duration * i / 4)));
    const ch = $("[data-chords]", sec);
    ch.innerHTML = "";
    const seen = new Set();
    for (const s of p.sections) {
      const key = s.kind + s.chords.join();
      if (seen.has(key)) continue;
      seen.add(key);
      const uniq = [];
      for (const c of s.chords) if (uniq[uniq.length - 1] !== c) uniq.push(c);
      ch.append(el("div", {}, el("b", {}, s.label), uniq.slice(0, 8).join(" · ")));
    }
    $("[data-plan-notes]", sec).textContent = (p.notes || []).join(" · ");
    $("[data-plan-sub]", sec).textContent = `${p.total_bars} ô nhịp · ${p.sections.length} đoạn`;
  },

  // ---------- tạo nhạc ----------
  async generate(sec) {
    if (!this.online) return this.showOffline(true);
    const S = this.st[sec.dataset.mode];
    const req = this.request(sec);
    if (S.clips.some((c) => c.busy)) return toast("Đợi clip phân tích xong đã");
    if (S.mode === "song" && !req.lyrics.trim() && !req.style.trim() && !req.genre) return toast("Hãy viết lời hoặc mô tả phong cách");
    try {
      const job = await API.post("/api/generate", req);
      this.trackJob(sec, job);
    } catch (e) { toast(e.message, 5000); }
  },
  trackJob(sec, job) { this.trackJobHost($("[data-jobs]", sec), job); },
  trackJobHost(host, job) {
    const card = el("div", { class: "job" }, el("div", { class: "jt" }, el("span", {}, "Đang tạo…"), el("button", { class: "ghost", style: "padding:4px 10px", onclick: () => API.post(`/api/jobs/${job.id}/cancel`) }, "Huỷ")),
      el("div", { class: "bar" }, el("i")), el("div", { class: "jm" }, job.message));
    host.prepend(card);
    const t0 = Date.now();
    const tick = async () => {
      let j;
      try { j = await API.get(`/api/jobs/${job.id}`); } catch { setTimeout(tick, 2000); return; }
      $(".bar i", card).style.width = Math.round(j.progress * 100) + "%";
      $(".jm", card).textContent = j.message + ` · ${Math.round((Date.now() - t0) / 1000)} giây`;
      if (j.status === "done") {
        const item = j.result;
        card.replaceWith(this.trackCard(item));
        this.lib.unshift(item);
        Player.load(item, true);
        toast(`Xong: ${item.title}`);
      } else if (j.status === "error" || j.status === "cancelled") {
        card.classList.add("err");
        $(".jt span", card).textContent = j.status === "cancelled" ? "Đã huỷ" : "Lỗi";
        $(".jm", card).textContent = j.error || j.message;
        $(".jt button", card).textContent = "Đóng";
        $(".jt button", card).onclick = () => card.remove();
      } else setTimeout(tick, 700);
    };
    tick();
  },

  // =============================== BÀI / THƯ VIỆN ===============================
  metaLine(it) {
    const cc = it.mode === "capcut" ? "CapCut" + (it.capcut && it.capcut.peak_at != null ? ` · drop ${it.capcut.peak_at}s` : "") : null;
    return [cc || it.genre_name, it.bpm ? `${Math.round(it.bpm)} BPM` : null, it.key && it.key.name_vi, fmtTime(it.duration), it.engine_name].filter(Boolean).join(" · ");
  },
  trackCard(it) {
    const cv = el("canvas");
    const play = el("button", { class: "round play", "aria-label": "Phát", html: ico(Player.playing(it.id) ? "pause" : "play"), onclick: () => {
      if (Player.item && Player.item.id === it.id) Player.toggle(); else Player.load(it, true);
    } });
    cv.onclick = (e) => { if (!Player.item || Player.item.id !== it.id) Player.load(it, true); setTimeout(() => Player.seekFrac(e.offsetX / cv.clientWidth), 60); };
    const dl = el("button", { class: "icon ghost", "aria-label": "Tải về", html: ico("download"), onclick: (e) => { e.stopPropagation(); this.downloadMenu(dl, it); } });
    const more = el("button", { class: "icon ghost", "aria-label": "Thêm", html: ico("more"), onclick: (e) => { e.stopPropagation(); this.moreMenu(more, it); } });
    const card = el("div", { class: "track" + (Player.item && Player.item.id === it.id ? " cur" : ""), dataset: { id: it.id } }, play,
      el("div", { style: "min-width:0" }, el("div", { class: "tt", title: it.title }, it.title), el("div", { class: "tm" }, this.metaLine(it)), cv),
      el("div", { class: "ta" }, dl, more));
    requestAnimationFrame(() => drawWave(cv, it.peaks, Player.item && Player.item.id === it.id ? (Player.a.currentTime / (Player.a.duration || 1)) : -1));
    return card;
  },
  syncPlayIcons() { $$(".track").forEach((t) => { const b = $(".round.play", t); if (b) b.innerHTML = ico(Player.playing(t.dataset.id) ? "pause" : "play"); }); },
  downloadMenu(anchor, it) {
    const f = it.files || {}, slug = (it.title || "micow").replace(/[\\/:*?"<>|]+/g, "");
    const items = [{ header: "Tải về" }, { label: "WAV (chất lượng gốc)", icon: "download", href: API.file(it.id, f.wav, slug + ".wav"), download: "" }];
    if (f.mp3) items.push({ label: "MP3 256 kbps", icon: "download", href: API.file(it.id, f.mp3, slug + ".mp3"), download: "" });
    if (f.midi) items.push({ label: "MIDI (kèm lời)", hint: "DAW", icon: "note", href: API.file(it.id, f.midi, slug + ".mid"), download: "" });
    if (f.lrc) items.push({ label: "Lời .lrc", hint: "Bravin", icon: "edit", href: API.file(it.id, f.lrc, slug + ".lrc"), download: "" });
    if (f.markers) items.push({ label: "Mốc nhịp .csv", hint: "cắt cảnh theo nhịp", icon: "target", href: API.file(it.id, f.markers, slug + "_moc_nhip.csv"), download: "" });
    if (f.bravin) items.push({ label: "Dự án Bravin 9:16", hint: ".bravin.json", icon: "link", href: API.file(it.id, f.bravin, slug + ".bravin.json"), download: "" });
    items.push({ label: f.stems ? "Trọn gói + stem (.zip)" : "Trọn gói (.zip)", icon: "download", href: API.url(`/api/library/${it.id}/zip`), download: "" });
    menu(anchor, items);
  },
  moreMenu(anchor, it) {
    const req = (it.request || {});
    menu(anchor, [
      { label: "Tạo lại (seed mới)", icon: "redo", onclick: async () => {
        const mode = it.mode === "beat" ? "beat" : "song", sec = $(`#page-${mode}`);
        if (it.mode === "capcut") { try { this.go("capcut"); this.trackJobHost($("#ccJobs"), await API.post(it.engine === "micow-ear" ? "/api/capcut" : "/api/generate", Object.assign({}, req, { seed: null }))); } catch (e) { toast(e.message); } return; }
        const r = Object.assign({}, req, { seed: null });
        try { this.go(mode); this.trackJob(sec, await API.post("/api/generate", r)); } catch (e) { toast(e.message); }
      } },
      { label: "Dùng làm đoạn mẫu (bài hát)", icon: "upload", onclick: () => this.addClipFromItem(it, "song") },
      { label: "Dùng làm đoạn mẫu (beat)", icon: "upload", onclick: () => this.addClipFromItem(it, "beat") },
      { label: "Đổi tên", icon: "edit", onclick: async () => {
        const t = prompt("Tên bài", it.title); if (!t) return;
        const m = await API.post(`/api/library/${it.id}/rename`, { title: t }); Object.assign(it, m); this.renderLibrary(); if (Player.item && Player.item.id === it.id) $("#pTitle").textContent = it.title;
      } },
      { label: "Xoá", icon: "trash", onclick: async () => {
        if (!confirm(`Xoá "${it.title}" khỏi máy?`)) return;
        await API.del(`/api/library/${it.id}`); this.lib = this.lib.filter((x) => x.id !== it.id); $$(`.track[data-id="${it.id}"]`).forEach((t) => t.remove()); this.renderLibrary();
      } },
    ]);
  },
  setupLibrary() {
    $("#libRefresh").onclick = () => this.loadLibrary();
    $("#libSearch").oninput = debounce(() => this.renderLibrary(), 150);
    $$("#libFilter button").forEach((b) => (b.onclick = () => { $$("#libFilter button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); this.renderLibrary(); }));
  },
  async loadLibrary() {
    if (!this.online) return;
    this.lib = await API.get("/api/library").catch(() => this.lib);
    this.renderLibrary();
  },
  renderLibrary() {
    const host = $("#libList");
    host.innerHTML = "";
    const f = ($("#libFilter [aria-pressed=true]") || {}).dataset?.f || "all";
    const q = $("#libSearch").value.trim().toLowerCase();
    const items = this.lib.filter((it) => (f === "all" || it.mode === f) && (!q || (it.title + " " + it.genre_name + " " + (it.request?.style || "")).toLowerCase().includes(q)));
    if (!items.length) { host.append(el("div", { class: "empty", style: "grid-column:1/-1" }, this.lib.length ? "Không có bài khớp." : "Chưa có bài nào. Hãy tạo bài hát hoặc beat đầu tiên!")); return; }
    for (const it of items) host.append(this.trackCard(it));
  },

  // =============================== MÔ HÌNH ===============================
  renderSystem() {
    const s = this.sys;
    if (!s) return;
    const box = $("#sysInfo");
    box.innerHTML = "";
    const g = s.gpu.backend === "cpu" ? "Không có (chạy CPU)" : `${s.gpu.name} · ${s.gpu.vram_gb} GB`;
    for (const [k, v] of [["Hệ điều hành", s.os], ["GPU", g], ["RAM", `${s.ram_gb} GB`], ["CPU", `${s.cores} luồng`], ["Ổ trống", `${s.disk_free_gb} GB`], ["ffmpeg", s.ffmpeg ? "Có (xuất MP3)" : "Không (chỉ WAV)"], ["PyTorch", s.torch ? "Có" : "Chưa cài"], ["Dữ liệu", s.home]])
      box.append(el("div", { class: k === "Dữ liệu" ? "wide" : null }, el("small", {}, k), el("b", { title: v }, v)));
    $("#sysRec").textContent = s.recommended_engine === "ace-step" ? "Gợi ý: máy đủ mạnh để cài ACE-Step 1.5" : "Gợi ý: dùng Micow Beat (máy chưa có GPU đủ mạnh)";
  },
  async renderModels() {
    if (!this.online) return;
    await this.loadEngines();
    const host = $("#engList");
    host.innerHTML = "";
    for (const e of this.engines) {
      const acts = el("div", { class: "acts" });
      const log = el("div", { class: "log", hidden: true });
      const status = e.ready ? el("span", { class: "badge ok" }, e.running ? "Đang chạy" : e.needs_install === false ? "Có sẵn" : "Sẵn sàng") : el("span", { class: "badge warn" }, e.installed ? "Chưa sẵn sàng" : "Chưa cài");
      const card = el("div", { class: "card mcard" }, el("div", { class: "ch" }, el("span", {}, e.name, " ", status), el("span", { class: "sub" }, e.license || "")),
        el("p", { class: "note" }, e.description), el("p", { class: "note" }, e.message || ""), acts, log);
      if (e.id === "ace-step") {
        const base = el("input", { type: "checkbox", id: "aceBase" });
        if (!e.running) acts.append(el("button", { class: "primary", html: ico("download") + (e.installed ? "Cài lại / cập nhật" : "Cài ACE-Step 1.5"), onclick: () => this.runAction(`/api/engines/ace-step/install`, { with_base: base.checked }, log) }),
          el("label", { class: "row", style: "gap:8px;font-size:13px" }, base, "Tải thêm model base (cho “Làm đầy”, +5 GB)"));
        if (e.installed && !e.running) acts.append(el("button", { class: "tonal", html: ico("power") + "Khởi động", onclick: () => this.runAction(`/api/engines/ace-step/start`, {}, log) }));
        if (e.running) acts.append(el("button", { html: ico("power") + "Dừng", onclick: async () => { await API.post(`/api/engines/ace-step/stop`); this.renderModels(); } }));
        const url = el("input", { type: "url", value: e.url || "http://127.0.0.1:8001", style: "flex:1;min-width:200px" });
        const ext = el("input", { type: "checkbox" });
        ext.checked = e.managed === false;
        card.append(el("details", { class: "adv" }, el("summary", {}, "Máy chủ ACE-Step khác (LAN)"), el("div", { class: "body" },
          el("p", { class: "note" }, "Đã chạy ACE-Step 1.5 trên máy khác (uv run acestep-api)? Nhập địa chỉ rồi bật “dùng máy chủ ngoài”."),
          el("div", { class: "row" }, url, el("label", { class: "row", style: "gap:8px;font-size:13px" }, ext, "Dùng máy chủ ngoài"),
            el("button", { class: "tonal", onclick: async () => { await API.post("/api/settings", { acestep: { url: url.value.trim(), managed: !ext.checked } }); toast("Đã lưu"); this.renderModels(); } }, "Lưu")))));
      }
      if (e.id === "micow-lm") {
        if (!e.installed) acts.append(el("button", { class: "primary", html: ico("download") + "Cài PyTorch", onclick: () => this.runAction(`/api/engines/micow-lm/install`, {}, log) }));
        for (const m of e.models || []) acts.append(el("span", { class: "badge n" }, `${m.name} · ${m.size_mb} MB`));
      }
      host.append(card);
    }
  },
  async runAction(path, body, log) {
    try {
      const job = await API.post(path, body);
      log.hidden = false;
      const poll = async () => {
        const j = await API.get(`/api/jobs/${job.id}`).catch(() => null);
        if (!j) return setTimeout(poll, 2000);
        log.textContent = j.log.join("\n");
        log.scrollTop = log.scrollHeight;
        if (j.status === "running" || j.status === "queued") setTimeout(poll, 1200);
        else { toast(j.status === "done" ? "Hoàn tất" : "Lỗi: " + (j.error || "")); this.loadEngines(); if (j.status === "done") setTimeout(() => this.renderModels(), 400); }
      };
      poll();
    } catch (e) { toast(e.message); }
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());
