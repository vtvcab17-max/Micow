# Nhật ký tiến độ Micow (progress.md)

## Current State
**Last Updated:** 2026-10-14
**Phiên bản:** 1.0.0 (nhánh phát triển). Chưa deploy bản web (wrangler.jsonc trỏ `web/`).

## Đã xong
- [x] Suy ngược Suno → kiến trúc 3 tầng (planner → engine → hậu kỳ), tài liệu trong `docs/`.
- [x] Micow Beat: beat 11 thể loại + bài hát có giọng mẫu, clip làm loop/chop/kit, stem/MIDI/LRC.
- [x] Micow-LM: codec RVQ + transformer tự hồi quy, huấn luyện + sinh (đã chạy thử preset tiny trên CPU).
- [x] Engine ACE-Step 1.5 qua REST API (chưa chạy trên GPU thật).
- [x] Máy chủ cục bộ, CLI, giao diện web phong cách Bravin, bộ cài, init.sh, CI.

## 1.1 – Micow Ear + Nhạc CapCut (14/10/2026)
- [x] Micow Ear: nghe nhiều bài, dò phách/ô nhịp, cấu trúc, hook (3 ứng viên), peak + khoảnh khắc drop.
- [x] Cắt CapCut từ bài có sẵn (hook / peak / drop@giây, đúng số giây, vòng lặp, mốc nhịp, dự án Bravin).
- [x] Tạo nhạc CapCut hook-first, drop đúng giây; gộp phong cách nhiều clip; clip kiểu "hook".
- [x] Micow-LM v2: đường cấu trúc theo khung.
- [ ] Huấn luyện BeatTCN + BarMLP trên 221 bài tổng hợp có nhãn (39 bài kiểm tra) – đang chạy, kết quả ở BENCHMARK.md.
- [x] So sánh Suno v6 trung thực (docs/SO_SANH_SUNO_V6.md) – không có điểm tự chấm.

## Tiếp theo
1. Người dùng thả nhạc thật vào trang Nhạc CapCut, bấm "Đúng hook" trên các bài đúng/sai → `micow train ear` để Ear học nhạc thật.
1. Người dùng thử ACE-Step 1.5 trên máy có GPU (feat-005) – gửi `~/.micow/logs/acestep.log` nếu lỗi.
2. Thử bộ cài Windows thật (feat-008).
3. Trang Micow trên website Bravinall (feat-009), nút gửi sang Bravin (feat-010).
4. Huấn luyện Micow-LM trên dữ liệu có quyền (docs/HUAN_LUYEN.md).

## Rủi ro
- Micow Ear mới được đo trên nhạc tổng hợp (có nhãn tuyệt đối); độ chính xác trên nhạc thật chưa đo được vì chưa có bộ nhạc thật có nhãn và giấy phép rõ ràng.
- Giọng mẫu của Micow Beat chỉ ngân nguyên âm (demo); lời hát rõ chữ cần ACE-Step hoặc Micow-LM đã huấn luyện.
- Micow-LM chưa có trọng số tốt: cần GPU và dữ liệu hợp pháp.
- API ACE-Step có thể đổi giữa các bản; Micow gọi theo docs/en/API.md tháng 10/2026.

## Quyết định
- Lõi chỉ cần numpy + scipy (cài nhẹ trên mọi máy); PyTorch tuỳ chọn.
- Máy chủ dùng thư viện chuẩn Python (không FastAPI) để bộ cài đơn giản; trình duyệt giải mã clip để không bắt buộc ffmpeg.
- ACE-Step 1.5 (MIT) là engine giọng hát thật vì giấy phép cho dùng thương mại và chạy được trên GPU phổ thông;
  không đóng gói MusicGen (trọng số CC-BY-NC).
