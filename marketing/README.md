# Marketing Micow

| Tài liệu | Nội dung |
|---|---|
| [KE_HOACH_VIET_NAM.md](KE_HOACH_VIET_NAM.md) | Kế hoạch thị trường Việt Nam: định vị, nhóm người dùng, kênh, lịch 4 tuần, 20 ý tưởng video ngắn, kịch bản cho creator, bài đăng mẫu |
| [KE_HOACH_QUOC_TE.md](KE_HOACH_QUOC_TE.md) | Kế hoạch thị trường nước ngoài: điều kiện trước khi ra mắt (giao diện tiếng Anh), Show HN, Reddit, Product Hunt, kịch bản và bài đăng tiếng Anh |
| [kenh/](kenh/HUONG_DAN_TAO_KENH.md) | Bộ dựng kênh **Beta** (công ty mẹ của Bravinall): ảnh đại diện, ảnh bìa, tên, tiểu sử, bài đầu tiên cho YouTube, TikTok, Facebook, Instagram, Threads, X |
| [kenh/bai-seo/](kenh/bai-seo/) | Bài chuẩn SEO theo từng nền tảng (YouTube, TikTok, Facebook, Instagram, Threads, X) và bài blog, giọng viết tự nhiên |
| [video/](video/) | Video giới thiệu 30 giây, tiếng Việt và tiếng Anh, bản ngang 16:9 và dọc 9:16 |

## Video giới thiệu

| Tệp | Dùng cho |
|---|---|
| `video/micow-vi-16x9.mp4` | YouTube, trang Bravinall, Facebook |
| `video/micow-vi-9x16.mp4` | TikTok, Reels, Shorts |
| `video/micow-en-16x9.mp4` | YouTube, Product Hunt, GitHub |
| `video/micow-en-9x16.mp4` | TikTok, Reels, Shorts tiếng Anh |

**Nhạc nền của cả bốn video do chính Micow tạo**, drop rơi đúng giây 7:

```bash
micow capcut --gen -s "vinahouse sôi động, sáo" -d 30 --peak-at 7 --seed 7   # bản tiếng Việt
micow capcut --gen -s "edm hiện đại, supersaw" -d 30 --peak-at 7 --seed 7    # bản tiếng Anh
```

Mỗi cảnh trong video dài đúng một số ô nhịp (1,75 giây ở 137 BPM), nên chuyển cảnh khớp phách.

### Sửa chữ rồi dựng lại

Video là một trang HTML vẽ theo thời gian (`video/nguon/micow-promo.html`). Chữ cho hai ngôn ngữ nằm trong biến `T` ở đầu phần `<script>`.

```bash
cd marketing/video/nguon
# xem thử 10 khung: node render.js vi h xem-thu 1
node render.js vi h khung            # 900 khung, 30 fps, 30 giây (v = bản dọc, en = tiếng Anh)
ffmpeg -framerate 30 -i khung/f%04d.jpg -i <thư mục nhạc>/mix.wav \
  -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart micow-vi-16x9.mp4
```

Cần Node.js, Playwright (Chromium) và ffmpeg. Nếu Playwright cài toàn cục: `PLAYWRIGHT=$(npm root -g)/playwright node render.js …`.

## Quy tắc chung khi làm nội dung

- Không viết "hơn Suno", "200 điểm" hay điểm tự chấm.
- Số đo luôn kèm điều kiện "đo trên 39 bài nhạc tổng hợp có nhãn" (nguồn `docs/BENCHMARK.md`).
- Không hứa "không bao giờ dính bản quyền". Nói đúng: nhạc tạo bằng Micow Beat thuộc về bạn.
- Màu vàng `#f2c14e` chỉ dùng cho yếu tố thời gian (đầu phát, "drop @ 7s").
