#!/usr/bin/env bash
# Tải + cài Micow bằng một lệnh (macOS / Linux):
#   curl -fsSL https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.sh | bash
#   curl -fsSL …/get.sh | bash -s -- --with-torch      # thêm PyTorch (huấn luyện / Micow-LM)
# Mã nguồn đặt ở ~/.micow/app (chạy lại lệnh để cập nhật); nhạc và mô hình của bạn ở ~/.micow không bị xoá.
set -euo pipefail
REPO="${MICOW_REPO:-vtvcab17-max/Micow}"
REF="${MICOW_REF:-HEAD}"
HOME_DIR="${MICOW_HOME:-$HOME/.micow}"
APP="$HOME_DIR/app"
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "Cần Python 3.10+ (macOS: brew install python@3.12 · Ubuntu: sudo apt install python3 python3-venv)"; exit 1
fi
echo "♪ Tải Micow ($REPO@$REF)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
curl -fsSL "https://github.com/$REPO/archive/$REF.zip" -o "$tmp/micow.zip"
"$PY" -m zipfile -e "$tmp/micow.zip" "$tmp/x"
src="$(find "$tmp/x" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -f "$src/pyproject.toml" ] || { echo "Gói tải về không đúng (thiếu pyproject.toml)"; exit 1; }
mkdir -p "$HOME_DIR"
rm -rf "$APP.new" && mv "$src" "$APP.new"
rm -rf "$APP" && mv "$APP.new" "$APP"
echo "→ Mã nguồn: $APP"
bash "$APP/scripts/install.sh" "$@"
