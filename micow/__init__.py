"""Micow: mô hình làm nhạc chạy trên máy của bạn (hệ sinh thái Bravinall).

Hai chế độ chính:
  1. Tạo beat (nhạc không lời) từ phong cách + các đoạn nhạc mẫu đưa vào.
  2. Tạo bài hát hoàn chỉnh từ lời (lyric) + phong cách (style) + đoạn nhạc mẫu.

Kiến trúc ba tầng (xem docs/KIEN_TRUC.md):
  Planner (micow.planner)  ->  Engine sinh âm thanh (micow.engines)  ->  Hậu kỳ (micow.dsp.master)
"""

__version__ = "1.1.0"
APP_NAME = "Micow"
DEFAULT_PORT = 5690
