"use strict";
/* Tiện ích giao diện: chọn phần tử, biểu tượng, toast, menu, vẽ sóng âm, định dạng thời gian. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(e.dataset, v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}

const ICONS = {
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  drum: "M4 8c0-1.9 3.6-3.5 8-3.5S20 6.1 20 8s-3.6 3.5-8 3.5S4 9.9 4 8zM4 8v8c0 1.9 3.6 3.5 8 3.5s8-1.6 8-3.5V8M8 11v8M16 11v8",
  note: "M9 18V5l11-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
  chip: "M7 7h10v10H7zM9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4",
  play: "M7 5l12 7-12 7z",
  pause: "M7 5h3.5v14H7zM13.5 5H17v14h-3.5z",
  download: "M12 3v12M7 10l5 5 5-5M5 21h14",
  upload: "M12 16V4M7 9l5-5 5 5M5 20h14",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  spark: "M12 3l1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.7 1.8 1.8.7-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7z",
  x: "M6 6l12 12M18 6L6 18",
  refresh: "M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5",
  edit: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  check: "M5 12l5 5 9-9",
  wave: "M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0",
  redo: "M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3",
  power: "M12 3v9M6.3 6.3a8 8 0 1 0 11.4 0",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
};
function ico(name, cls = "i") {
  const fill = name === "play" || name === "pause" ? ' fill="currentColor" stroke="none"' : "";
  return `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name] || ""}"${fill}/></svg>`;
}
function hydrateIcons(root = document) {
  $$("i[data-ico]", root).forEach((i) => { i.outerHTML = ico(i.dataset.ico); });
}

let toastTimer = 0;
function toast(msg, ms = 3200) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}

let openMenuEl = null;
function closeMenu() { if (openMenuEl) { openMenuEl.remove(); openMenuEl = null; } }
function menu(anchor, items) {
  closeMenu();
  const m = el("div", { class: "menu", role: "menu" });
  for (const it of items) {
    if (it.header) { m.append(el("div", { class: "mh" }, it.header)); continue; }
    const tag = it.href ? "a" : "button";
    const b = el(tag, { role: "menuitem", href: it.href, download: it.download, target: it.href && !it.download ? "_blank" : null,
      onclick: (e) => { if (it.onclick) { e.preventDefault(); it.onclick(); } closeMenu(); } });
    b.innerHTML = (it.icon ? ico(it.icon) : "") + `<span>${it.label}</span>` + (it.hint ? `<small>${it.hint}</small>` : "");
    m.append(b);
  }
  document.body.append(m);
  const r = anchor.getBoundingClientRect();
  const w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + "px";
  m.style.top = (r.top - h - 8 > 8 ? r.top - h - 8 : r.bottom + 8) + "px";
  openMenuEl = m;
  setTimeout(() => document.addEventListener("click", closeMenu, { once: true }), 0);
}

function fmtTime(s) {
  s = Math.max(0, s || 0);
  const m = Math.floor(s / 60), x = Math.floor(s % 60);
  return `${m}:${String(x).padStart(2, "0")}`;
}

/** Vẽ sóng âm từ mảng đỉnh (0..1). progress 0..1 tô màu iris, đầu phát màu vàng (vàng = thời gian). */
function drawWave(canvas, peaks, progress = -1, opts = {}) {
  if (!canvas) return;
  const dpr = devicePixelRatio || 1;
  const w = canvas.clientWidth || 300, h = canvas.clientHeight || 40;
  if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
  const c = canvas.getContext("2d");
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, w, h);
  const css = getComputedStyle(document.documentElement);
  const base = opts.base || "#4a4b57", acc = css.getPropertyValue("--accent").trim() || "#7b6cf6";
  const gold = css.getPropertyValue("--gold").trim() || "#f2c14e";
  const n = Math.max(1, Math.floor(w / 3));
  const P = peaks && peaks.length ? peaks : [0];
  const mx = Math.max(0.05, ...P);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * P.length / n), b = Math.max(a + 1, Math.floor((i + 1) * P.length / n));
    let v = 0;
    for (let k = a; k < b && k < P.length; k++) v = Math.max(v, P[k]);
    const bh = Math.max(2, (v / mx) * (h - 4));
    c.fillStyle = progress >= 0 && i / n <= progress ? acc : base;
    const x = i * 3;
    c.beginPath();
    if (c.roundRect) c.roundRect(x, (h - bh) / 2, 2, bh, 1); else c.rect(x, (h - bh) / 2, 2, bh);
    c.fill();
  }
  if (progress >= 0) {
    c.fillStyle = gold;
    c.fillRect(Math.min(w - 2, progress * w), 0, 2, h);
  }
}

/** Đỉnh sóng từ AudioBuffer (cho clip vừa thả). */
function bufferPeaks(buf, n = 300) {
  const ch = buf.getChannelData(0), k = Math.max(1, Math.floor(ch.length / n)), out = [];
  for (let i = 0; i < n; i++) { let m = 0; for (let j = i * k; j < (i + 1) * k && j < ch.length; j += 4) m = Math.max(m, Math.abs(ch[j])); out.push(m); }
  return out;
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem("micow-" + k)); localStorage.setItem("micow-" + k, JSON.stringify(v)); } catch { return null; } }
