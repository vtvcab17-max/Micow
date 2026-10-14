# Kiến trúc Micow

Micow là mô hình làm nhạc **chạy trên máy người dùng**, thuộc hệ sinh thái Bravinall (Bravin dựng video,
Antifact thiết kế, Micron mở rộng AI). Hai việc chính:

1. **Tạo beat** (không lời) từ thể loại / mô tả + các đoạn nhạc mẫu đưa vào.
2. **Tạo bài hát hoàn chỉnh** từ lời + phong cách (+ đoạn nhạc mẫu).

## Ba tầng

```
 phong cách ─┐                ┌──────────────┐     ┌──────────────────────────┐     ┌──────────────┐
 lời ────────┼─▶ PLANNER ───▶ │ BẢN THIẾT KẾ │ ──▶ │ ENGINE                    │ ──▶ │ HẬU KỲ       │──▶ thư viện
 clip mẫu ───┘   (+analysis)  │ tempo, giọng │     │ • Micow Beat (CPU, có sẵn)│     │ cân stem     │   WAV/MP3/
                              │ đoạn, ô nhịp │     │ • ACE-Step 1.5 (GPU)      │     │ −14 LUFS     │   stem/MIDI/
                              │ hợp âm, NL   │     │ • Micow-LM (tự huấn luyện)│     │ trần −1 dBFS │   LRC
                              └──────────────┘     └──────────────────────────┘     └──────────────┘
```

| Tầng | Mã | Việc |
|---|---|---|
| Phân tích clip | `micow/analysis.py` | Tempo (tự tương quan đường onset + ưu tiên log-normal), phách, giọng (HPSS + chroma hoà âm + chroma bass, profile Albrecht–Shanahan & Krumhansl), năng lượng, độ sáng, onset, phân loại kick/snare/hat, đoán thể loại |
| Phong cách | `micow/styles.py` | 12 thể loại (V-Pop, Ballad, R&B, Trap, Drill, Boom Bap, Lo-fi, House, EDM, Vinahouse, Bolero, Cinematic); đọc tâm trạng, nhạc cụ, BPM, giọng ("La thứ", "Am"), giới tính giọng hát; caption tiếng Anh cho mô hình AI |
| Lời | `micow/lyrics.py` | Thẻ đoạn Việt/Anh, tự đoán điệp khúc khi không có thẻ, âm tiết, **thanh điệu tiếng Việt**, nguyên âm chính, ngôn ngữ, chuẩn hoá thẻ cho ACE-Step, xuất LRC |
| Planner | `micow/planner.py` | Bản thiết kế: số ô nhịp mỗi câu theo tốc độ hát của thể loại, đoạn làm tròn 4 ô, khớp thời lượng, hợp âm theo đoạn, năng lượng; dùng tempo/giọng của clip khi người dùng không ghi rõ |
| Micow Beat | `micow/dsp/` | `patterns.py` (trống/bass/hoà âm/hook theo thể loại, build-up, fill, crash), `melody.py` (giai điệu theo lời + thanh điệu), `synth.py` (tổng hợp nhạc cụ + giọng mẫu formant), `sampler.py` (loop/chop/kit từ clip), `fx.py` (lọc, reverb tích chập, delay, nén, sidechain, phase vocoder), `master.py` (LUFS BS.1770, limiter), `render.py` (ghép) |
| Micow-LM | `micow/model/` | `codec.py` (Micow Codec RVQ), `lm.py` (transformer tự hồi quy), `tokenizer.py` (byte UTF-8), `train.py`, `data.py`, `generate.py` |
| ACE-Step 1.5 | `micow/engines/acestep.py` | Cài (git + uv + `acestep-download`), chạy REST API cục bộ, gửi tác vụ text2music / cover / complete / Micow Beat + cover |
| Máy chủ | `micow/server.py`, `service.py`, `jobs.py` | HTTP thư viện chuẩn, hàng đợi một luồng sinh nhạc, chặn Origin lạ |
| Giao diện | `web/` | HTML/CSS/JS thuần (không build) theo phong cách Bravin: graphite + iris, vàng chỉ cho thời gian |

## Micow Ear – nghe nhiều bài, tìm hook và peak

```
âm thanh ─STFT─▶ HPSS (hoà âm / bộ gõ) ─┬─▶ BeatTCN (19 đặc trưng/khung, TCN giãn 1..32) ─▶ xác suất phách, đầu ô nhịp
                                        └─▶ dự phòng: tempo theo cấp phách + quy hoạch động + chọn pha (kick/snare/đổi hợp âm)
phách, ô nhịp ─▶ đặc trưng ô nhịp (chroma xếp chồng, MFCC, độ lớn, độ sáng, bass, giọng…)
             ─▶ SSM + novelty ─▶ ranh giới đoạn, cụm A/B/C ─▶ 18 đặc trưng/ô nhịp
             ─▶ quy tắc  ⊕  BarMLP (ngữ cảnh ±4 ô) ─▶ hook (3 ứng viên), peak, loại đoạn
peak ─▶ tinh chỉnh khoảnh khắc drop ở độ phân giải 23 ms (bước nhảy độ lớn) ─▶ bám phách gần nhất
```

