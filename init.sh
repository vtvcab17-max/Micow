#!/usr/bin/env bash
# Micow – khởi động phiên & cổng kiểm chứng.
#   ./init.sh          kiểm tra tĩnh + unittest + kiểm thử giao diện Chromium (nếu có Playwright)
#   ./init.sh --quick  kiểm tra tĩnh + unittest
# Thoát mã khác 0 nếu có lỗi. Chưa đạt thì KHÔNG được báo "xong".
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
echo "=== Micow: khởi động phiên ==="
echo "Phiên bản: $($PY -c 'import micow; print(micow.__version__)')"
command -v git >/dev/null && git log --oneline -3 2>/dev/null || true

echo
echo "=== 1/3 Kiểm tra tĩnh ==="
$PY -m compileall -q micow tests >/dev/null && echo "✓ cú pháp Python"
for f in web/js/*.js; do node --check "$f"; done && echo "✓ cú pháp JS ($(ls web/js/*.js | wc -l) tệp)"
$PY - <<'PYEOF'
import json, re, sys, pathlib
root = pathlib.Path(".")
json.load(open("web/manifest.webmanifest", encoding="utf-8"))
v_py = __import__("micow").__version__
v_html = re.search(r'name="micow-version" content="([^"]+)"', open("web/index.html", encoding="utf-8").read()).group(1)
v_toml = re.search(r'^version = "([^"]+)"', open("pyproject.toml", encoding="utf-8").read(), re.M).group(1)
if not (v_py == v_html == v_toml):
    sys.exit(f"✗ phiên bản lệch: micow {v_py}, index.html {v_html}, pyproject {v_toml}")
html = open("web/index.html", encoding="utf-8").read()
for ref in re.findall(r'(?:src|href)="((?:css|js|icons|fonts)/[^"]+)"', html):
    if not (root / "web" / ref).exists():
        sys.exit(f"✗ index.html tham chiếu tệp không tồn tại: {ref}")
big = [p for p in (root / "web").rglob("*") if p.is_file() and p.stat().st_size > 25 * 2**20]
if big:
    sys.exit(f"✗ tệp > 25 MiB trong web/ (Cloudflare từ chối): {big}")
if open("scripts/install.ps1", "rb").read(3) != b"\xef\xbb\xbf":
    sys.exit("✗ scripts/install.ps1 phải lưu UTF-8 có BOM (Windows PowerShell 5.1)")
for p in list(root.rglob("*.py")) + list(root.rglob("*.js")) + list(root.rglob("*.md")):
    if ".git" in p.parts or "node_modules" in p.parts:
        continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"(sk-ant-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,})", t):
        sys.exit(f"✗ có vẻ lộ khoá bí mật trong {p}")
print(f"✓ phiên bản {v_py} khớp, tham chiếu index.html đủ, không tệp > 25 MiB, không lộ khoá")
PYEOF

echo
echo "=== 2/3 Unittest (lõi, máy chủ, mô hình nếu có PyTorch) ==="
$PY -m unittest discover -s tests -q

if [ "${1:-}" = "--quick" ]; then
  echo; echo "Bỏ qua kiểm thử giao diện (--quick). Trước khi báo xong phải chạy ./init.sh đầy đủ."
else
  echo
  echo "=== 3/3 Kiểm thử giao diện trong Chromium ==="
  if node -e 'require("playwright")' 2>/dev/null || [ -d "$(npm root -g 2>/dev/null)/playwright" ]; then
    export MICOW_HOME="$(mktemp -d)"
    PORT=5697
    $PY -m micow serve --port $PORT >"$MICOW_HOME/server.log" 2>&1 &
    echo $! > "$MICOW_HOME/pid"
    trap 'kill $(cat "$MICOW_HOME/pid") 2>/dev/null || true; rm -rf "$MICOW_HOME"' EXIT
    for i in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.5; done
    $PY -c "from micow.planner import make_blueprint; from micow.dsp.render import render; from micow.audio_io import write_wav; write_wav('$MICOW_HOME/clip.wav', render(make_blueprint('beat', 'lofi', duration=12, seed=1)).mix)"
    node tests/ui_smoke.mjs "http://127.0.0.1:$PORT" "" "$MICOW_HOME/clip.wav"
  else
    echo "⚠ Chưa có Playwright (npm i -g playwright) – bỏ qua kiểm thử giao diện"
  fi
fi
echo
echo "=== Kiểm chứng xong: mọi kiểm tra đạt ==="
