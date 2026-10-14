#!/usr/bin/env bash
# Cài Micow trên macOS / Linux.
#   bash scripts/install.sh [--with-torch] [--with-ace]
#     --with-torch  cài PyTorch (để huấn luyện / chạy Micow-LM)
#     --with-ace    cài luôn ACE-Step 1.5 (giọng hát thật, cần GPU ≥ 4 GB hoặc Apple Silicon, ~10 GB)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
WITH_TORCH=0; WITH_ACE=0
for a in "$@"; do
  case "$a" in
    --with-torch) WITH_TORCH=1 ;;
    --with-ace) WITH_ACE=1 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
  esac
done
echo "♪ Cài Micow – hệ sinh thái Bravinall"
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Cần Python 3.10 trở lên."
  echo "  macOS:  brew install python@3.12   (hoặc tải ở https://www.python.org/downloads/)"
  echo "  Ubuntu: sudo apt install python3 python3-venv"
  exit 1
fi
HOME_DIR="${MICOW_HOME:-$HOME/.micow}"
VENV="$HOME_DIR/venv"
mkdir -p "$HOME_DIR"
echo "→ Tạo môi trường Python: $VENV"
"$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install -q -U pip
echo "→ Cài Micow (numpy, scipy)"
"$VENV/bin/python" -m pip install -q -e "$ROOT"
if [ "$WITH_TORCH" = 1 ]; then
  echo "→ Cài PyTorch"
  "$VENV/bin/python" -m pip install -q torch
fi
mkdir -p "$HOME/.local/bin"
ln -sf "$VENV/bin/micow" "$HOME/.local/bin/micow"
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo "  Thêm ~/.local/bin vào PATH:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.profile" ;;
esac
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  (Tuỳ chọn) cài ffmpeg để xuất MP3: brew install ffmpeg  /  sudo apt install ffmpeg"
fi
if [ "$WITH_ACE" = 1 ]; then
  "$VENV/bin/micow" install ace-step
fi
"$VENV/bin/micow" engines || true
echo
echo "✓ Xong. Chạy:  micow serve --open   (hoặc $VENV/bin/micow serve --open)"