* Mọi đặc trưng ô nhịp chuẩn hoá trong từng bài (tương đối) để học trên nhạc tổng hợp vẫn dùng được cho nhạc thật.
* Trọng số `micow/ear/weights/*.npz` (~100 KB), chạy bằng numpy; `report.json` lưu kết quả đánh giá lúc huấn luyện.
* Dữ liệu huấn luyện: `micow/ear/dataset.py` dựng bài bằng Micow Beat với nhãn tuyệt đối (phách, ô nhịp, đoạn, hook, peak),
  **trộn lại ngẫu nhiên từng stem** (±7 dB, tắt bớt stem), EQ, nhiễu, tự động hoá âm lượng, master lại.
* Nhãn người dùng (nút "Đúng hook") lưu ở `~/.micow/ear_labels.jsonl`, được trộn vào lần huấn luyện sau với trọng số ×3.

## Nhạc CapCut
* **Cắt từ bài có sẵn** (`ear/capcut.py`): `hook` (bắt đầu đúng đầu ô nhịp của hook), `peak` (bắt đầu ở cú drop),
  `peak_at` (drop rơi đúng giây X). Mặc định dài **đúng** số giây; tuỳ chọn kết thúc ở đầu ô nhịp; thiếu nhạc thì lặp hook
  theo ô nhịp; vòng lặp liền mạch. Xuất `markers.csv/json` (phách, ô nhịp, hook, drop, đoạn) và `capcut.bravin.json`.
* **Tạo mới** (`planner.py` chế độ `capcut`): đoạn Hook từ ô nhịp đầu → build-up (snare dồn + riser) → Drop đúng giây
  `peak_at`; tempo được chỉnh để drop rơi đúng đầu ô nhịp; độ dài đúng tuyệt đối; vòng lặp nối đuôi vang vào đầu bài.
* Engine AI (ACE-Step, Micow-LM) ở chế độ CapCut: tạo bài dài gấp ~3 lần rồi Micow Ear chọn hook/peak và cắt.
* Nhiều clip "Học phong cách" được gộp: tempo trung vị (quy về cùng quãng tám), giọng bỏ phiếu theo độ tin cậy, năng lượng trung bình.
* Clip dùng kiểu `hook`: Micow Ear tìm hook của clip rồi dùng đúng đoạn đó làm vòng lặp trong bài mới.

## Engine

| | Micow Beat | ACE-Step 1.5 | Micow-LM |
|---|---|---|---|
| Cần cài | Không | Git + ~10 GB | PyTorch + checkpoint |
| Phần cứng | CPU bất kỳ | GPU ≥ 4 GB (NVIDIA/AMD) hoặc Apple Silicon | GPU khuyến nghị |
| Beat | ✓ | ✓ | ✓ |
| Bài hát | Nhạc nền + giọng mẫu ngân nguyên âm | **Giọng hát thật** 50+ ngôn ngữ (có tiếng Việt) | Theo dữ liệu bạn huấn luyện |
| Dùng clip | style · loop · chop · kit | style (reference) · cover · complete · loop/chop/kit → Micow Beat + cover | style (tham chiếu) · complete (nối dài) |
| Stem / MIDI / LRC | ✓ / ✓ / ✓ | – | – |
| Giấy phép | MIT | MIT | MIT (trọng số của bạn) |

## Micow-LM chi tiết

```
Micow Codec: wav 32 kHz ─conv stride 2·4·8·10─▶ latent 128-d @ 50 Hz ─RVQ 8 × 1024─▶ token [8, T]
Micow-LM   : [<style> byte… <meta> bpm:120 key:A minor dur:180 t:30 <lyrics> byte…][<ref> khung… </ref>][BOS, khung…]
             mỗi khung = Σ_k Emb_k(token_k) ; 8 đầu ra dự đoán 8 sổ mã ; sổ mã k trễ k bước (delay pattern)
```

* **Không âm vị**: lời tiếng Việt có dấu đi thẳng vào dạng byte – mô hình tự học cách hát.
* **Điều kiện thời điểm** `t:` cho biết cửa sổ đang ở giây thứ mấy của bài → sinh bài dài bằng cửa sổ trượt
  (giữ 50% cửa sổ trước làm ngữ cảnh).
* **Clip tham chiếu** (≤10 giây) trong tiền tố; khi huấn luyện lấy từ đoạn khác của cùng bài, bỏ ngẫu nhiên 50%.
* **Nối dài clip** (giống Suno Extend): token của clip được "ép" ở đầu luồng âm thanh, mô hình sinh tiếp.
* **Classifier-free guidance**: bỏ điều kiện văn bản 10% khi huấn luyện, trộn logit khi sinh (mặc định 3.0).
* **v2 – đường cấu trúc**: mỗi khung cộng embedding loại đoạn + mức năng lượng (từ planner khi sinh, từ nhãn Micow Ear khi
  huấn luyện) → mô hình biết lúc nào vào hook, lúc nào drop; checkpoint v1 vẫn nạp được (tắt đường cấu trúc).
