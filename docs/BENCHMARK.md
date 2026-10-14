# Micow – số đo cho nhạc CapCut (bản 1.1.0, 2026-10-14 14:01)

Mọi con số dưới đây do `micow bench` đo lại được trên máy (CPU). Không có điểm tự chấm.

## A. Micow Ear – nghe và tìm hook / peak

Tập kiểm tra: 39 bài tổng hợp có nhãn chính xác, **không dùng khi huấn luyện**, đã trộn lại stem, EQ, nhiễu.

| Chỉ số | Chỉ thuật toán | Sau huấn luyện |
|---|---|---|
| Phách đúng (±70 ms) | 89% | 99% |
| Đầu ô nhịp đúng (±70 ms) | 88% | 97% |
| Tempo đúng (±4%, cho phép ×2/÷2) | 95% | 100% |
| Đoạn hook chọn ra nằm trong điệp khúc/drop thật (≥50%) | 72% | 87% |
| Đoạn peak nằm trong đoạn cao trào thật (≥50%) | 38% | 87% |
| Nhãn loại đoạn đúng | 53% | 86% |

## B. Tạo nhạc CapCut mới (Micow Beat)

8 bài (8 thể loại, 15–30 giây, drop yêu cầu ở giây 6–10,5).

| Chỉ số | Kết quả |
|---|---|
| Sai số độ dài | tối đa 0.0 giây |
| Drop theo bản thiết kế lệch giây yêu cầu | tối đa 0.0001 giây |
| Micow Ear nghe lại: drop nằm trong ±0,25 giây | 100% (trung vị lệch 0.01 giây) |
| Nốt hook đầu tiên vang lúc | chậm nhất 0.002 giây |
| Độ bùng của drop (4 giây sau drop so với trước drop) | trung bình +3.58 dB, thấp nhất +3.01 dB |
| Loudness | trung bình -14.0 LUFS, lệch tối đa 0.0 LU so với −14 |
| Đỉnh mẫu cao nhất | -1.0 dBFS |
| Mối nối vòng lặp: bước nhảy so với p99 bước nhảy quanh đó | tối đa 0.85× (≤ 1 là không có tiếng click) |
| Thời gian dựng trung bình (CPU) | 2.08 giây/bài |

## C. Cắt CapCut từ bài có sẵn

12 bài, mỗi bài cắt 15 giây kiểu hook và kiểu drop@7s.

| Chỉ số | Kết quả |
|---|---|
| Sai số độ dài | tối đa 0.0 giây |
| Điểm bắt đầu trùng đầu ô nhịp thật (±70 ms) | 100% |
| Điểm bắt đầu nằm trong điệp khúc/drop thật | 83% |
| Drop thật rơi trong ±0,5 giây quanh giây 7 | 75% |
| Tốc độ nghe | 1.09 giây cho mỗi phút nhạc |

## Giới hạn của phép đo

* Bài kiểm tra là nhạc tổng hợp có nhãn tuyệt đối (do chính Micow dựng rồi trộn lại); chưa đo trên bộ nhạc thật có nhãn.
  Nút **Đúng hook** trên trang Nhạc CapCut ghi nhãn bài thật của bạn, `micow train ear` sẽ học thêm từ đó.
* Phần B, C đo độ chính xác thời gian/âm lượng – không đo "hay" hay không; cái đó cần người nghe.
