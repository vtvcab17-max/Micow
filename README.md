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

## Ba engine

| Engine | Cần gì | Làm được |
|---|---|---|
| **Micow Beat** (có sẵn) | CPU bất kỳ, không tải gì | Beat 11 thể loại trong vài giây; bài hát có nhạc nền + **giọng mẫu** ngân theo giai điệu; dùng clip làm loop/chop/bộ trống; xuất WAV, MP3, **stem**, **MIDI kèm lời**, **.lrc** cho Bravin |
| **ACE-Step 1.5** (cài thêm, MIT) | GPU ≥ 4 GB hoặc Apple Silicon, ~10 GB ổ | **Giọng hát thật** theo lời (có tiếng Việt), cover từ clip, làm đầy đoạn dang dở, 10 giây – 10 phút; kết hợp "Micow Beat + cover" giữ cấu trúc bài của Micow |
| **Micow-LM** (tự huấn luyện) | PyTorch, GPU khuyến nghị | Mô hình riêng theo kiến trúc Suno: codec RVQ + transformer tự hồi quy trên token âm thanh, điều kiện bằng phong cách, lời (byte UTF-8), clip tham chiếu, nối dài clip – xem [`docs/HUAN_LUYEN.md`](docs/HUAN_LUYEN.md) |

Thể loại có sẵn: V-Pop, Ballad, R&B, Trap, Boom Bap, Lo-fi, House, EDM, **Vinahouse**, **Bolero**, Cinematic.
Nhạc cụ tổng hợp: piano, piano điện, guitar, dàn dây, pad, supersaw, pluck, chuông, organ, **sáo trúc**, **đàn tranh**, 808…

## Cài đặt

**Windows**: tải mã nguồn (Code → Download ZIP), giải nén, bấm đúp `Cai dat Micow.bat`, sau đó `Mo Micow.bat`
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

Giao diện: **Tạo bài hát** · **Tạo beat** · **Thư viện** · **Mô hình**. Bản thiết kế (cấu trúc, hợp âm, tempo, giọng)
hiện ngay khi bạn gõ, trước khi tạo.

Dòng lệnh:
```bash
micow beat -s "trap tối, 808 nặng, chuông" -d 90 --clip vong_lap.wav:loop --clip trong.wav:kit -o beat_cua_toi
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
| `docs/` | `SUNO_SUY_NGUOC.md`, `KIEN_TRUC.md` (kiến trúc + REST API), `HUAN_LUYEN.md` |
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
