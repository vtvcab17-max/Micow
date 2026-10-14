# Huấn luyện Micow-LM

Micow-LM là mô hình riêng của Micow (kiến trúc ở `docs/KIEN_TRUC.md`, lý do thiết kế ở `docs/SUNO_SUY_NGUOC.md`).
Repo không kèm trọng số: chất lượng phụ thuộc dữ liệu và GPU của bạn.

> **Chỉ huấn luyện trên nhạc bạn có quyền sử dụng** (tự sáng tác, đã mua bản quyền, public domain, giấy phép mở
> cho phép huấn luyện). Không dùng bài tải từ Suno/Udio/YouTube… khi điều khoản không cho phép.

## 0. Chuẩn bị
```bash
bash scripts/install.sh --with-torch      # hoặc: pip install torch
micow info                                # xem GPU, VRAM
```
Gợi ý phần cứng: `tiny` chạy CPU (chỉ để thử quy trình); `small` cần GPU 8–12 GB; `base` cần ≥ 24 GB.

## 1. Dữ liệu
`manifest.jsonl`, mỗi dòng một bài, đường dẫn tương đối với thư mục chứa manifest:
```json
{"audio": "audio/bai01.wav", "style": "ballad buồn, piano, dàn dây, giọng nữ", "lyrics": "[Verse]\nChiều nay phố vắng…\n[Chorus]\n…", "bpm": 72, "key": "A minor", "lrc": "audio/bai01.lrc"}
```
* `style`: mô tả tự do (Việt hoặc Anh), càng nhất quán càng tốt (thể loại, tâm trạng, nhạc cụ, giọng nam/nữ).
* `lyrics`: lời có thẻ đoạn; bài không lời để trống.
* `lrc` (rất nên có): mốc thời gian từng câu → mỗi cửa sổ huấn luyện chỉ kèm lời đúng đoạn đó, mô hình học
  canh lời nhanh hơn nhiều. Bravin xuất được `.lrc` bằng cách bắt nhịp phím Space.
* Định dạng âm thanh: WAV đọc trực tiếp; mp3/flac/m4a cần ffmpeg.

Muốn chạy thử ngay: dữ liệu tổng hợp bằng Micow Beat (biết chính xác phong cách, lời, LRC):
```bash
micow data synth --out data --n 200 --duration 60
```

## 2. Codec (token hoá âm thanh)
```bash
micow train codec --data data/manifest.jsonl --out ~/.micow/models/micow-lm/cua-toi/codec.pt --steps 100000
```
* Mặc định: 32 kHz, 8 sổ mã × 1024, 50 khung/giây; loss L1 + STFT đa phân giải + commitment, sau 2000 bước
  thêm discriminator STFT (tắt bằng `--no-adv`). Quantizer dropout cho phép giải mã ở ít sổ mã hơn.
* Có thể tiếp tục bằng `--resume`.

## 3. Token hoá dữ liệu
```bash
micow train tokenize --data data/manifest.jsonl --codec ~/.micow/models/micow-lm/cua-toi/codec.pt --out data/tokens
```
Tạo `data/tokens/*.pt` (int16, [8, T]) và `index.json`.

## 4. Micow-LM
```bash
micow train lm --tokens data/tokens --out ~/.micow/models/micow-lm/cua-toi/lm.pt --preset small --steps 200000 --batch 8
```
* Mỗi bước: cắt ngẫu nhiên cửa sổ (mặc định 30 giây), văn bản = phong cách + `bpm/key/dur/t` + lời của cửa sổ,
  clip tham chiếu lấy từ đoạn khác của cùng bài.
* bf16 tự bật trên CUDA; AdamW, warmup + cosine; lưu mỗi 2000 bước; `--resume` để tiếp tục.
* Theo dõi loss từng sổ mã (in ra màn hình): sổ mã đầu giảm trước, các sổ sau giảm chậm hơn là bình thường.

## 5. Dùng
Đặt `codec.pt` và `lm.pt` trong `~/.micow/models/micow-lm/<tên>/` (như các lệnh trên). Mở Micow →
Mô hình: Micow-LM báo "sẵn sàng". Khi tạo nhạc chọn engine Micow-LM; tuỳ chọn trong `options` của API:
`model` (tên thư mục), `cfg` (3.0), `temperature` (1.0), `top_k` (250).

Dòng lệnh:
```bash
micow song -e micow-lm -s "ballad buồn, piano" -l loi.txt -d 60 --clip mau.wav:style
micow beat -e micow-lm -s "lofi chill" --clip dau_bai.wav:complete    # nối dài clip
```

## 6. Huấn luyện Micow Ear (nghe phách, hook, peak) – chạy được trên CPU
```bash
micow train ear                 # sinh 260 bài có nhãn (~45 phút trên 4 nhân), huấn luyện BeatTCN + BarMLP, đánh giá
micow bench                     # đo lại, ghi docs/BENCHMARK.md
```
* Trọng số ghi vào `micow/ear/weights/` (chạy bằng numpy, không cần PyTorch khi dùng).
* Muốn Ear nghe "đúng tai" bạn với nhạc thật: mở trang **Nhạc CapCut**, thả bài, chọn ứng viên hook đúng (nút
  **Hook khác**) rồi bấm **Đúng hook**; nhãn lưu ở `~/.micow/ear_labels.jsonl`, lần `micow train ear` sau sẽ học thêm.

## 7. Nhãn cấu trúc cho Micow-LM v2
Micow-LM v2 học thêm "đường cấu trúc" (loại đoạn + năng lượng từng khung). Dữ liệu tổng hợp đã có sẵn nhãn;
với nhạc thật, cho Micow Ear gán nhãn trước khi token hoá:
```bash
micow data label data/manifest.jsonl
```

## 8. Mở rộng gợi ý
* Dữ liệu lớn hơn và đa dạng hơn quan trọng hơn mô hình lớn hơn (CEO Suno: cả giọng nói không phải nhạc cũng giúp).
* Tinh chỉnh bằng phản hồi người nghe (thích/không thích) theo kiểu DPO là hướng Suno nhắc tới.
* Có thể thay Micow Codec bằng codec mở mạnh hơn (DAC, EnCodec) nếu giấy phép trọng số phù hợp mục đích của bạn.
