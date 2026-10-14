# AGENTS.md: hướng dẫn cho agent viết code (Claude, Codex…) làm việc trên Micow

Micow là mô hình làm nhạc chạy trên máy người dùng (tạo beat + bài hát hoàn chỉnh từ lời, phong cách, đoạn nhạc mẫu),
thuộc hệ sinh thái Bravinall của Phạm Việt Hà (Bravin dựng video, Antifact thiết kế, Micron AI canvas; website ở repo
`vtvcab17-max/Bravinall`). Lõi Python (`micow/`, chỉ cần numpy + scipy; PyTorch tuỳ chọn cho Micow-LM), giao diện
HTML/CSS/JS thuần trong `web/` (không có bước build), phong cách thiết kế giống Bravin 4 (graphite + iris).

**Người dùng nói tiếng Việt: trả lời, giao diện, thông báo, tài liệu đều bằng tiếng Việt.**

## Startup Workflow (bắt đầu phiên)
1. `pwd` để chắc đang ở gốc repo; đọc hết tệp này.
2. Đọc `progress.md` (trạng thái) và `feature_list.json` (nguồn sự thật về tính năng).
3. Chạy `./init.sh --quick` (hoặc đầy đủ `./init.sh`). Nền đỏ thì **sửa nền trước**.
4. `git log --oneline -5`.
5. Cần hiểu sâu thì đọc tài liệu tương ứng:

| Cần biết | Đọc |
|---|---|
| Vì sao kiến trúc như vậy (suy ngược Suno) | `docs/SUNO_SUY_NGUOC.md` |
| Kiến trúc, engine, REST API, thư mục dữ liệu | `docs/KIEN_TRUC.md` |
| Huấn luyện Micow-LM, Micow Ear | `docs/HUAN_LUYEN.md` |
| So sánh với Suno v6, số đo | `docs/SO_SANH_SUNO_V6.md`, `docs/BENCHMARK.md` (`micow bench`) |

## Working Rules
- **Một tính năng một lần**: chọn MỘT mục chưa `done` trong `feature_list.json`, đặt `in-progress`, làm xong mới sang mục khác.
- **Đúng phạm vi**: thấy lỗi khác thì ghi vào `feature_list.json` (`not-started`), không tiện tay sửa.
- **Không build**: thêm JS mới thì thêm `<script>` vào `web/index.html` đúng thứ tự (`ui.js` → `api.js` → `player.js` → `app.js`).
- **Phiên bản**: đổi đồng thời `micow/__init__.py` (`__version__`), `pyproject.toml`, `<meta name="micow-version">` trong `web/index.html`. `init.sh` báo lỗi nếu lệch.
- **Thiết kế**: dùng token trong `web/css/theme.css` (giống Bravin): một màu tương tác iris `#7b6cf6`, container tông iris,
  **vàng `#f2c14e` chỉ dành cho thời gian** (đầu phát, tiến độ phát), không viền mảnh, bo góc lớn, nút viên thuốc, phông Plus Jakarta Sans (cục bộ).
- **Engine mới** kế thừa `micow/engines/base.py:Engine`, đăng ký trong `micow/engines/__init__.py`, ghi kết quả bằng `outputs.save_result`.
- **Bên thứ ba**: ACE-Step 1.5 (MIT) chỉ được cài từ kho chính thức vào `~/.micow/engines`, không chép vào repo.
  Không dùng mã/trọng số/âm thanh của Suno, Udio hay sản phẩm thương mại khác.
- **Tệp > 25 MiB không được nằm trong `web/`** (Cloudflare Workers từ chối). Trọng số (`*.pt`) không đưa lên git.
- `scripts/install.ps1` phải lưu **UTF-8 có BOM** (Windows PowerShell 5.1); `.bat` viết tiếng Việt không dấu.

## Không bao giờ
- Đưa trọng số mô hình, dữ liệu nhạc có bản quyền, khoá API hay token vào repo.
- Mở máy chủ ra mạng (`0.0.0.0`) mặc định, hoặc nới kiểm tra Origin/đường dẫn trong `server.py`.
- Báo "xong" khi `./init.sh` chưa xanh.

## Definition of Done
- [ ] Hành vi mới đã thử như người dùng (Playwright `tests/ui_smoke.mjs` hoặc dòng lệnh `micow …`), không chỉ đọc mã.
- [ ] `./init.sh` đạt; tính năng quan trọng có kiểm thử trong `tests/test_core.py` hoặc `tests/ui_smoke.mjs`.
- [ ] Bằng chứng ghi vào `feature_list.json` (`evidence`) và `progress.md`.
- [ ] Tài liệu trong `docs/` cập nhật; giao diện và chữ bằng tiếng Việt.

## Verification Commands
```bash
./init.sh                       # kiểm tra tĩnh + unittest + kiểm thử giao diện Chromium
./init.sh --quick               # kiểm tra tĩnh + unittest
python3 -m unittest discover -s tests -v
python3 -m micow serve --port 5690   # chạy thử: http://127.0.0.1:5690
```
CI: `.github/workflows/verify.yml` chạy `init.sh` cho mỗi lần đẩy và PR.

## Bẫy đã gặp
- `pkill -f`/`pgrep -f` trong shell agent có thể giết chính shell: ghi PID ra tệp rồi `kill $(cat pid)`.
- `cgi` đã bị xoá khỏi Python 3.13: upload dùng thân request thô + header `X-Filename`, không multipart.
- Trình duyệt giải mã clip (mp3/m4a) bằng WebAudio rồi gửi WAV, nên máy chủ không bắt buộc có ffmpeg.
- Giọng (key) nhạc có nhiều trống: phải tách hoà âm (HPSS) trước khi tính chroma, nếu không sẽ đoán sai.
- Thứ hoà âm: hợp âm lấy từ thứ tự nhiên, chỉ bậc V là trưởng (tránh III+ và VII° nghe sai thể loại).
- `hash()` của Python ngẫu nhiên theo tiến trình: seed tổng hợp âm thanh dùng `zlib.crc32`.
- ACE-Step 1.5 cần Python 3.11–3.12 (uv tự lo), vLLM chỉ trên Linux + CUDA (nơi khác đặt `ACESTEP_LM_BACKEND=pt`);
  `lego`/`complete` chỉ chạy với model base (`acestep-v15-base`, tải bằng tuỳ chọn "model base").

- Micow Ear: hi-hat/bass phách lẻ (house, vinahouse) làm bộ dò phách thuật toán bắt nhầm pha; luôn chọn pha bằng
  kick + snare + đổi hợp âm trên tín hiệu đã lọc max ±2 khung (đỉnh flux chỉ rộng 1 khung).
- Khung STFT của scipy (`boundary=None`) tính từ mép trái: thời điểm = khung/FPS + N_FFT/2/SR (`LAG`).
- Đoạn ngắn / nhịp nửa tempo làm ô nhịp thô: thời điểm drop phải tinh chỉnh ở độ phân giải khung (`refine_drop`).
- Đổi `micow/ear/features.py` hoặc `structure.py` (đặc trưng) thì phải huấn luyện lại (`micow train ear`), vì trọng số
  gắn với đúng thứ tự/ý nghĩa đặc trưng (`FEAT_NAMES`, 19 đặc trưng khung).
- Không đưa "điểm" tự chấm vào tài liệu: mọi so sánh phải có số đo `micow bench` hoặc nguồn công khai.

## End of Session
1. `./init.sh` xanh (hoặc ghi rõ chỗ đỏ và lý do).
2. Cập nhật `feature_list.json`, `progress.md`.
3. Commit thông điệp rõ ràng khi repo sạch.
