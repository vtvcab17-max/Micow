# Video giới thiệu từng sản phẩm của Beta

Mỗi sản phẩm hai bản: **9:16** (TikTok, Reels, Shorts) và **16:9** (YouTube, Facebook, web). Dài 27–32 giây, âm lượng −14 LUFS.

| Sản phẩm | Dọc 9:16 | Ngang 16:9 |
|---|---|---|
| Bravin | `bravin-9x16.mp4` | `bravin-16x9.mp4` |
| Antifact | `antifact-9x16.mp4` | `antifact-16x9.mp4` |
| Micron | `micron-9x16.mp4` | `micron-16x9.mp4` |
| Micow | `micow-9x16.mp4` | `micow-16x9.mp4` |

- **Giọng đọc:** ElevenLabs, giọng "Chi" (nữ miền Bắc), model `eleven_v4`. Flow: "Beta – giọng đọc video giới thiệu" trong tài khoản ElevenLabs (mỗi lời thoại có 4 bản để chọn; video dùng bản đầu).
- **Nhạc nền:** tạo bằng Micow (`micow capcut --gen`). Drop rơi đúng lúc tên sản phẩm hoặc cảnh chính xuất hiện; riêng video Micow, drop rơi đúng lúc giọng đọc nói "Drop rơi đúng giây bảy".
- **Phụ đề** gắn sẵn trong video (nhiều người xem video ngắn khi tắt tiếng).
- Bài đăng kèm theo: `../../kenh/bai-seo/BAI_THEO_NEN_TANG.md`. Khi đăng, bật nhãn nội dung AI nếu nền tảng hỏi (giọng đọc và nhạc đều do AI tạo).

## Dựng lại

Thư mục `nguon/`: `khuon.html` (khuôn hình), `cfg.json` (nội dung từng cảnh), `loi/` (lời thoại), `timing.py` (chia thời gian theo giọng đọc), `dung.js` (chụp khung hình), `dung-tat-ca.sh` (dựng và trộn tiếng cả 8 video). Cần đặt giọng đọc ở `giong/<app>.mp3` và nhạc ở `nhac/<app>/mix.wav` cạnh các tệp này.
