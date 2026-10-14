# Suy ngược mô hình làm nhạc của Suno

Tài liệu này ghi lại những gì **công khai** về cách Suno làm nhạc, phần nào là **suy luận**, và Micow
lấy ý tưởng nào từ đó. Suno không công bố mã hay trọng số của mô hình làm nhạc; Micow không dùng
bất cứ thứ gì của Suno ngoài các ý tưởng kiến trúc đã được nói công khai.

> Mức độ chắc chắn: **[Đã công bố]** do Suno nói / mã nguồn mở của Suno · **[Suy luận]** suy ra từ
> sản phẩm và các mô hình mở tương tự · **[Chưa kiểm chứng]** tin đồn, phân tích của bên thứ ba.

## 1. Những gì Suno đã nói ra

### Bark – mô hình mã nguồn mở của chính Suno (2023, MIT) [Đã công bố]
Trước khi làm nhạc, Suno phát hành Bark (văn bản → giọng nói / âm thanh). Bark là "tổ tiên" công khai duy nhất:

```
văn bản ──GPT 1──▶ token ngữ nghĩa ──GPT 2──▶ token âm học "thô" (2 sổ mã đầu của EnCodec)
        ──GPT 3 (không nhân quả)──▶ token âm học "mịn" (6 sổ mã còn lại) ──EnCodec decoder──▶ sóng âm 24 kHz
```

* Cả ba tầng đều là transformer kiểu GPT dựng trên nanoGPT.
* Âm thanh được biến thành **token rời rạc** bằng codec thần kinh (EnCodec, lượng tử hoá vector dư – RVQ).
* Bark không dùng âm vị: văn bản đi thẳng vào mô hình.

### CEO Mikey Shulman (podcast Latent Space) [Đã công bố]
* Suno **thích transformer** hơn diffusion, mô hình tự hồi quy: "dự đoán mẩu âm thanh nhỏ tiếp theo".
* Phần họ đầu tư nhiều nhất là **cách token hoá âm thanh**; chi tiết là bí mật.
* Cố gắng **ít giả định sẵn nhất có thể** (không mã hoá âm vị, làm "end-to-end").
* Dữ liệu: chỉ nhạc là không đủ, **giọng nói/âm thanh không phải nhạc cũng giúp** mô hình hay hơn.
* Mô hình "vẫn khá nhỏ", mở rộng giống transformer văn bản; họ quan tâm **số token sinh mỗi giây** (để phát trực tuyến).
* Hơn nửa người dùng dùng chế độ chuyên sâu: tự sửa lời, ngắt dòng, ad-lib.
* Đánh giá bằng tai người (độ trung thực âm thanh, chất lượng bài, khả năng điều khiển).

### Sản phẩm cho thấy gì [Đã công bố – tính năng]
| Tính năng Suno | Lộ ra điều gì về mô hình |
|---|---|
| "Custom": ô **Lyrics** + ô **Style of Music** | Hai luồng điều kiện riêng: lời và mô tả phong cách |
| Thẻ trong ngoặc vuông `[Verse]`, `[Chorus]`, `[Bridge]`, `[Instrumental]`… | Cấu trúc bài nằm **ngay trong văn bản lời**, mô hình tự học ý nghĩa thẻ |
| **Extend / Continue from** | Mô hình tự hồi quy: lấy phần đã có làm ngữ cảnh rồi sinh tiếp |
| **Upload audio** → extend, cover, thêm giọng / thêm nhạc nền | Điều kiện bằng token của clip người dùng (nối tiếp hoặc tham chiếu) |
| **Persona** | Một "dấu vân" giọng/phong cách lấy từ một bài làm điều kiện cho bài khác |
| **Replace section** | Sinh lại một khoảng giữa bài khi biết hai đầu (inpainting) |
| **Stems** | Tách nguồn (có thể là mô hình tách riêng) |
| Bài dài tới vài phút | Có cơ chế cửa sổ trượt / nhiều đoạn nối nhau |

## 2. Phần còn tranh cãi [Chưa kiểm chứng]
* Có dùng **diffusion** hay không: một số bài báo nói Suno "lai transformer + diffusion", diễn đàn chuyên môn lại
  cho rằng bản mới làm việc trên lưới latent liên tục. CEO chỉ nói họ *thích* transformer.
* Bộ mã hoá văn bản cụ thể (có bài đoán NV-Embed) – không có nguồn chính thức.
* Kích thước mô hình, lượng dữ liệu – không công bố. Năm 2024 các hãng đĩa lớn đã kiện Suno về dữ liệu
  huấn luyện, nên câu hỏi dữ liệu là then chốt cho bất kỳ ai muốn làm lại.

## 3. Kiến trúc suy ra [Suy luận]

