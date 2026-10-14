"""Thư mục dữ liệu của Micow (mặc định ~/.micow, đổi bằng biến MICOW_HOME)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # gốc repo / thư mục cài


def home() -> Path:
    p = Path(os.environ.get("MICOW_HOME") or Path.home() / ".micow")
    p.mkdir(parents=True, exist_ok=True)
    return p


def sub(name: str) -> Path:
    p = home() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def library() -> Path:
    """Bài đã tạo: library/<job_id>/{meta.json, mix.wav, stems/...}."""
    return sub("library")


def uploads() -> Path:
    return sub("uploads")


def models() -> Path:
    """Trọng số mô hình đã cài: models/<engine>/<tên>/."""
    return sub("models")


def engines() -> Path:
    """Mã nguồn engine ngoài (ACE-Step 1.5…) được cài vào đây."""
    return sub("engines")


def logs() -> Path:
    return sub("logs")


def web_dir() -> Path:
    return ROOT / "web"