* Preset: `tiny` (thử), `small` (~30M tham số, 8 lớp × 512), `base` (~300M, 24 × 1024), `large` (32 × 1536).

## REST API (máy chủ cục bộ, mặc định `http://127.0.0.1:5690`)

| Phương thức | Đường dẫn | Việc |
|---|---|---|
| GET | `/api/health` | `{app, version, ok}` |
| GET | `/api/system` | CPU, RAM, GPU/VRAM, ổ trống, ffmpeg, PyTorch, engine gợi ý |
| GET/POST | `/api/settings` | Đọc / sửa `~/.micow/settings.json` (URL ACE-Step, `allowed_origins`…) |
| GET | `/api/styles` | Thể loại, tâm trạng, nhạc cụ |
| GET | `/api/engines` | Trạng thái engine |
| POST | `/api/engines/{id}/install` · `/start` · `/stop` | Cài / chạy / dừng (trả job) |
| POST | `/api/plan` | Bản thiết kế bài (xem trước, không sinh âm thanh) |
| POST | `/api/upload` | Thân = byte âm thanh, header `X-Filename` → phân tích clip |
| GET/DELETE | `/api/uploads[/{id}]`, `/api/uploads/{id}/audio` | Danh sách / xoá / nghe clip |
| POST | `/api/generate` | Tạo nhạc → job (xem `GenRequest` trong `engines/base.py`) |
| GET | `/api/jobs[/{id}]`, POST `/api/jobs/{id}/cancel` | Tiến độ / huỷ |
| GET/DELETE | `/api/library[/{id}]`, POST `/api/library/{id}/rename`, GET `/api/library/{id}/zip` | Thư viện |
| GET | `/files/{id}/{tệp}` | Tải tệp (hỗ trợ Range) |
| POST | `/api/ear/listen` | `{ids: [upload id…]}` → job: Micow Ear nghe nhiều bài (kết quả lưu `uploads/<id>/ear.json`) |
| POST | `/api/capcut` | `{id, duration, mode: hook\|peak\|peak_at, peak_at, candidate, loop, snap_end}` → job cắt nhạc |
| POST | `/api/ear/label` | `{id, hook_start, hook_end, peak_start?, peak_end?}` – ghi nhãn người dùng |
| GET | `/api/ear/report` | Kết quả đánh giá của lần huấn luyện Ear gần nhất |

Ví dụ:
```bash
curl -X POST localhost:5690/api/generate -H 'Content-Type: application/json' -d '{
  "mode": "song", "engine": "micow-dsp", "style": "ballad buồn, piano, giọng nữ",
  "lyrics": "[Verse]\nChiều nay phố vắng mưa rơi trên vai\n[Chorus]\nThôi đừng khóc nữa em ơi",
  "clips": [{"id": "<upload id>", "use": "style"}]}'
```

`use` của clip: `style` (học tempo/giọng/năng lượng, ACE-Step dùng làm reference audio), `loop`, `chop`, `kit`
(Micow Beat), `cover`, `complete` (ACE-Step; Micow-LM dùng `complete` để nối dài).

## Dữ liệu trên máy (`~/.micow`, đổi bằng `MICOW_HOME`)
```
library/<id>/  meta.json  mix.wav  mix.mp3  stems/*.wav  song.mid  lyrics.lrc  blueprint.json
uploads/<id>/  clip.wav  meta.json (phân tích)
models/micow-lm/<tên>/  codec.pt  lm.pt
models/ace-step/        trọng số ACE-Step (ACESTEP_CHECKPOINTS_DIR)
engines/ACE-Step-1.5/   mã nguồn + .venv của ACE-Step
logs/                   nhật ký lỗi, acestep.log
settings.json
```

## Bảo mật
* Máy chủ chỉ nghe `127.0.0.1` (trừ khi chạy `micow serve --lan`).
* Trình duyệt chỉ gọi được API từ `localhost`, bản web chính thức và các nguồn trong `allowed_origins`
  (trang web lạ không điều khiển được Micow trên máy bạn). Có header Private Network Access.
* Đường dẫn tệp được kiểm tra chống `../`.

## Liên kết hệ sinh thái Bravinall
* **Bravin**: tải `.lrc` (mốc thời gian từng câu do Micow Beat tính) + WAV → Bravin "Video lời bài hát" nhập LRC và dựng video karaoke.
* **MIDI kèm lời** (sự kiện lyric từng âm tiết) mở được trong DAW.
* Giao diện dùng chung token màu, phông Plus Jakarta Sans và quy tắc "vàng = thời gian" của Bravin.
