# Micow

**Mô hình làm nhạc chạy trên máy của bạn** – thuộc hệ sinh thái **Bravinall** (Bravin dựng video · Antifact thiết kế · Micron AI).

Micow được thiết kế bằng cách **suy ngược kiến trúc của Suno** (xem [`docs/SUNO_SUY_NGUOC.md`](docs/SUNO_SUY_NGUOC.md)):
hiểu phong cách + lời + đoạn nhạc mẫu → lập bản thiết kế bài → sinh âm thanh → hậu kỳ. Hai việc chính:

1. **Tạo beat** – chọn thể loại hoặc thả đoạn nhạc bạn thích; Micow học tempo, giọng, năng lượng và dùng clip
   làm vòng lặp, lát cắt (chop) hoặc bộ trống, dựng beat đủ intro / điệp khúc / drop / kết.
2. **Tạo bài hát hoàn chỉnh** – viết lời (thẻ `[Phiên khúc]`, `[Điệp khúc]`…), tả phong cách, thả clip mẫu;
   Micow soạn hoà âm, giai điệu **theo thanh điệu tiếng Việt**, cấu trúc bài, rồi dựng thành bài.

Mô hình **luôn chạy trên máy bạn**: giao diện web có thể mở từ máy chủ cục bộ của Micow hoặc từ bản web,
nhưng đều yêu cầu cài Micow (và mô hình) về máy.

## Mới: Micow Ear + Nhạc CapCut
* **Nghe nhiều bài cùng lúc**: Micow Ear dò phách, đầu ô nhịp, cấu trúc (intro/verse/chorus/drop…), chỉ ra **hook**
  (3 ứng viên) và **đoạn peak / cú drop** của từng bài, xếp hạng hook mạnh nhất.
* **Cắt nhạc CapCut**: đúng số giây (10/15/30/60 hoặc tuỳ ý), bắt đầu đúng đầu ô nhịp của hook, hoặc đặt **drop rơi
  đúng giây X** của video; vòng lặp liền mạch; xuất **mốc nhịp .csv** để cắt cảnh theo nhịp và **dự án Bravin 9:16**.
* **Tạo nhạc CapCut mới**: hook vang ngay giây đầu, build-up rồi drop đúng giây bạn chọn (Micow tự chỉnh tempo để drop
  rơi đúng đầu ô nhịp); học phong cách từ tất cả bài bạn thả, hoặc lấy đúng hook của một bài làm vòng lặp.
* **Mô hình đã huấn luyện**: mạng BeatTCN (nghe phách) + BarMLP (hook/peak/loại đoạn) huấn luyện trên 221 bài có nhãn
  chính xác, chạy bằng numpy (không cần GPU). Bấm **Đúng hook** trên bài thật để Micow học theo tai bạn (`micow train ear`).
* So sánh thẳng thắn với Suno v6: [`docs/SO_SANH_SUNO_V6.md`](docs/SO_SANH_SUNO_V6.md) · số đo: [`docs/BENCHMARK.md`](docs/BENCHMARK.md).

```bash
micow ear bai1.mp3 bai2.mp3 bai3.mp3                 # cấu trúc, hook, peak + xếp hạng hook
micow capcut bai1.mp3 -d 15                           # 15 giây từ hook, đúng đầu ô nhịp
micow capcut bai1.mp3 -d 30 --peak-at 7 --loop        # drop rơi đúng giây 7, phát lặp liền mạch
micow capcut --gen -s "vinahouse sôi động, sáo" -d 15 --peak-at 7   # tạo mới
```

## Ba engine

| Engine | Cần gì | Làm được |
|---|---|---|
| **Micow Beat** (có sẵn) | CPU bất kỳ, không tải gì | Beat 12 thể loại trong vài giây; bài hát có nhạc nền + **giọng mẫu** ngân theo giai điệu; dùng clip làm loop/chop/bộ trống; xuất WAV, MP3, **stem**, **MIDI kèm lời**, **.lrc** cho Bravin |
| **ACE-Step 1.5** (cài thêm, MIT) | GPU ≥ 4 GB hoặc Apple Silicon, ~10 GB ổ | **Giọng hát thật** theo lời (có tiếng Việt), cover từ clip, làm đầy đoạn dang dở, 10 giây – 10 phút; kết hợp "Micow Beat + cover" giữ cấu trúc bài của Micow |
| **Micow-LM** (tự huấn luyện) | PyTorch, GPU khuyến nghị | Mô hình riêng theo kiến trúc Suno: codec RVQ + transformer tự hồi quy trên token âm thanh, điều kiện bằng phong cách, lời (byte UTF-8), clip tham chiếu, nối dài clip – xem [`docs/HUAN_LUYEN.md`](docs/HUAN_LUYEN.md) |

Thể loại có sẵn: V-Pop, Ballad, R&B, Trap, **Drill**, Boom Bap, Lo-fi, House, EDM, **Vinahouse**, **Bolero**, Cinematic.