```
          ┌──────────────── HIỂU YÊU CẦU ────────────────┐
 Style ──▶│ chuẩn hoá phong cách, có thể có LLM viết lại │──┐
 Lời   ──▶│ lời + thẻ đoạn giữ nguyên dạng văn bản        │  │ token văn bản
 Clip  ──▶│ codec → token của clip                        │  │ + token clip
          └───────────────────────────────────────────────┘  ▼
          ┌──────────── SINH TOKEN ÂM THANH ──────────────────────────────┐
          │ transformer tự hồi quy (kiểu GPT/Bark) trên token codec,       │
          │ điều kiện = [phong cách][lời][clip]; sinh theo cửa sổ trượt    │
          │ → extend/continue chỉ là "ép" token đã biết rồi sinh tiếp       │
          └────────────────────────────────────────────────────────────────┘
          ┌──────────── GIẢI MÃ / LÀM ĐẸP ────────────────┐
          │ codec decoder (có thể + diffusion nâng chất)  │──▶ stereo 44,1–48 kHz
          │ tách stem, master                             │
          └───────────────────────────────────────────────┘
```

Các mô hình mở năm 2025–2026 xác nhận hướng này khả thi:
* **YuE / YuE2**: LM hai tầng sinh token ngữ nghĩa rồi âm học, học trong ngữ cảnh từ clip tham chiếu.
* **ACE-Step 1.5** (MIT, 01/2026): LM (Qwen3) lập "bản thiết kế" bài (BPM, giọng, cấu trúc, mã 5 Hz) + Diffusion
  Transformer tổng hợp âm thanh; có cover, repaint, "lego" (thêm track), "complete" (làm đầy) – rất giống bộ tính năng của Suno.
* **MusicGen**: một transformer duy nhất sinh K sổ mã song song nhờ "delay pattern".

## 4. Micow lấy gì, làm gì

| Thành phần (suy ra từ Suno) | Trong Micow |
|---|---|
| Hiểu phong cách + lời + thẻ đoạn | `micow/planner.py`, `styles.py`, `lyrics.py`: đọc mô tả tiếng Việt/Anh, thẻ `[Điệp khúc]`/`[Chorus]`, thanh điệu tiếng Việt → **bản thiết kế bài** (tempo, giọng, đoạn, ô nhịp, hợp âm, năng lượng) – tương đương LM planner của ACE-Step |
| Phân tích clip người dùng | `micow/analysis.py`: tempo, phách, giọng (HPSS + chroma bass), năng lượng, onset, phân loại kick/snare/hat |
| Codec token hoá âm thanh | `micow/model/codec.py` – **Micow Codec**: encoder/decoder conv + RVQ 8 sổ mã, 50 khung/giây |
| Transformer tự hồi quy trên token | `micow/model/lm.py` – **Micow-LM**: một transformer (RoPE, SwiGLU) đọc `[phong cách][meta][lời]` dạng byte UTF-8 (không âm vị – đúng triết lý Suno), `[clip tham chiếu]`, rồi sinh K sổ mã/khung bằng delay pattern; classifier-free guidance; KV-cache; cửa sổ trượt |
| Extend / Continue / Upload | "Ép token đã biết": clip người dùng được mã hoá rồi đặt ở đầu luồng âm thanh, mô hình sinh tiếp (`prompt=`) |
| Persona / tham chiếu phong cách | Clip tham chiếu đặt trong tiền tố `<ref>…</ref>`; khi huấn luyện lấy từ *phần khác của cùng bài* để học phong cách mà không chép nội dung |
| Chất lượng sản xuất ngay hôm nay | Engine **ACE-Step 1.5** (MIT) cài vào máy qua Micow: giọng hát thật theo lời tiếng Việt, cover, làm đầy |
| Tức thì, không GPU | Engine **Micow Beat**: soạn nhạc + tổng hợp âm thanh bằng thuật toán, dùng clip làm vòng lặp/lát cắt/bộ trống |
| Stems, master | Micow Beat xuất stem thật (từng track); master −14 LUFS, trần −1 dBFS cho mọi engine |

## 5. Giới hạn trung thực
* Không thể "lấy" mô hình của Suno: trọng số nằm trên máy chủ của họ. Thứ suy ngược được là **kiến trúc và
  cách điều khiển**, không phải chất lượng.
* Chất lượng của Micow-LM phụ thuộc hoàn toàn vào **dữ liệu bạn có quyền dùng** và GPU để huấn luyện.
  Dữ liệu tổng hợp từ Micow Beat chỉ dùng để chạy thử quy trình và khởi động.
* Muốn có giọng hát thật ngay: dùng engine ACE-Step 1.5 (đã được huấn luyện sẵn, giấy phép MIT).

## Nguồn
* Latent Space – phỏng vấn CEO Suno Mikey Shulman: https://latent.space/p/suno
* Suno Bark (mã nguồn mở): https://github.com/suno-ai/bark
* ACE-Step 1.5: https://github.com/ace-step/ACE-Step-1.5 – báo cáo kỹ thuật arXiv 2602.00744
* YuE: https://github.com/multimodal-art-projection/YuE
* MusicGen / AudioCraft (delay pattern): https://github.com/facebookresearch/audiocraft
* Thảo luận kỹ thuật về Suno/Udio: https://vi-control.net/community/threads/how-exactly-do-suno-ai-and-udio-com-work-technical-view.151041/
