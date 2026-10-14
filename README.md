<p align="center">
  <img src="web/icons/icon.svg" alt="Micow" width="72" height="72">
</p>

<h1 align="center">Micow</h1>

<p align="center"><b>Làm nhạc trên máy bạn.</b><br>
Tạo beat, tạo bài hát hoàn chỉnh từ lời, phong cách và đoạn nhạc mẫu. Tìm hook, cắt nhạc cho CapCut.<br>
Miễn phí (MIT) · chạy offline · không giới hạn lượt tải.</p>

<p align="center">
  <a href="#cài-đặt"><b>⬇ Cài đặt</b></a> ·
  <a href="https://micow.vtvcab17.workers.dev/">Bản web</a> ·
  <a href="https://bravinall.vtvcab17.workers.dev/micow.html">Trang giới thiệu</a>
</p>

---

> [!NOTE]
> Mô hình **luôn chạy trên máy bạn**. Giao diện web mở được từ máy chủ cục bộ của Micow hoặc từ [bản web](https://micow.vtvcab17.workers.dev/), nhưng cả hai đều cần cài Micow về máy trước.

## Mục lục

- [Làm được gì](#làm-được-gì)
- [Cài đặt](#cài-đặt)
- [Dùng](#dùng)
- [Ba engine](#ba-engine)
- [Thể loại](#thể-loại)
- [Số đo](#số-đo)
- [Cho người phát triển](#cho-người-phát-triển)
- [Giấy phép](#giấy-phép-và-trách-nhiệm)

## Làm được gì

| | Tính năng | Chi tiết |
|---|---|---|
| 🎤 | **Tạo bài hát** | Viết lời (thẻ `[Phiên khúc]`, `[Điệp khúc]`…), tả phong cách, thả clip mẫu. Micow soạn hoà âm, giai điệu **theo thanh điệu tiếng Việt**, cấu trúc bài, rồi dựng thành bài. Xuất WAV, MP3, stem, MIDI kèm lời, `.lrc` cho Bravin |
| 🥁 | **Tạo beat** | Chọn thể loại hoặc thả đoạn nhạc bạn thích. Micow học tempo, giọng, năng lượng; dùng clip làm vòng lặp, lát cắt (chop) hoặc bộ trống; dựng đủ intro / điệp khúc / drop / kết |
| 👂 | **Micow Ear** | Nghe nhiều bài cùng lúc: dò phách, đầu ô nhịp, cấu trúc (intro / verse / chorus / drop…), chỉ ra **hook** (3 ứng viên) và **đoạn peak / cú drop**, xếp hạng hook mạnh nhất |
| ✂️ | **Cắt nhạc CapCut** | Đúng số giây (10 / 15 / 30 / 60 hoặc tuỳ ý), bắt đầu đúng đầu ô nhịp của hook, hoặc đặt **drop rơi đúng giây X** của video. Vòng lặp liền mạch. Xuất **mốc nhịp .csv** và **dự án Bravin 9:16** |
| ✨ | **Tạo nhạc CapCut mới** | Hook vang ngay giây đầu, build-up rồi drop đúng giây bạn chọn (Micow tự chỉnh tempo để drop rơi đúng đầu ô nhịp). Học phong cách từ các bài bạn thả, hoặc lấy đúng hook của một bài làm vòng lặp |

Micow Ear dùng mạng **BeatTCN** (nghe phách) và **BarMLP** (hook / peak / loại đoạn), huấn luyện trên 221 bài có nhãn chính xác, chạy bằng numpy, không cần GPU. Bấm **Đúng hook** trên bài thật để Micow học theo tai bạn (`micow train ear`).

Micow được thiết kế bằng cách **suy ngược kiến trúc của Suno**: hiểu phong cách + lời + đoạn nhạc mẫu → lập bản thiết kế bài → sinh âm thanh → hậu kỳ. Xem [`docs/SUNO_SUY_NGUOC.md`](docs/SUNO_SUY_NGUOC.md).

## Cài đặt

Cần **Python 3.10+** và CPU bất kỳ. GPU chỉ cần cho ACE-Step hoặc khi huấn luyện.

### Một lệnh (khuyên dùng)

Tải từ GitHub về `~/.micow/app` rồi cài. Chạy lại lệnh để cập nhật; nhạc và mô hình của bạn giữ nguyên.

**Windows** (mở PowerShell):
```powershell
irm https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.ps1 | iex
```

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.sh | bash
```

Mở trang web Micow khi chưa cài cũng thấy màn hình **Tải Micow về máy** với đúng lệnh cho hệ điều hành của bạn.

### Windows: tải tệp

1. Tải [mã nguồn dạng ZIP](https://github.com/vtvcab17-max/Micow/archive/HEAD.zip) và giải nén.
2. Bấm đúp `Cai dat Micow.bat`. Nếu thiếu Python, bộ cài tự đề nghị cài qua winget.
3. Mở `Mo Micow.bat` (hoặc biểu tượng Micow trên Desktop).

### macOS / Linux: từ mã nguồn

```bash
git clone https://github.com/vtvcab17-max/Micow && cd Micow
bash scripts/install.sh            # tạo môi trường ~/.micow/venv và lệnh `micow`
micow serve --open                 # mở http://127.0.0.1:5690
```

<details>
<summary><b>Tuỳ chọn cài thêm</b></summary>

- `--with-torch`: cho Micow-LM.
- `--with-ace`: cài luôn ACE-Step 1.5.
- **ffmpeg** (không bắt buộc): để xuất MP3 và đọc clip mp3/m4a từ dòng lệnh. Giao diện web tự giải mã clip trong trình duyệt.

</details>

## Dùng

### Giao diện

**Tạo bài hát** · **Tạo beat** · **Nhạc CapCut** · **Thư viện** · **Mô hình**

Bản thiết kế bài (cấu trúc, hợp âm, tempo, giọng) hiện ngay khi bạn gõ, trước khi tạo.

### Dòng lệnh

**Nhạc CapCut**
```bash
micow ear bai1.mp3 bai2.mp3 bai3.mp3                  # cấu trúc, hook, peak + xếp hạng hook
micow capcut bai1.mp3 -d 15                            # 15 giây từ hook, đúng đầu ô nhịp
micow capcut bai1.mp3 -d 30 --peak-at 7 --loop         # drop rơi đúng giây 7, phát lặp liền mạch
micow capcut --gen -s "vinahouse sôi động, sáo" -d 15 --peak-at 7   # tạo mới
```

**Beat và bài hát**
```bash
micow beat -s "trap tối, 808 nặng, chuông" -d 90 --clip vong_lap.wav:loop --clip trong.wav:kit -o beat_cua_toi
micow beat -s "UK drill tối, 808 trượt, dàn dây" -d 60 -o beat_drill
micow beat -s "vinahouse bay phòng, sáo" -d 60 -o beat_vinahouse
micow song -s "ballad buồn, piano, giọng nữ" -l loi.txt
micow song -e ace-step -s "v-pop tươi sáng, guitar, giọng nam" -l loi.txt --clip mau.mp3:style
```

**Công cụ khác**
```bash
micow analyze clip.wav              # tempo, giọng, năng lượng
micow plan -s "bolero" -l loi.txt   # xem bản thiết kế
micow install ace-step              # cài ACE-Step 1.5
```

## Ba engine

| Engine | Cần gì | Làm được |
|---|---|---|
| **Micow Beat** · có sẵn | CPU bất kỳ, không tải gì | Beat 12 thể loại trong vài giây; bài hát có nhạc nền + **giọng mẫu** ngân theo giai điệu; dùng clip làm loop / chop / bộ trống; xuất WAV, MP3, **stem**, **MIDI kèm lời**, **.lrc** cho Bravin |
| **ACE-Step 1.5** · cài thêm, MIT | GPU ≥ 4 GB hoặc Apple Silicon, ~10 GB ổ | **Giọng hát thật** theo lời (có tiếng Việt), cover từ clip, làm đầy đoạn dang dở, 10 giây – 10 phút; kết hợp "Micow Beat + cover" giữ cấu trúc bài của Micow |
| **Micow-LM** · tự huấn luyện | PyTorch, GPU khuyến nghị | Mô hình riêng theo kiến trúc Suno: codec RVQ + transformer tự hồi quy trên token âm thanh, điều kiện bằng phong cách, lời (byte UTF-8), clip tham chiếu, nối dài clip. Xem [`docs/HUAN_LUYEN.md`](docs/HUAN_LUYEN.md) |

## Thể loại

V-Pop · Ballad · R&B · Trap · **Drill** · Boom Bap · Lo-fi · House · EDM · **Vinahouse** · **Bolero** · Cinematic

<details>
<summary><b>Vinahouse và Drill</b></summary>

- **Vinahouse** (132–140 BPM): kick 4/4, bass cuộn phách lẻ, hi-hat dày, sáo/lead nổi, build-up + drop. Gõ "vinahouse", "nhạc sàn", "bay phòng", "remix".
- **Drill** (138–146 BPM, cảm giác nửa nhịp): 808 nhảy quãng và **trượt cao độ**, hi-hat nhóm 3-3-2 + cuộn chùm ba, snare phách 3 kèm snare "trễ" ở ô nhịp lẻ, dàn dây/piano tối. Gõ "drill", "UK drill", "drill Việt", "808 trượt".

</details>

Nhạc cụ tổng hợp: piano, piano điện, guitar, dàn dây, pad, supersaw, pluck, chuông, organ, **sáo trúc**, **đàn tranh**, 808…

## Số đo

Đo bằng `micow bench` trên **39 bài nhạc tổng hợp có nhãn** (chưa đo trên nhạc thật có nhãn):

| Chỉ số | Kết quả |
|---|---|
| Micow Ear: nhận phách | 99% |
| Micow Ear: hook nằm trong điệp khúc / drop thật | 95% |
| Micow Ear: peak nằm trong đoạn cao trào thật | 87% |
| Nhạc CapCut tạo mới: drop rơi trong ±0,25 giây | 8/8 bài |
| Cắt nhạc: sai số độ dài | 0 giây |

Phép đo đo độ chính xác thời gian và âm lượng, không đo bài có hay hay không. Chi tiết: [`docs/BENCHMARK.md`](docs/BENCHMARK.md). So sánh thẳng thắn với Suno v6: [`docs/SO_SANH_SUNO_V6.md`](docs/SO_SANH_SUNO_V6.md).

## Cho người phát triển

### Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| `micow/` | Lõi Python: `planner.py`, `analysis.py`, `styles.py`, `lyrics.py`, `theory.py`, `dsp/` (Micow Beat), `model/` (Micow-LM), `engines/`, `server.py`, `cli.py` |
| `micow/ear/` | Micow Ear: `features.py` (phách, ô nhịp), `structure.py` (cấu trúc, hook, peak), `nn.py` + `weights/` (mạng đã huấn luyện, numpy), `capcut.py` (cắt, mốc nhịp, dự án Bravin), `dataset.py` + `train.py` (dữ liệu có nhãn, huấn luyện) |
| `web/` | Giao diện HTML/CSS/JS thuần (không build), phong cách Bravin: graphite + iris, vàng chỉ dành cho thời gian |
| `docs/` | `SUNO_SUY_NGUOC.md`, `KIEN_TRUC.md` (kiến trúc + REST API), `HUAN_LUYEN.md`, `SO_SANH_SUNO_V6.md`, `BENCHMARK.md` |
| `scripts/` | Bộ cài macOS / Linux / Windows |
| `tests/` | `test_core.py` (unittest), `ui_smoke.mjs` (Playwright) |

### Kiểm thử

```bash
./init.sh            # kiểm tra tĩnh + unittest + kiểm thử giao diện Chromium
./init.sh --quick    # chỉ kiểm tra tĩnh + unittest
```

### Bản web

`wrangler.jsonc` phát thư mục `web/` lên Cloudflare Workers ([micow.vtvcab17.workers.dev](https://micow.vtvcab17.workers.dev/)). Trang gọi về máy chủ Micow trên máy người dùng (`http://127.0.0.1:5690`); nếu chưa cài, trang hướng dẫn cài đặt.

## Hệ sinh thái Bravinall

| Ứng dụng | Dùng để | Mở ngay |
|---|---|---|
| [Antifact](https://github.com/vtvcab17-max/Antiface) | Thiết kế, chỉnh ảnh | [antiface.vtvcab17.workers.dev](https://antiface.vtvcab17.workers.dev/) |
| [Bravin](https://github.com/vtvcab17-max/Bravin) | Dựng video, nhận `.lrc` và dự án `.bravin.json` từ Micow | [bravin.vtvcab17.workers.dev](https://bravin.vtvcab17.workers.dev/) |
| [Micron](https://github.com/vtvcab17-max/micron) | Canvas AI, plugin cho Bravin | [micron.vtvcab17.workers.dev](https://micron.vtvcab17.workers.dev/) |
| **Micow** | Làm nhạc trên máy | [micow.vtvcab17.workers.dev](https://micow.vtvcab17.workers.dev/) |

## Giấy phép và trách nhiệm

- Mã Micow: **MIT**. Nhạc tạo bằng Micow Beat thuộc về bạn.
- ACE-Step 1.5: MIT (ACE Studio × StepFun). Cài riêng từ kho chính thức, không đóng gói trong repo này.
- Phông Plus Jakarta Sans: SIL Open Font License.
- Micow không dùng mã hay trọng số của Suno. Chỉ huấn luyện Micow-LM trên dữ liệu bạn có quyền dùng.

---

<p align="center">© 2026 Phạm Việt Hà · <a href="https://bravinall.vtvcab17.workers.dev/">Bravinall</a></p>