- **Vinahouse** (132–140 BPM): kick 4/4, bass cuộn phách lẻ, hi-hat dày, sáo/lead nổi, build-up + drop. Gõ "vinahouse", "nhạc sàn", "bay phòng", "remix".
- **Drill** (138–146 BPM, cảm giác nửa nhịp): 808 nhảy quãng và **trượt cao độ**, hi-hat nhóm 3-3-2 + cuộn chùm ba, snare phách 3 kèm snare "trễ" ở ô nhịp lẻ, dàn dây/piano tối. Gõ "drill", "UK drill", "drill Việt", "808 trượt".
Nhạc cụ tổng hợp: piano, piano điện, guitar, dàn dây, pad, supersaw, pluck, chuông, organ, **sáo trúc**, **đàn tranh**, 808…

## Cài đặt

**Một lệnh** (tải từ GitHub về `~/.micow/app` rồi cài; chạy lại lệnh để cập nhật, nhạc và mô hình của bạn giữ nguyên):
```powershell
# Windows – mở PowerShell:
irm https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.ps1 | iex
```
```bash
# macOS / Linux:
curl -fsSL https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.sh | bash
```
Mở trang web Micow khi chưa cài cũng thấy màn hình **Tải Micow về máy** với đúng lệnh cho hệ điều hành của bạn.

**Windows (tải tệp)**: tải mã nguồn (Code → Download ZIP), giải nén, bấm đúp `Cai dat Micow.bat`, sau đó `Mo Micow.bat`
(hoặc biểu tượng Micow trên Desktop). Cần Python 3.10+ (bộ cài tự đề nghị cài qua winget nếu thiếu).

**macOS / Linux**:
```bash
git clone https://github.com/vtvcab17-max/Micow && cd Micow
bash scripts/install.sh            # tạo môi trường ~/.micow/venv, lệnh `micow`
micow serve --open                 # mở http://127.0.0.1:5690
```
Tuỳ chọn: `--with-torch` (cho Micow-LM), `--with-ace` (cài luôn ACE-Step 1.5). ffmpeg (không bắt buộc) để xuất MP3
và đọc clip mp3/m4a từ dòng lệnh – giao diện web tự giải mã clip trong trình duyệt.

## Dùng

Giao diện: **Tạo bài hát** · **Tạo beat** · **Nhạc CapCut** · **Thư viện** · **Mô hình**. Bản thiết kế (cấu trúc, hợp âm, tempo, giọng)
hiện ngay khi bạn gõ, trước khi tạo.

Dòng lệnh:
```bash
micow beat -s "trap tối, 808 nặng, chuông" -d 90 --clip vong_lap.wav:loop --clip trong.wav:kit -o beat_cua_toi
micow beat -s "UK drill tối, 808 trượt, dàn dây" -d 60 -o beat_drill
micow beat -s "vinahouse bay phòng, sáo" -d 60 -o beat_vinahouse
micow song -s "ballad buồn, piano, giọng nữ" -l loi.txt
micow song -e ace-step -s "v-pop tươi sáng, guitar, giọng nam" -l loi.txt --clip mau.mp3:style
micow analyze clip.wav              # tempo, giọng, năng lượng
micow plan -s "bolero" -l loi.txt   # xem bản thiết kế
micow install ace-step              # cài ACE-Step 1.5
```

## Cấu trúc thư mục
| Thư mục | Nội dung |
|---|---|
| `micow/` | Lõi Python: `planner.py`, `analysis.py`, `styles.py`, `lyrics.py`, `theory.py`, `dsp/` (Micow Beat), `model/` (Micow-LM), `engines/`, `server.py`, `cli.py` |
| `web/` | Giao diện HTML/CSS/JS thuần (không build), phong cách Bravin: graphite + iris, vàng chỉ dành cho thời gian |
| `micow/ear/` | Micow Ear: `features.py` (phách, ô nhịp), `structure.py` (cấu trúc, hook, peak), `nn.py` + `weights/` (mạng đã huấn luyện, numpy), `capcut.py` (cắt, mốc nhịp, dự án Bravin), `dataset.py` + `train.py` (dữ liệu có nhãn, huấn luyện) |
| `docs/` | `SUNO_SUY_NGUOC.md`, `KIEN_TRUC.md` (kiến trúc + REST API), `HUAN_LUYEN.md`, `SO_SANH_SUNO_V6.md`, `BENCHMARK.md` |
| `scripts/` | Bộ cài macOS/Linux/Windows |
| `tests/` | `test_core.py` (unittest), `ui_smoke.mjs` (Playwright) |

## Kiểm thử
```bash
./init.sh            # kiểm tra tĩnh + unittest + kiểm thử giao diện Chromium
./init.sh --quick    # chỉ kiểm tra tĩnh + unittest
```

## Bản web
`wrangler.jsonc` phát thư mục `web/` lên Cloudflare Workers. Trang web gọi về máy chủ Micow trên máy người dùng
(`http://127.0.0.1:5690`); nếu chưa cài, trang hướng dẫn cài đặt.

## Giấy phép và trách nhiệm
* Mã Micow: MIT. Nhạc tạo bằng Micow Beat thuộc về bạn.
* ACE-Step 1.5: MIT (ACE Studio × StepFun) – cài riêng từ kho chính thức, không đóng gói trong repo này.
* Phông Plus Jakarta Sans: SIL Open Font License.
* Micow không dùng mã hay trọng số của Suno. Chỉ huấn luyện Micow-LM trên dữ liệu bạn có quyền dùng.
