"use strict";
/* Kết nối máy chủ Micow cục bộ (mặc định http://127.0.0.1:5690). Giao diện có thể được phát bởi chính
   máy chủ đó, hoặc từ bản web trên Internet – mô hình luôn chạy trên máy người dùng. */
const API = {
  base: "",
  init() {
    const saved = store("server");
    const local = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.port === "5690";
    this.base = saved || (location.protocol.startsWith("http") && local ? location.origin : "http://127.0.0.1:5690");
  },
  url(p) { return this.base.replace(/\/$/, "") + p; },
  async req(path, opts = {}) {
    const r = await fetch(this.url(path), opts);
    const ct = r.headers.get("content-type") || "";
    const data = ct.includes("json") ? await r.json() : await r.text();
    if (!r.ok) throw new Error((data && data.error) || `Lỗi ${r.status}`);
    return data;
  },
  get(p) { return this.req(p); },
  post(p, body) { return this.req(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); },
  del(p) { return this.req(p, { method: "DELETE" }); },
  file(id, path, dl) { return this.url(`/files/${id}/${path}`) + (dl ? `?download=${encodeURIComponent(dl)}` : ""); },

  /** Giải mã clip ngay trong trình duyệt (mp3/m4a/ogg… không cần ffmpeg), gửi WAV 16-bit lên máy chủ. */
  async upload(file, onStage) {
    let body = file, name = file.name, peaks = null;
    try {
      onStage && onStage("Đang giải mã");
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 });
      const buf = await ctx.decodeAudioData(await file.arrayBuffer());
      ctx.close && ctx.close();
      peaks = bufferPeaks(buf);
      const max = Math.min(buf.length, 44100 * 8 * 60);
      body = new Blob([wavEncode(buf, max)], { type: "audio/wav" });
      name = name.replace(/\.[^.]+$/, "") + ".wav";
    } catch (e) { /* để máy chủ tự đọc (cần ffmpeg cho định dạng nén) */ }
    onStage && onStage("Đang phân tích tempo, giọng…");
    const r = await fetch(this.url("/api/upload"), { method: "POST", headers: { "X-Filename": encodeURIComponent(name) }, body });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Tải lên lỗi");
    if (peaks && !data.peaks) data.peaks = peaks;
    return data;
  },
};

function wavEncode(buf, len) {
  const ch = Math.min(2, buf.numberOfChannels), sr = buf.sampleRate, n = len || buf.length;
  const out = new DataView(new ArrayBuffer(44 + n * ch * 2));
  const w = (o, s) => { for (let i = 0; i < s.length; i++) out.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); out.setUint32(4, 36 + n * ch * 2, true); w(8, "WAVE"); w(12, "fmt ");
  out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, ch, true); out.setUint32(24, sr, true);
  out.setUint32(28, sr * ch * 2, true); out.setUint16(32, ch * 2, true); out.setUint16(34, 16, true); w(36, "data"); out.setUint32(40, n * ch * 2, true);
  const data = [...Array(ch)].map((_, c) => buf.getChannelData(c));
  let o = 44;
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) { const v = Math.max(-1, Math.min(1, data[c][i])); out.setInt16(o, v < 0 ? v * 32768 : v * 32767, true); o += 2; }
  return out.buffer;
}
