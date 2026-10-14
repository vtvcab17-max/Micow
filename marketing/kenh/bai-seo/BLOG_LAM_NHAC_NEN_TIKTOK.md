<!--
SEO
- Tiêu đề trang (title tag, ≤ 60 ký tự): Làm nhạc nền TikTok bằng AI miễn phí, chạy trên máy | Micow
- Mô tả (meta description, ≤ 155 ký tự): Mình thử làm nhạc nền cho video TikTok bằng Micow: AI làm nhạc chạy ngay trên laptop, miễn phí, không cần mạng, chọn được drop rơi đúng giây.
- Đường dẫn (slug): lam-nhac-nen-tiktok-bang-ai-mien-phi
- Từ khoá chính: làm nhạc nền tiktok bằng ai
- Từ khoá phụ: phần mềm làm nhạc miễn phí, tạo beat bằng ai, ai làm nhạc offline, cắt nhạc capcut, nhạc nền video không lo bản quyền, tạo nhạc vinahouse
- Ảnh: dùng khung hình từ video giới thiệu; alt ghi rõ nội dung (gợi ý ở cuối bài)
- Nơi đăng: trang Bravinall (bản blog), Viblo, Spiderum. Đăng nơi khác thì để link gốc (canonical) về bản đầu tiên.
-->

# Mình làm nhạc nền TikTok bằng AI ngay trên laptop, không tốn đồng nào

Ai làm video ngắn chắc cũng từng bị vụ này. Dựng xong cái video, ghép nhạc vào, rồi ngồi kéo qua kéo lại mãi để cái đoạn nhạc bùng lên nó trúng đúng lúc chuyển cảnh. Kéo xong thì nhạc bị cụt, hoặc vừa lúc hay thì hết giờ. Có hôm đăng lên còn bị tắt tiếng vì nhạc của người ta.

Mình cũng bị y như vậy nên mới ngồi làm cái phần mềm tên là **Micow**. Nói ngắn gọn thì nó là AI làm nhạc, nhưng chạy ngay trên máy tính của mình chứ không phải lên web của ai.

## Micow làm được gì

Cái mình dùng nhiều nhất là làm nhạc nền cho video ngắn. Mình gõ kiểu "vinahouse sôi động, sáo", chọn video dài 15 giây, chọn muốn drop rơi ở giây thứ 7. Bấm tạo, chờ vài giây là có bài. Drop nó rơi đúng giây 7 luôn, khỏi kéo tay.

Video giới thiệu Micow cũng làm đúng kiểu này. Nhạc nền trong đó là Micow tự làm, drop ở giây 7, trùng cái lúc màn hình chớp tím.

Ngoài ra thì có mấy cái này:

- **Tạo beat.** Có 12 thể loại: V-Pop, Ballad, R&B, Trap, Drill, Boom Bap, Lo-fi, House, EDM, Vinahouse, Bolero, Cinematic. Mình thích nhất là có Vinahouse với Bolero, mấy cái tool nước ngoài ít khi có.
- **Tạo bài hát từ lời.** Viết lời vào, chọn phong cách, nó ra cả bài. Cái hay là giai điệu nó đi theo dấu tiếng Việt, chữ dấu sắc thì nốt lên, dấu huyền thì nốt xuống, nghe đỡ bị lơ lớ.
- **Nghe nhạc có sẵn rồi tìm đoạn hay.** Cái này tên là Micow Ear. Thả mấy bài vào, nó chỉ ra đoạn hook với đoạn cao trào của từng bài, rồi cắt đúng số giây mình cần, bắt đầu đúng đầu nhịp.
- **Xuất file.** WAV, MP3, tách riêng từng phần nhạc (stem), MIDI có lời, file lời .lrc. Nếu dựng video bằng Bravin thì nó xuất luôn dự án khung dọc 9:16.

## Có mất tiền không, có cần mạng không

