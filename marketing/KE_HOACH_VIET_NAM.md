# Marketing Micow tại Việt Nam

> Mục tiêu 3 tháng đầu: để **người làm video ngắn và người làm beat ở Việt Nam** biết Micow, cài thử được trong 5 phút, và tự quay lại dùng vì nó giải đúng một việc khó: **nhạc nền có drop rơi đúng giây của video**.

## Mục lục

1. [Định vị trong một câu](#1-định-vị-trong-một-câu)
2. [Ai sẽ dùng Micow](#2-ai-sẽ-dùng-micow)
3. [Nói gì và không nói gì](#3-nói-gì-và-không-nói-gì)
4. [Kênh](#4-kênh)
5. [Lịch 4 tuần ra mắt](#5-lịch-4-tuần-ra-mắt)
6. [20 ý tưởng video ngắn](#6-20-ý-tưởng-video-ngắn)
7. [Kịch bản cho creator review công nghệ](#7-kịch-bản-cho-creator-review-công-nghệ)
8. [Bài đăng mẫu](#8-bài-đăng-mẫu)
9. [Hợp tác creator](#9-hợp-tác-creator)
10. [Đo lường](#10-đo-lường)
11. [Rủi ro và cách tránh](#11-rủi-ro-và-cách-tránh)
12. [Việc cần làm trên sản phẩm trước khi đẩy mạnh](#12-việc-cần-làm-trên-sản-phẩm-trước-khi-đẩy-mạnh)

---

## 1. Định vị trong một câu

**Micow: làm nhạc trên máy bạn. Drop rơi đúng giây của video.**

Ba điểm đỡ cho câu đó, đều có thật trong sản phẩm:

| Điểm | Bằng chứng |
|---|---|
| Nhạc CapCut có **drop đúng giây X**, cắt **đúng số giây**, bắt đầu **đúng đầu ô nhịp** | `docs/BENCHMARK.md`: drop trong ±0,25 giây ở 8/8 bài; sai số độ dài 0 giây (đo trên nhạc tổng hợp có nhãn) |
| **Chạy trên máy, offline, miễn phí (MIT), không giới hạn lượt tải** | Mã nguồn mở, mô hình chạy CPU |
| **Hiểu nhạc Việt**: giai điệu theo thanh điệu, có Vinahouse, Bolero, sáo trúc, đàn tranh | `micow/styles.py`, README |

Video giới thiệu (thư mục `marketing/video/`) chứng minh luôn câu định vị: **nhạc nền của chính video do Micow tạo, drop rơi đúng giây 7**.

## 2. Ai sẽ dùng Micow

| Nhóm | Họ đang khổ vì | Micow giúp gì | Nơi tìm họ |
|---|---|---|---|
| **A. Creator TikTok / Reels / Shorts** (chính) | Nhạc trend dính bản quyền, bị tắt tiếng; cắt nhạc cho khớp cảnh mất thời gian | Nhạc của riêng mình, drop rơi đúng lúc chuyển cảnh, xuất thẳng dự án Bravin 9:16 | TikTok, nhóm Facebook về CapCut, edit video |
| **B. Editor freelance, agency nhỏ** | Khách cần nhạc nền "không bản quyền", đúng 15/30 giây | Cắt đúng số giây, vòng lặp liền mạch, không giới hạn lượt tải | Nhóm Facebook freelancer, Zalo nhóm nghề |
| **C. Beatmaker, producer phòng ngủ** | Cần ý tưởng beat nhanh, muốn stem và MIDI để làm tiếp trong DAW | Beat 12 thể loại, stem, MIDI kèm lời | Nhóm beatmaker, YouTube, Discord nhạc Việt |
| **D. Người làm Vinahouse / remix** | Ít công cụ hiểu thể loại này | Vinahouse 132–140 BPM có build-up + drop, sáo lead | TikTok remix, nhóm DJ |
| **E. Shop online, livestream bán hàng** | Cần nhạc nền an toàn, nhiều bài | Không giới hạn, chạy trên máy | Nhóm bán hàng TikTok Shop |
| **F. Sinh viên, dev quan tâm AI** | Muốn dự án AI mở để học, tự huấn luyện | Mã MIT, Micow Ear, Micow-LM tự huấn luyện | Viblo, Spiderum, J2TEAM, nhóm AI Việt |

**Ưu tiên:** A và D trước (thông điệp "drop đúng giây" ăn ngay), F song song (họ đánh sao GitHub, viết bài, báo lỗi). B, C, E đến tự nhiên từ nội dung của A.

## 3. Nói gì và không nói gì

### Nói
- "Làm nhạc trên máy bạn." / "Drop rơi đúng giây bạn cần."
- "Miễn phí, mã nguồn mở, chạy offline, không giới hạn lượt tải."
- "Micow Ear nghe nhiều bài, chỉ ra hook và đoạn peak."
- Số đo **kèm điều kiện**: "đo trên 39 bài nhạc tổng hợp có nhãn".
- "Nhạc tạo bằng Micow Beat thuộc về bạn."

### Không nói
- ❌ "Hơn Suno", "chất lượng như Suno", "200 điểm" hay bất kỳ điểm tự chấm nào.
- ❌ "Không bao giờ dính bản quyền". Nếu người dùng thả **clip có bản quyền** làm vòng lặp thì bài vẫn có thể dính. Nói đúng: *"Nhạc tạo bằng Micow Beat thuộc về bạn."*
- ❌ "Giọng hát như thật" với Micow Beat (giọng mẫu tổng hợp). Giọng hát thật cần ACE-Step 1.5 và GPU, nói rõ điều kiện đó.
- ❌ Đưa số đo mà bỏ điều kiện "nhạc tổng hợp có nhãn".

### Nếu bị hỏi "so với Suno thế nào?"
> "Về giọng hát và phối khí thì Suno hơn. Micow khác ở quy trình: chạy trên máy bạn, không giới hạn lượt tải, và có công cụ tìm hook, đặt drop đúng giây cho video ngắn mà Suno không có."

(Nguồn so sánh: `docs/SO_SANH_SUNO_V6.md`. Trước khi đăng con số giới hạn lượt tải của Suno, kiểm tra lại trang giá của Suno vì giá có thể đổi.)

## 4. Kênh

| Kênh | Vai trò | Nhịp đăng | Ghi chú |
|---|---|---|---|
| **TikTok** (kênh chính) | Kéo người dùng nhóm A, D | 1 video/ngày trong 4 tuần đầu | Video dọc 9:16, hook 2 giây đầu, nhạc nền luôn tạo bằng Micow |
| **YouTube** | Hướng dẫn cài, dùng sâu; tìm kiếm lâu dài | 1 video dài/tuần + Shorts tái dùng từ TikTok | "Cài Micow trên Windows trong 5 phút" là video quan trọng nhất |
| **Facebook** (trang + nhóm) | Cộng đồng, hỏi đáp | 3 bài/tuần trên trang; đăng vào nhóm khi có video hay | Đọc luật từng nhóm, nhiều nhóm cấm quảng cáo: đăng dạng chia sẻ kinh nghiệm |
| **Threads** | Lan truyền nhanh trong giới creator | Mỗi ngày 1 bài ngắn | Clip 15 giây + một câu |
| **Viblo / Spiderum / blog** | Nhóm F, uy tín kỹ thuật | 2 bài trong tháng đầu | "Tôi suy ngược cách một AI làm nhạc hoạt động", "Dò phách bằng numpy" |
| **GitHub** | Nơi tải, nơi chứng minh | Phát hành có ghi chú, trả lời issue nhanh | README đẹp (đã làm), thêm GIF |
| **Trang Bravinall** | Trang đích | Cập nhật theo phiên bản | `bravinall.vtvcab17.workers.dev/micow` |

**Link đích dùng thống nhất:** `bravinall.vtvcab17.workers.dev/micow` (có nút tải, lệnh cài, bản web).

## 5. Lịch 4 tuần ra mắt

### Tuần 0: chuẩn bị (trước ngày ra mắt)
- [ ] Quay **video cài đặt trên Windows** thật, từ đầu tới lúc ra bài đầu tiên (đây là chỗ người dùng bỏ cuộc nhiều nhất).
- [ ] Đăng video giới thiệu dọc `micow-vi-9x16.mp4` lên TikTok, Reels, Shorts; bản ngang lên YouTube và trang Bravinall.
- [ ] Làm 5 bài nhạc mẫu (Vinahouse, V-Pop, Lo-fi, Bolero, Drill), mỗi bài 15 giây có drop @ 7s, đăng thư viện mẫu.
- [ ] Tạo trang Facebook, kênh TikTok, YouTube cùng tên **Micow**.
- [ ] Ghim bình luận mẫu trả lời 5 câu hỏi hay gặp (máy yếu chạy được không, có trên điện thoại không, có bản quyền không, có giọng hát không, Mac chạy được không).

### Tuần 1: "Drop đúng giây"
- Ngày ra mắt: video giới thiệu + bài Facebook + bài Threads + bài Viblo.
- Mỗi ngày 1 video thử thách: *"Drop rơi đúng giây X"*, đổi X và đổi thể loại.
- Mời 3–5 creator nhỏ (dưới 50 nghìn follow) dùng thử, gửi brief ở mục 9.

### Tuần 2: "Nhạc Việt"
- Chuỗi Vinahouse, Bolero, sáo trúc, đàn tranh. Video "giai điệu theo thanh điệu tiếng Việt": cùng lời, nghe Micow đặt nốt lên xuống theo dấu.
- Livestream 30 phút: làm nhạc nền cho video của người xem, theo yêu cầu.

### Tuần 3: "Micow Ear"
- Thả 5 bài, Micow chỉ ra hook nào mạnh nhất. Video phản ứng: "Micow đoán hook có đúng tai bạn không?"
- Kêu gọi bấm **Đúng hook** để Micow học theo tai người dùng.

### Tuần 4: "Cộng đồng"
- Cuộc thi nhỏ: video dùng nhạc Micow, drop khớp chuyển cảnh nhất. Giải: được đăng lên kênh Micow và trang Bravinall.
- Tổng kết số liệu thật (sao GitHub, lượt xem), đăng công khai.

## 6. 20 ý tưởng video ngắn

Mỗi ý tưởng có **hook 2 giây đầu** (câu nói hoặc chữ trên màn hình):

| # | Hook 2 giây đầu | Nội dung |
|---|---|---|
| 1 | "Drop rơi đúng giây 7. Không phải cắt tay." | Gõ phong cách, chọn 7s, phát cùng video |
| 2 | "Nhạc nền video này do máy tôi tự làm." | Quay màn hình tạo bài, rồi phát video có nhạc đó |
| 3 | "Bị tắt tiếng vì nhạc bản quyền? Thử cái này." | Tạo nhạc riêng thay nhạc trend |
| 4 | "Vinahouse bay phòng, 10 giây ra beat." | Gõ "vinahouse bay phòng, sáo" |
| 5 | "AI làm Bolero nghe thế nào?" | Bolero + đàn tranh |
| 6 | "Cùng một câu lời, nghe giai điệu đi theo dấu." | Minh hoạ thanh điệu |
| 7 | "Thả 5 bài, AI chỉ ra hook nào mạnh nhất." | Micow Ear |
| 8 | "Cắt đúng 15 giây mà không lệch ô nhịp." | So sánh cắt tay và Micow |
| 9 | "Vòng lặp không có tiếng click." | Phát lặp 3 lần |
| 10 | "Làm nhạc mà không cần mạng." | Tắt Wi-Fi rồi tạo bài |
| 11 | "Máy văn phòng cũ có làm nhạc được không?" | Chạy trên CPU thường |
| 12 | "Drill Việt, 808 trượt." | Beat Drill |
| 13 | "Lấy đúng hook bài này làm vòng lặp." | Thả clip của chính bạn |
| 14 | "Xuất stem, mở trong FL Studio." | Cho beatmaker |
| 15 | "Lời bài hát chạy đúng nhịp trong Bravin." | `.lrc` → Bravin |
| 16 | "Mốc nhịp CSV: cắt cảnh theo phách." | Dựng video theo phách |
| 17 | "Mã nguồn mở, tự huấn luyện AI của riêng bạn." | Cho nhóm F |
| 18 | "1 phút, 5 thể loại." | Montage nhanh |
| 19 | "Tôi để AI làm nhạc nền cho 7 ngày video." | Chuỗi thử thách |
| 20 | "Micow không làm được gì? Nói thật." | Giọng hát chưa bằng Suno, cần GPU cho giọng thật. Video trung thực tạo niềm tin |

**Quy tắc chung:** nhạc nền mọi video tạo bằng Micow, góc dưới ghi "Nhạc: Micow · drop @ Xs". Chữ trên màn hình bằng tiếng Việt có dấu.

## 7. Kịch bản cho creator review công nghệ

### Kịch bản A: review ngắn 45–60 giây (TikTok / Reels)

| Thời gian | Hình | Lời |
|---|---|---|
| 0–3s | Mặt creator, phía sau phát video có drop khớp chuyển cảnh | "Nhạc nền video này, drop rơi đúng giây 7, là do máy tôi tự làm. Không mạng, không tốn tiền." |
| 3–10s | Màn hình Micow, gõ "vinahouse sôi động, sáo" | "Đây là Micow, phần mềm làm nhạc mã nguồn mở của người Việt. Gõ phong cách vào…" |
| 10–20s | Chọn độ dài 15 giây, drop @ 7s, bấm Tạo | "…chọn video dài bao nhiêu giây, muốn drop rơi ở giây nào. Bấm tạo." |
| 20–30s | Phát kết quả cùng video | "Đây. Drop rơi đúng chỗ chuyển cảnh. Cắt cũng đúng 15 giây, không lệch nhịp." |
| 30–40s | Thả 3 bài vào Micow Ear | "Nó còn nghe được nhạc của bạn, chỉ ra đoạn hook với đoạn cao trào để cắt làm nhạc nền." |
| 40–50s | Mặt creator | "Điểm trừ: giọng hát chưa bằng Suno, muốn giọng thật thì phải có card đồ hoạ. Nhưng làm nhạc nền video thì đủ dùng, và không giới hạn lượt tải." |
| 50–60s | Chữ: link + lệnh cài | "Link cài ở bình luận ghim. Miễn phí." |

### Kịch bản B: review dài 8–10 phút (YouTube)

1. **Mở (0:00–0:30):** phát 3 video ngắn có nhạc Micow, hỏi "đoán xem nhạc nào AI làm?". Trả lời: cả ba.
2. **Micow là gì (0:30–1:30):** chạy trên máy, mã nguồn mở MIT, thuộc hệ sinh thái Bravinall (Bravin dựng video, Antifact thiết kế, Micron AI).
3. **Cài đặt (1:30–3:00):** Windows: một lệnh PowerShell, hoặc tải ZIP rồi bấm đúp `Cai dat Micow.bat`. Nói rõ cần Python 3.10+, bộ cài tự đề nghị cài nếu thiếu.
4. **Tạo beat (3:00–4:30):** thử 3 thể loại, trong đó có Vinahouse và Bolero. Thả một đoạn nhạc mẫu để Micow học tempo, giọng.
5. **Tạo bài hát (4:30–6:00):** viết lời có thẻ `[Điệp khúc]`, nghe giai điệu theo dấu. Xuất stem, MIDI, `.lrc`.
6. **Nhạc CapCut (6:00–7:30):** Micow Ear, cắt 15 giây, drop @ 7s, vòng lặp, xuất mốc nhịp CSV và dự án Bravin 9:16.
7. **Điểm cộng / điểm trừ (7:30–9:00):**
   - Cộng: miễn phí, offline, riêng tư, không giới hạn lượt tải, drop đúng giây, hiểu nhạc Việt.
   - Trừ: giọng hát và phối khí chưa bằng Suno; giọng thật cần ACE-Step 1.5 và GPU; giao diện hiện chỉ có tiếng Việt; cài đặt qua lệnh có thể lạ với người mới.
8. **Kết (9:00–10:00):** "Ai hợp với Micow": creator cần nhạc nền riêng, người làm Vinahouse/remix, beatmaker cần ý tưởng nhanh. Link ở mô tả.

### Lưu ý gửi creator
- Creator được nói điểm trừ. Review trung thực giúp sản phẩm hơn là khen một chiều.
- Không dùng câu "hơn Suno" hay "không bao giờ dính bản quyền" (lý do ở mục 3).
- Nếu là hợp tác có trả phí hoặc tặng quà, ghi rõ "hợp tác" theo quy định nền tảng.

## 8. Bài đăng mẫu

### Facebook (ngày ra mắt)
> 🎵 **Micow: làm nhạc trên máy bạn.**
>
> Làm video ngắn mà cứ phải cắt nhạc cho khớp chuyển cảnh? Micow làm nhạc nền mới với **drop rơi đúng giây bạn chọn**, cắt đúng số giây, bắt đầu đúng đầu ô nhịp.
>
> ✅ Tạo beat 12 thể loại, có Vinahouse, Bolero, Drill
> ✅ Tạo bài hát từ lời, giai điệu theo thanh điệu tiếng Việt
> ✅ Micow Ear nghe nhạc của bạn, chỉ ra hook và đoạn peak
> ✅ Chạy trên máy, offline, miễn phí, mã nguồn mở, không giới hạn lượt tải
>
> Nhạc nền video dưới đây do chính Micow tạo, drop rơi đúng giây 7.
>
> 👉 Tải về: bravinall.vtvcab17.workers.dev/micow

### Caption TikTok
> Drop rơi đúng giây 7, máy tự làm 🎧 Miễn phí, chạy offline. Link ở bình luận ghim.
> #micow #capcut #lamnhac #vinahouse #beat #aiviet #edit

### Threads
> Tôi để máy tự làm nhạc nền cho video, chọn drop rơi đúng giây 7. Nó làm đúng. Không mạng, không tốn tiền, mã nguồn mở. Tên là Micow.

### Bình luận ghim (mọi video)
> Cài Micow: bravinall.vtvcab17.workers.dev/micow
> ❓ Máy yếu được không? Được, chạy CPU thường.
> ❓ Điện thoại? Chưa, cần máy tính (Windows, macOS, Linux).
> ❓ Có giọng hát không? Có giọng mẫu; giọng thật cần cài thêm ACE-Step và card đồ hoạ.
> ❓ Bản quyền? Nhạc tạo bằng Micow Beat thuộc về bạn.

## 9. Hợp tác creator

**Chọn ai:** creator review công nghệ, hướng dẫn CapCut, làm beat, có 5–100 nghìn follow, tương tác thật. Creator nhỏ hợp hơn creator lớn ở giai đoạn này: rẻ hơn, nói chuyện gần hơn, và dễ nhận lời với sản phẩm miễn phí.

**Brief gửi creator (copy được):**
> Chào bạn, mình là Hà, làm Micow: phần mềm làm nhạc mã nguồn mở chạy trên máy, miễn phí. Điểm mạnh nhất là làm nhạc nền video ngắn có drop rơi đúng giây bạn chọn.
>
> Mình mong bạn dùng thử và review thật lòng, có cả điểm trừ. Gợi ý kịch bản đính kèm, bạn sửa thoải mái theo giọng của bạn.
>
> Xin bạn tránh hai câu "hơn Suno" và "không bao giờ dính bản quyền", vì chưa đúng.
>
> Link: bravinall.vtvcab17.workers.dev/micow

**Đổi lại:** chia sẻ video của creator trên kênh Micow; ghi tên creator trong phần cảm ơn của GitHub; nếu có ngân sách thì trả phí theo thoả thuận.

## 10. Đo lường

| Chỉ số | Xem ở đâu | Mục tiêu tháng 1 (tự đặt lại sau tuần 2) |
|---|---|---|
| Lượt vào trang Micow | Cloudflare Analytics của Worker `bravinall` | Tăng đều theo tuần |
| Sao, lượt clone GitHub | GitHub → Insights → Traffic | Theo dõi tuần |
| Lượt xem, lượt lưu video | TikTok / YouTube Analytics | Video nào giữ người xem quá 50% thì làm thêm biến thể |
| Câu hỏi về cài đặt | Bình luận, issue | Giảm dần; nếu nhiều thì sửa bộ cài trước khi làm nội dung mới |
| Video người dùng tự đăng có nhạc Micow | Tìm hashtag #micow | Có video đầu tiên trong tháng |

**Một con số quan trọng nhất:** số người **cài xong và tạo được bài đầu tiên**. Nếu thấp, việc cần làm là sửa trải nghiệm cài, không phải đăng thêm nội dung.

## 11. Rủi ro và cách tránh

| Rủi ro | Cách tránh |
|---|---|
| Người dùng thả clip có bản quyền làm vòng lặp rồi bị đánh bản quyền | Luôn nói "nhạc tạo bằng Micow Beat thuộc về bạn", kèm nhắc chỉ thả clip bạn có quyền dùng |
| Nền tảng yêu cầu gắn nhãn nội dung tạo bằng AI | Đọc quy định gắn nhãn AI của TikTok, YouTube, Facebook; gắn nhãn khi được yêu cầu |
| Người mới không quen dòng lệnh, bỏ cuộc ở bước cài | Ưu tiên video cài đặt; nhấn mạnh gói ZIP bấm đúp |
| Bị so sánh với Suno và thất vọng về giọng hát | Nói trước điểm trừ (ý tưởng #20); định vị là "nhạc nền video", không phải "thay ca sĩ" |
| Hứa quá mức trong quảng cáo | Mọi con số phải có nguồn trong `docs/BENCHMARK.md` hoặc trang công khai |

## 12. Việc cần làm trên sản phẩm trước khi đẩy mạnh

Đây là các đề xuất, ghi vào `feature_list.json` nếu chủ dự án đồng ý:

1. **Bộ cài một chạm cho Windows** (tệp `.exe`), không cần mở PowerShell. Người dùng nhóm A, E sẽ bỏ cuộc ở dòng lệnh.
2. **Thư viện nhạc mẫu** trong trang web: nghe thử trước khi cài.
3. **Nút "Chia sẻ lên TikTok"**: xuất video 9:16 có sóng nhạc và chữ "Nhạc: Micow", vừa tiện cho người dùng vừa tự quảng bá.
4. **GIF 10 giây** đầu README: gõ phong cách → drop rơi đúng giây.

---

Tài liệu đi kèm: [Kế hoạch thị trường nước ngoài](KE_HOACH_QUOC_TE.md) · [Video giới thiệu](video/)
