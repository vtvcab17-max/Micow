// Kiểm thử khói giao diện Micow trong Chromium (Playwright): tạo beat + bài hát như người dùng, chụp màn hình.
// Dùng: node tests/ui_smoke.mjs http://127.0.0.1:5690 [thư_mục_ảnh] [clip.wav]
import { createRequire } from "module";
const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(require("child_process").execSync("npm root -g").toString().trim() + "/playwright"); }
const base = process.argv[2] || "http://127.0.0.1:5690";
const shots = process.argv[3] || "";
const clip = process.argv[4] || "";
const fail = (m) => { console.error("✗ " + m); process.exit(1); };
const browser = await pw.chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 940 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.goto(base + "/#beat");
await page.waitForSelector("#conn.ok", { timeout: 15000 }).catch(() => fail("không kết nối được API"));
await page.waitForSelector("#page-beat [data-tl] .sec", { timeout: 15000 }).catch(() => fail("không hiện bản thiết kế"));
// chọn thể loại Trap, thêm clip, tạo beat
await page.click("#page-beat .gtile:has-text('Trap')");
if (clip) {
  const [fc] = await Promise.all([page.waitForEvent("filechooser"), page.click("#page-beat .drop")]);
  await fc.setFiles(clip);
  await page.waitForSelector("#page-beat .clip select", { timeout: 30000 }).catch(() => fail("clip không phân tích xong"));
}
await page.waitForTimeout(800);
if (shots) await page.screenshot({ path: shots + "/beat.png", fullPage: false });
await page.click("#page-beat [data-go]");
await page.waitForSelector("#page-beat .track", { timeout: 120000 }).catch(() => fail("tạo beat không xong"));
await page.waitForSelector("#player:not([hidden])");
console.log("✓ tạo beat:", await page.textContent("#page-beat .track .tt"));
// bài hát với lời mẫu
await page.goto(base + "/#song");
await page.waitForSelector("#conn.ok");
await page.fill("#page-song textarea.style", "ballad buồn, piano, dàn dây, giọng nữ");
page.once("dialog", (d) => d.accept());
await page.click("#page-song [data-act=sample]");
await page.waitForTimeout(900);
const secs = await page.$$eval("#page-song [data-tl] .sec", (n) => n.map((x) => x.textContent));
if (secs.length < 4) fail("bản thiết kế bài hát thiếu đoạn: " + secs.join(","));
console.log("✓ bản thiết kế:", secs.join(" | "));
if (shots) await page.screenshot({ path: shots + "/song.png" });
await page.click("#page-song [data-go]");
await page.waitForSelector("#page-song .track", { timeout: 180000 }).catch(() => fail("tạo bài hát không xong"));
console.log("✓ tạo bài hát:", await page.textContent("#page-song .track .tt"));
await page.waitForTimeout(600);
if (shots) await page.screenshot({ path: shots + "/song_done.png" });
// tải về: kiểm tra liên kết WAV và LRC hoạt động
await page.click("#page-song .track [aria-label='Tải về']");
const links = await page.$$eval(".menu a", (a) => a.map((x) => x.href));
for (const h of links.filter((h) => /\.(wav|lrc|mid)\b/.test(h) || /zip$/.test(h))) {
  const r = await page.request.get(h);
  if (!r.ok()) fail("tải về lỗi " + h);
}
console.log("✓ tải về:", links.length, "định dạng");
await page.keyboard.press("Escape");
await page.click("body", { position: { x: 5, y: 5 } });
await page.goto(base + "/#library");
await page.waitForSelector("#libList .track");
if (shots) await page.screenshot({ path: shots + "/library.png" });
await page.goto(base + "/#models");
await page.waitForSelector("#engList .mcard");
if (shots) await page.screenshot({ path: shots + "/models.png", fullPage: true });
// điện thoại
const ph = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const pp = await ph.newPage();
await pp.goto(base + "/#song");
await pp.waitForSelector("#conn.ok", { state: "attached" });
await pp.waitForTimeout(700);
const ow = await pp.evaluate(() => document.documentElement.scrollWidth - innerWidth);
if (ow > 1) fail("tràn ngang trên điện thoại: " + ow + "px");
if (shots) await pp.screenshot({ path: shots + "/phone.png" });
if (errors.length) fail("lỗi JS: " + errors.join(" | "));
console.log("✓ không lỗi JS, không tràn ngang trên điện thoại");
await browser.close();
