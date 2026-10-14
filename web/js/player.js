"use strict";
/* Thanh phát cố định: phát bài trong thư viện, sóng âm + đầu phát vàng, tua bằng cách bấm vào sóng. */
const Player = {
  item: null,
  init() {
    this.a = $("#pAudio");
    this.cv = $("#pWave");
    $("#pPlay").onclick = () => this.toggle();
    this.cv.onclick = (e) => this.seekFrac(e.offsetX / this.cv.clientWidth);
    $("#pMore").onclick = (e) => { e.stopPropagation(); if (this.item) App.downloadMenu($("#pMore"), this.item); };
    this.a.addEventListener("timeupdate", () => this.paint());
    this.a.addEventListener("play", () => this.icon());
    this.a.addEventListener("pause", () => this.icon());
    this.a.addEventListener("ended", () => this.icon());
    this.a.addEventListener("loadedmetadata", () => this.paint());
    addEventListener("resize", () => this.paint());
    addEventListener("keydown", (e) => {
      if (e.code === "Space" && this.item && !/INPUT|TEXTAREA|SELECT|BUTTON/.test(document.activeElement.tagName)) { e.preventDefault(); this.toggle(); }
    });
  },
  load(item, autoplay = true) {
    this.item = item;
    const bar = $("#player");
    bar.hidden = false;
    document.documentElement.style.setProperty("--playerh", bar.offsetHeight + "px");
    $("#pTitle").textContent = item.title;
    $("#pMeta").textContent = App.metaLine(item);
    this.a.src = API.file(item.id, item.files.mp3 || item.files.wav);
    if (autoplay) this.a.play().catch(() => {});
    this.paint();
    $$(".track").forEach((t) => t.classList.toggle("cur", t.dataset.id === item.id));
  },
  toggle() { if (!this.item) return; this.a.paused ? this.a.play().catch(() => {}) : this.a.pause(); },
  seekFrac(f) { if (this.a.duration) { this.a.currentTime = f * this.a.duration; this.paint(); } },
  icon() { $("#pPlay").innerHTML = ico(this.a.paused ? "play" : "pause"); App.syncPlayIcons(); },
  paint() {
    if (!this.item) return;
    const d = this.a.duration || this.item.duration || 0, t = this.a.currentTime || 0;
    drawWave(this.cv, this.item.peaks, d ? t / d : 0);
    $("#pTime").innerHTML = `<b>${fmtTime(t)}</b> / ${fmtTime(d)}`;
    const c = $(`.track[data-id="${this.item.id}"] canvas`);
    if (c) drawWave(c, this.item.peaks, d ? t / d : 0);
  },
  playing(id) { return this.item && this.item.id === id && !this.a.paused; },
};
