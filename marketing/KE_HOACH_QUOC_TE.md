# Marketing Micow ở thị trường nước ngoài

> Thị trường nước ngoài khác Việt Nam ở một điểm lớn: **người dùng sớm nhất sẽ là cộng đồng mã nguồn mở và "local AI"**, không phải creator TikTok. Họ quan tâm "chạy trên máy, không gửi dữ liệu đi, mã MIT". Creator đến sau, khi đã có bằng chứng và giao diện tiếng Anh.

## Mục lục

1. [Điều kiện bắt buộc trước khi ra mắt](#1-điều-kiện-bắt-buộc-trước-khi-ra-mắt)
2. [Định vị](#2-định-vị)
3. [Ai sẽ dùng Micow](#3-ai-sẽ-dùng-micow)
4. [Nói gì và không nói gì](#4-nói-gì-và-không-nói-gì)
5. [Kênh và thứ tự ra mắt](#5-kênh-và-thứ-tự-ra-mắt)
6. [Lịch 6 tuần](#6-lịch-6-tuần)
7. [Bài đăng mẫu bằng tiếng Anh](#7-bài-đăng-mẫu-bằng-tiếng-anh)
8. [Kịch bản cho creator review công nghệ (tiếng Anh)](#8-kịch-bản-cho-creator-review-công-nghệ-tiếng-anh)
9. [Đo lường](#9-đo-lường)
10. [Rủi ro](#10-rủi-ro)

---

## 1. Điều kiện bắt buộc trước khi ra mắt

> [!IMPORTANT]
> Hiện tại **giao diện, README và tài liệu của Micow chỉ có tiếng Việt** (`web/index.html` là `lang="vi"`, không có bộ đa ngôn ngữ). Ra mắt quốc tế lúc này sẽ mất phần lớn người xem ở bước đầu tiên.

| # | Việc | Vì sao |
|---|---|---|
| 1 | **Giao diện web có tiếng Anh** (nút chuyển Việt / English) | Người dùng nước ngoài không đọc được nút |
| 2 | **README tiếng Anh** (`README.en.md`, link ở đầu README tiếng Việt) | GitHub là trang đích chính ở thị trường này |
| 3 | **Thông báo dòng lệnh** và bộ cài có tiếng Anh | Lỗi cài đặt bằng tiếng Việt thì không ai tự sửa được |
| 4 | **Trang giới thiệu tiếng Anh** trên Bravinall (`/micow/en` hoặc bản tiếng Anh của `micow.html`) | Link chia sẻ cần mở ra trang đọc được |
| 5 | **Kiểm thử phong cách nhập bằng tiếng Anh** | Đã thử: "dark trap, heavy 808, bells" ra Trap, "uplifting EDM, supersaw" ra EDM. Nên thử thêm nhiều cách gõ khác trước khi ra mắt |
| 6 | **Tên lệnh, thư mục không dấu** đã đúng; chỉ cần thêm hướng dẫn tiếng Anh cho `Cai dat Micow.bat` | Tên tệp tiếng Việt không dấu khó hiểu với người nước ngoài |

Video giới thiệu tiếng Anh đã có sẵn: `marketing/video/micow-en-16x9.mp4` và `micow-en-9x16.mp4`.

## 2. Định vị

**English one-liner:**
> **Micow: an open-source music generator that runs on your own machine. Make beats, full songs, and short-video tracks where the drop lands on the exact second.**

**Câu ngắn (tagline):**
> *Make music on your own machine.*

**Ba điểm khác biệt, đều kiểm chứng được:**

| Điểm | Bằng chứng |
|---|---|
| **Local-first**: offline, riêng tư, không giới hạn lượt tải, MIT | Mã nguồn công khai |
| **Công cụ cho video ngắn**: drop đúng giây X, cắt đúng số giây từ đầu ô nhịp, vòng lặp liền mạch, mốc nhịp CSV | `docs/BENCHMARK.md` (đo trên 39 bài nhạc tổng hợp có nhãn) |
| **Mở cho người muốn tự huấn luyện**: Micow Ear học theo nhãn bạn bấm; Micow-LM tự huấn luyện trên dữ liệu bạn có quyền dùng | `docs/HUAN_LUYEN.md` |

**Điểm riêng có thể kể như một câu chuyện:** Micow sinh ra ở Việt Nam, giai điệu theo thanh điệu tiếng Việt, có Vinahouse và Bolero. Với khán giả nước ngoài, đây là chi tiết thú vị ("a music model that understands a tonal language"), không phải tính năng chính.

## 3. Ai sẽ dùng Micow

| Thứ tự | Nhóm | Họ cần gì | Nơi tìm họ |
|---|---|---|---|
| 1 | **Cộng đồng local AI / self-hosted** | Công cụ AI chạy trên máy, không thuê bao | Hacker News, r/selfhosted, r/LocalLLaMA, r/opensource |
| 2 | **Lập trình viên âm nhạc, người làm audio ML** | Mã đọc được, dò phách, cấu trúc bài, huấn luyện | GitHub, r/audioengineering, Discord ACE-Step, Hugging Face |
| 3 | **Creator video ngắn** | Nhạc nền riêng, drop khớp chuyển cảnh, không thuê bao | YouTube (hướng dẫn edit), TikTok, Reels |
| 4 | **Beatmaker, producer phòng ngủ** | Ý tưởng nhanh, stem, MIDI | YouTube, r/WeAreTheMusicMakers (luật quảng bá rất chặt), forum KVR |
| 5 | **Game dev indie** | Nhạc nền lặp liền mạch, không thuê bao | r/gamedev, itch.io |

## 4. Nói gì và không nói gì

### Nói
- "Runs on your own machine. Offline. MIT-licensed. Unlimited downloads."
- "The drop lands on the exact second of your video."
- "Micow Ear listens to your tracks and finds the hook and the peak."
- Số đo **luôn kèm điều kiện**: *"measured on 39 labeled synthetic tracks (see BENCHMARK.md)"*.

### Không nói
- ❌ "Better than Suno", "Suno killer", "Suno-quality vocals", hay điểm tự chấm.
- ❌ Dùng tên, logo Suno trong quảng cáo, ảnh bìa, tiêu đề. Nhãn hiệu của bên khác dễ bị khiếu nại ở thị trường Mỹ, châu Âu.
- ❌ "Royalty-free guaranteed". Nói đúng: *"Music you generate with Micow Beat is yours."* Nếu người dùng thả clip có bản quyền làm vòng lặp thì không còn đúng.
- ❌ Số đo không kèm "on synthetic labeled tracks".

### Nếu bị hỏi "how does it compare to Suno/Udio?"
> "For vocal realism and mixing, Suno is clearly ahead. Micow is different in workflow: it runs locally with no download caps, and it has tools for short-video music (hook/peak finder, drop on an exact second, bar-aligned cuts) that hosted generators don't offer. We keep an honest comparison in docs/SO_SANH_SUNO_V6.md."

(Kiểm tra lại trang giá của đối thủ trước khi nêu con số cụ thể. Tài liệu so sánh hiện bằng tiếng Việt, cần dịch khi có README tiếng Anh.)

## 5. Kênh và thứ tự ra mắt

Thứ tự quan trọng: **cộng đồng kỹ thuật trước** (họ chịu được bản đầu còn thô, góp ý, đánh sao), **creator sau**.

| Giai đoạn | Kênh | Định dạng | Ghi chú |
|---|---|---|---|
| 1 | **Hacker News: Show HN** | Bài "Show HN" + link GitHub | Chỉ đăng khi người đọc **tự cài thử được**. Chủ dự án có mặt trả lời bình luận suốt ngày đầu |
| 1 | **Reddit** r/selfhosted, r/opensource, r/LocalLLaMA | Bài kể chuyện + video ngắn | Đọc luật từng subreddit; nhiều nơi giới hạn tự quảng bá |
| 2 | **Product Hunt** | Trang sản phẩm, video, ảnh | Đăng sau HN/Reddit, khi đã sửa các lỗi cài đặt họ báo |
| 2 | **GitHub** | Release có ghi chú tiếng Anh, topic `music-generation`, `local-ai`, `audio` | Thêm GIF, video ở đầu README tiếng Anh |
| 2 | **Hugging Face** | Trang model cho trọng số Micow Ear (nếu chủ dự án muốn chia sẻ), Space demo | Space có thể chạy Micow Beat trên CPU: người xem nghe thử không cần cài |
| 3 | **YouTube** | Video dài "local AI music generator for short videos", Shorts từ video 9:16 | Tìm kiếm lâu dài |
| 3 | **TikTok / Reels** (tiếng Anh) | Thử thách "drop on second X" | Tái dùng ý tưởng của kế hoạch Việt Nam |
| 3 | **Creator review công nghệ** | Kịch bản ở mục 8 | Ưu tiên creator về local AI, open source, edit video |
| 3 | **X / Bluesky / Mastodon** | Thread kỹ thuật, clip ngắn | Cộng đồng âm nhạc và audio ML có mặt ở cả ba |

## 6. Lịch 6 tuần

| Tuần | Việc |
|---|---|
| **0–2** | Làm xong 6 điều kiện ở mục 1. Thử cài trên máy Windows, macOS, Linux sạch bằng hướng dẫn tiếng Anh. |
| **3** | Show HN (ngày thường, buổi sáng giờ Mỹ). Đăng r/selfhosted, r/opensource trong cùng tuần nhưng khác ngày. Ghi lại mọi lỗi cài đặt người dùng báo. |
| **4** | Sửa lỗi từ tuần 3, phát hành bản vá có ghi chú. Đăng bài kỹ thuật "How I built a beat tracker in numpy" hoặc "Reverse-engineering how AI music generators work" (từ `docs/SUNO_SUY_NGUOC.md`, viết lại không dùng tên thương mại ở tiêu đề). |
| **5** | Product Hunt. Mời 5–10 creator nhỏ (local AI, open source, edit video) dùng thử. |
| **6** | YouTube video dài, chuỗi Shorts / TikTok "drop on second X". Tổng kết số liệu thật, đăng công khai. |

## 7. Bài đăng mẫu bằng tiếng Anh

### Show HN

**Title:**
> Show HN: Micow – open-source music generator that runs locally, with drops on the exact second

**Body:**
> Hi HN, I'm Ha from Hanoi. Micow is a music generator that runs on your own machine (CPU is enough; MIT-licensed).
>
> It started from a narrow problem: short-video editors spend a lot of time cutting music so the drop hits a scene change. Micow can generate a new track where the drop lands on a second you choose, cut existing tracks to an exact length starting on a bar, and make seamless loops. A small model (Micow Ear: a beat tracker plus a bar classifier, numpy only) listens to your tracks and points out the hook and the peak.
>
> It also makes beats in 12 genres and full songs from lyrics. The built-in engine is a synthesizer with placeholder vocals; for real vocals you can install ACE-Step 1.5 (needs a GPU). Vocal quality is well behind hosted services like Suno, and I'd rather say that up front.
>
> Numbers are in docs/BENCHMARK.md, measured on 39 labeled synthetic tracks (not real-world music yet): beat tracking 99%, hook inside the true chorus/drop 95%, drop within ±0.25 s on 8/8 generated tracks.
>
> Code: github.com/vtvcab17-max/Micow
> I'd love feedback on the install experience and on the beat tracker.

### Reddit (r/selfhosted)

**Title:**
> I built a local, offline music generator for short-video creators (MIT, runs on CPU)

**Body:**
> No subscription, no upload, no download caps. Micow runs on your machine and serves a web UI on 127.0.0.1. It generates beats and songs, and its main trick is short-video music: pick a length and a second for the drop, and it builds the track around that. It can also analyze your own tracks and find the hook.
>
> Honest limits: vocals are basic unless you add ACE-Step (GPU). The UI is [English now / Vietnamese only for now].
>
> [video 9:16] · GitHub link in comments

### Product Hunt
- **Name:** Micow
- **Tagline (≤60 ký tự):** *Local music generator with drops on the exact second*
- **Mô tả:** *Free, open-source, offline. Make beats, songs and short-video tracks on your own machine. Find the hook in your tracks, cut to the exact second, loop seamlessly.*
- **First comment:** kể câu chuyện (người làm ở Hà Nội, vấn đề cắt nhạc cho video), nói rõ điểm trừ về giọng hát, mời góp ý.

### Thread X / Bluesky
> 1/ I made a music generator that runs entirely on my laptop. The soundtrack of this video came out of it, and the drop lands exactly at 7.0s. 🧵
>
> 2/ Why: cutting music so the drop hits your scene change is tedious. Micow plans the track around the second you pick.
>
> 3/ It also listens to your tracks and finds the hook and the peak (small numpy model, no GPU).
>
> 4/ Limits: vocals are basic unless you add ACE-Step (GPU). Not a replacement for a singer.
>
> 5/ Free, MIT, offline. github.com/vtvcab17-max/Micow

## 8. Kịch bản cho creator review công nghệ (tiếng Anh)

### Kịch bản A: Short 45–60 giây

| Time | Visual | Voiceover |
|---|---|---|
| 0–3s | Video playing, the drop hits a scene change | "The drop in this video lands exactly at seven seconds. My laptop made this track. Offline. For free." |
| 3–12s | Micow UI, typing "uplifting EDM, supersaw" | "This is Micow, an open-source music generator. Type a style…" |
| 12–20s | Set length 15s, drop at 7s, click Generate | "…pick the length and the second you want the drop. Generate." |
| 20–30s | Play result over the edit | "There it is. Cut to exactly fifteen seconds, starting on the beat." |
| 30–40s | Drop 3 songs into Micow Ear | "It can also listen to your own tracks and show you the hook and the peak." |
| 40–52s | Face to camera | "The catch: vocals aren't close to Suno. Real vocals need a GPU add-on. But for background music, no caps, no subscription." |
| 52–60s | Text: GitHub link | "Link in the description. It's MIT-licensed." |

### Kịch bản B: Video dài 8–10 phút
1. **Hook (0:00–0:30):** ba đoạn video, hỏi người xem đoán nhạc nào do AI chạy trên laptop tạo.
2. **What is Micow (0:30–1:30):** local-first, MIT, ba engine (Micow Beat, ACE-Step 1.5 tuỳ chọn, Micow-LM tự huấn luyện).
3. **Install (1:30–3:00):** lệnh một dòng cho macOS/Linux và Windows; yêu cầu Python 3.10+.
4. **Beats & songs (3:00–5:30):** 3 thể loại, thả clip tham chiếu, xuất stem, MIDI, `.lrc`.
5. **Short-video workflow (5:30–7:30):** Micow Ear, cắt 15 giây, drop @ 7s, vòng lặp, mốc nhịp CSV.
6. **Pros / cons (7:30–9:00):**
   - Pros: free, offline, private, unlimited, exact-second drops, open code you can train.
   - Cons: vocals and mixing behind hosted services; real vocals need a GPU; install is via command line.
7. **Who it's for (9:00–10:00):** short-video creators, self-hosters, devs curious about audio ML.

### Lưu ý gửi creator
- Cho phép và khuyến khích nói điểm trừ.
- Không dùng "better than Suno", không dùng logo/tên Suno trên thumbnail.
- Hợp tác có trả phí hoặc quà tặng phải công bố theo quy định (FTC ở Mỹ, ASA ở Anh, và quy định của từng nền tảng).

## 9. Đo lường

| Chỉ số | Xem ở đâu | Dùng để làm gì |
|---|---|---|
| Sao, traffic nguồn giới thiệu | GitHub Insights → Traffic | Biết kênh nào đưa người tới |
| Issue về cài đặt (tiếng Anh) | GitHub Issues | Nếu nhiều: dừng quảng bá, sửa bộ cài |
| Lượt vào trang tiếng Anh | Cloudflare Analytics | So sánh với trang tiếng Việt |
| Lượt xem, tỉ lệ xem hết video | YouTube / TikTok Analytics | Chọn biến thể để làm tiếp |
| Bình luận HN / Reddit | Đọc tay | Tìm câu hỏi lặp lại, đưa vào FAQ |

**Chỉ số quan trọng nhất** giống ở Việt Nam: số người **cài xong và tạo được bài đầu tiên**.

## 10. Rủi ro

| Rủi ro | Cách tránh |
|---|---|
| Ra mắt khi giao diện còn tiếng Việt | Không đăng HN / Product Hunt trước khi xong mục 1 |
| Bị so sánh chất lượng với dịch vụ trả phí | Nói điểm trừ trước; định vị "short-video workflow, local" |
| Khiếu nại nhãn hiệu vì nhắc tên đối thủ | Chỉ nhắc trong phần so sánh trung thực, không ở tiêu đề, ảnh bìa, quảng cáo |
| Tranh cãi về dữ liệu huấn luyện AI âm nhạc | Nói rõ: Micow Ear học từ nhạc tổng hợp do chính Micow dựng (`micow train ear`), cộng nhãn "Đúng hook" người dùng tự bấm trên máy họ; Micow-LM chỉ huấn luyện trên dữ liệu người dùng có quyền dùng; không dùng mã, trọng số, âm thanh của Suno |
| Nền tảng yêu cầu gắn nhãn nội dung AI | Hướng dẫn người dùng đọc và tuân theo quy định gắn nhãn AI của từng nền tảng |
| Ngày ra mắt quá nhiều người cài, lỗi lộ ra cùng lúc | Thử cài trên máy sạch trước; chủ dự án trực trả lời ngày đầu |

---

Tài liệu đi kèm: [Kế hoạch Việt Nam](KE_HOACH_VIET_NAM.md) · [Video giới thiệu](video/)
