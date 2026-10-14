// node render.js <lang> <h|v> <outdir> [preview]
const { chromium } = require(process.env.PLAYWRIGHT || 'playwright');
const [lang, ori, out, prev] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  const size = ori === 'v' ? { width: 1080, height: 1920 } : { width: 1920, height: 1080 };
  const p = await b.newPage({ viewport: size }); const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + __dirname + '/micow-promo.html?lang=' + lang + (ori === 'v' ? '&v=1' : ''), { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  require('fs').mkdirSync(out, { recursive: true });
  const times = prev ? [1.5, 5, 7.1, 8.5, 12.5, 16, 19.6, 22.5, 26, 29] : Array.from({ length: 900 }, (_, i) => i / 30);
  for (let i = 0; i < times.length; i++) {
    await p.evaluate(t => draw(t), times[i]);
    await p.screenshot({ path: `${out}/f${String(i).padStart(4, '0')}.${prev ? 'png' : 'jpg'}`, ...(prev ? {} : { type: 'jpeg', quality: 92 }) });
  }
  console.log(lang, ori, times.length, 'frames', errs.join('|') || 'no errors');
  await b.close();
})();
