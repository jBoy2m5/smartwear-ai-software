# Trạng thái thiết bị, hiệu suất và thí nghiệm học việc — 09/10/2026

## Đã triển khai

- `/api/v1/capture/devices` kiểm camera, MQTT và NTP có cache 5 giây. Trạng thái cổng TCP được phân biệt với camera/clock đã khởi tạo; chưa khẳng định ảnh hoặc sensor hợp lệ trước khi quay.
- SmartCap có HTTP chẩn đoán riêng `:82/status`, boot ID, reset reason, uptime, RSSI, camera init status, NTP và sequence. Multipart JPEG giữ boot ID/reset reason; receiver không ghép dữ liệu qua hai lần khởi động. Không tắt brownout protection.
- Firmware mới đã build/upload SmartCap COM5, MAC `30:76:f5:e5:66:d8`, hash flash verified. Endpoint status đã phản hồi cả khi port 81 đang stream.
- Model được tạo và warm-up trước khi thu. Bộ thu dừng trước khi đóng model, tránh thu tiếp và bỏ ảnh ở cuối phiên. Preview vẫn encode/write trên luồng riêng, mục tiêu 10 Hz, chất lượng JPEG 80; browser hỏi tối đa khoảng 10 Hz và giảm khi tab bị ẩn.
- Giao diện phân biệt đang chuẩn bị, có thể kết nối, thiếu thiết bị, ảnh cũ, không thấy tay và phiên đã dừng. Không hiển thị LIVE/trạng thái vòng tay hiện tại từ ảnh cũ hoặc phiên lỗi.
- `performance.json` giữ thời gian model ready, capture start, first inference và từng bước decode/alignment/inference/write/preview submit. Đồng hồ `perf_counter` dùng cho đo chi tiết; percentile giữ tối đa 2048 mẫu, tổng số/mean/max giữ cả phiên. Thời gian thu và cleanup được báo riêng.

## Kiểm chứng

- Suite Python đầu tiên: 77 passed, 14 subtests passed. Sau thêm regression API/source hash: 45 targeted tests + 6 subtests passed. Kiểm cuối thứ tự dừng: 10 deployment tests passed.
- Frontend TypeScript/Vite build đạt; cảnh báo bundle lớn còn tồn tại. `git diff --check` đạt.
- Backend đã restart khi không có capture; log `backend/data/improvements-backend.*.log`; `/ready` phản hồi ready. Các endpoint thiết bị và danh sách thực nghiệm đã phản hồi.
- Browser automation không khởi tạo được (`helper_unknown_error: setup refresh had errors`). Chưa xác minh bố cục hoặc thao tác trực quan bằng browser; build/API/tests không thay thế phần đó.

## Hiệu suất đo thật

Baseline 20 giây: `hardware_20261009_111435_295780_stodp8sk`: 336 JPEG, 324 inferred, 6 dropped_for_inference, 6 ảnh còn trong queue khi dừng. Source khoảng 16,26 FPS.

Lượt sau thay đổi firmware đầu tiên có các khoảng trống JPEG dài; raw không chạy AI cũng tái hiện. Đã thêm TCP_NODELAY cho stream socket và kiểm lại. Không quy mọi thay đổi tốc độ cho AI hoặc khẳng định nguyên nhân vật lý từ phép thử này.

Lượt bản cuối: `hardware_20261009_114208_401398_b97nj0sz`: 315 JPEG, 312 inferred, **0 dropped_for_inference**, 3 ảnh còn trong queue khi dừng; 1000 wrist samples. AI khoảng **15,59 FPS**, wrist **49,96 Hz**; inference p95 **50,877 ms**, frame processing p95 **53,846 ms**; không stream error/reset được ghi nhận trong lượt này. Lượt đó có kiểm thử fixture AI chạy đồng thời vài giây đầu, nên không dùng làm benchmark tăng FPS có kiểm soát.

Raw/JPEG/session lịch sử được giữ nguyên. Báo cáo chi tiết: `backend/data/performance-before.json`, `performance-after.json`, `performance-final.json`, `performance-verified.json`; tổng hợp `performance-comparison.json`. Nhiều lượt live khác khung hình/tải máy nên không công bố phần trăm tăng tốc từ chúng. Chưa nghiệm thu 25–30 FPS, clock accuracy hoặc ổn định dài hạn.

## Thí nghiệm học việc

Đã bổ sung form conditions note, xác nhận đã xem SOP và số lỗi được người đánh giá xác nhận. API `/knowledge/learning-trials` và `/knowledge/learning-experiment` so sánh hai phiên được chọn rõ; kiểm cùng participant/task/version/reference/review revision và điều kiện, review/consent/outcome/số lỗi/gợi ý/mốc thao tác. Không tự chọn một cặp hay tự điền số liệu.

Mỗi bản review mới pin SHA256 archive nguồn; báo cáo kiểm lại hash của mẫu, trước và sau. Thiếu gate hoặc archive đổi thì không tính chênh lệch. Báo cáo giữ cả đầu ra không đạt; cải thiện thời gian phải được đọc cùng chất lượng/số lỗi/gợi ý.

Hướng dẫn: [LEARNING_EXPERIMENT.md](demo-kit/LEARNING_EXPERIMENT.md). `deployment/export-learning-evidence.py` tải báo cáo và kiểm archive bằng checksum/size, xuất snapshot mới. Tests dùng fixture tổng hợp, không phải kết quả học việc thật.

**Chưa hoàn tất thí nghiệm bằng người.** Danh sách learning-trials trên backend hiện rỗng; chưa nhận xác nhận người hướng dẫn/người học/vật dụng. Cần thực hiện reference → before → xem SOP → after → human review theo quy trình trên. Không đổi benchmark kỹ thuật hoặc phiên lịch sử thành expert/worker để tạo kết quả.
