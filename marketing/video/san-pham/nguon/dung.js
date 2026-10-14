// node dung.js <app> <h|v> <thư mục khung> [xem-thử]
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
const fs = require('fs'); const [app, ori, out, prev] = process.argv.slice(2);
const B = '/home/user/Bravinall/site/assets/brand/', L = '/home/user/micow/marketing/kenh/logo-beta/';
const uri = f => 'data:image/svg+xml;base64,' + fs.readFileSync(f).toString('base64');
const cfg = JSON.parse(fs.readFileSync(__dirname + '/cfg.json'))[app];
cfg.logo = uri(B + app + '.svg'); cfg.beta = uri(L + 'beta-ngang-nen-toi.svg'); cfg.betaLock = uri(L + 'beta-ngang-nen-toi.svg');
cfg.bpm = JSON.parse(fs.readFileSync(__dirname + '/nhac/' + app + '/meta.json')).bpm || 120;
const timing = JSON.parse(fs.readFileSync(__dirname + '/giong/' + app + '.json'));
(async () => {
  const b = await chromium.launch(); const size = ori === 'v' ? { width: 1080, height: 1920 } : { width: 1920, height: 1080 };
  const p = await b.newPage({ viewport: size }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + __dirname + '/khuon.html', { waitUntil: 'networkidle' }); await p.evaluate(() => document.fonts.ready);
  const total = await p.evaluate(([c, t, v]) => setup(c, t, v), [cfg, timing, ori === 'v']);
  fs.mkdirSync(out, { recursive: true });
  const times = prev ? timing.segs.map(s => s.start + Math.min(1.6, (s.end - s.start) * .6)).concat([total - .3]) : Array.from({ length: Math.ceil(total * 30) }, (_, i) => i / 30);
  for (let i = 0; i < times.length; i++) { await p.evaluate(t => draw(t), times[i]); await p.screenshot({ path: `${out}/f${String(i).padStart(4, '0')}.${prev ? 'png' : 'jpg'}`, ...(prev ? {} : { type: 'jpeg', quality: 90 }) }); }
  fs.writeFileSync(out + '/total.txt', String(total));
  console.log(app, ori, times.length, 'khung,', total.toFixed(2), 's,', errs.join('|') || 'không lỗi'); await b.close();
})();