Không mất tiền. Micow là mã nguồn mở, giấy phép MIT. Không giới hạn số bài, muốn tải bao nhiêu thì tải.

Không cần mạng lúc làm nhạc. Cài xong là chạy trên máy, nhạc với dữ liệu nằm trên máy mình, không gửi đi đâu.

Máy cũng không cần mạnh. Bản có sẵn chạy bằng CPU thường, máy văn phòng cũng chạy được. Card đồ hoạ chỉ cần nếu muốn cài thêm ACE-Step để có giọng hát thật, hoặc muốn tự huấn luyện mô hình.

## Nói thật mấy điểm chưa được

Mình không muốn quảng cáo quá lên rồi mọi người cài về thất vọng.

Giọng hát với phối khí thì **Suno vẫn hơn**, cái này rõ. Bản có sẵn của Micow chỉ có giọng mẫu ngân theo giai điệu, chưa phải giọng người thật. Muốn giọng thật phải cài thêm ACE-Step và cần card đồ hoạ.

Giao diện hiện tại chỉ có tiếng Việt. Cài thì phải gõ một dòng lệnh, ai chưa quen chắc hơi ngợp, nhưng có gói ZIP bấm đúp cho Windows.

Micow chỉ chạy trên máy tính (Windows, macOS, Linux), chưa có bản điện thoại.

Còn mấy con số đo thì mình ghi rõ là đo trên nhạc tổng hợp có nhãn, chưa phải nhạc thật ngoài đời: nhận phách đúng khoảng 99%, tìm hook đúng khoảng 95%, drop rơi trong khoảng ±0,25 giây ở cả 8/8 bài thử. Chi tiết nằm trong file BENCHMARK trên GitHub, ai muốn thì tự chạy lại được.

## Cài thế nào

Trên Windows, mở PowerShell rồi dán dòng này:

```
irm https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.ps1 | iex
```

Trên macOS hoặc Linux thì mở Terminal:

```
curl -fsSL https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.sh | bash
```

Xong gõ `micow serve --open` là nó mở giao diện lên.

Ai ngại gõ lệnh thì tải gói ZIP về, giải nén, bấm đúp file `Cai dat Micow.bat`, xong bấm `Mo Micow.bat` là được. Máy cần có Python 3.10 trở lên, thiếu thì bộ cài nó tự hỏi cài giúp.

Link tải với hướng dẫn: [bravinall.vtvcab17.workers.dev/micow](https://bravinall.vtvcab17.workers.dev/micow)

## Mấy câu hay bị hỏi

**Nhạc làm ra có bị dính bản quyền không?**
Nhạc tạo bằng Micow Beat thuộc về người tạo. Nhưng nếu bạn thả bài của người khác vào làm vòng lặp thì bài đó vẫn là của người ta, đăng lên vẫn có thể dính.

**Máy yếu có chạy được không?**
Được, bản có sẵn chạy bằng CPU. Mình thử trên máy bình thường thì một bài 30 giây ra trong vài giây.

**Có dùng trên điện thoại được không?**
Chưa. Phải có máy tính.

**Có giọng hát không?**
Có giọng mẫu. Muốn giọng thật thì cài thêm ACE-Step, cần card đồ hoạ.

**Micow có liên quan gì tới Bravin?**
Cùng một nhà, đều là sản phẩm của Beta. Micow xuất file lời và dự án để dựng video luôn trong Bravin.

---

Mã nguồn: [github.com/vtvcab17-max/Micow](https://github.com/vtvcab17-max/Micow). Ai dùng thử thấy lỗi hay có ý gì thì cứ báo, mình đọc hết.

<!--
Gợi ý alt ảnh:
- "Giao diện Micow đang tạo nhạc nền 15 giây, drop ở giây 7"
- "Micow Ear chỉ ra đoạn hook trên sóng nhạc"
- "Khung hình video giới thiệu Micow lúc drop rơi đúng giây 7"
-->
