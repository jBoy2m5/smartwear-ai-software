# Kiểm tra thực tế ngày 06/10/2026, buổi tối

## Phần mềm và dịch vụ

- Đã đọc tài liệu dự án và đối chiếu firmware, collector, capture API, AI bridge, frontend.
- Backend/dashboard chạy tại http://127.0.0.1:8000/; `/health`, `/ready`, trang gốc và API dashboard trả HTTP 200.
- MQTT PID 24884 nghe 192.168.137.1:1883; NTP nghe 192.168.137.1:123. Đây là tiến trình phiên làm việc, chưa cài tự khởi động Windows.
- Python: 49 test, 4 subtest đạt. Sửa fixture test dừng quay để ghi status bằng atomic replace giống worker thật, tránh đọc JSON đang ghi dở.
- Frontend TypeScript/Vite build đạt; lint còn một cảnh báo setState trong effect ở RealtimeCharts.tsx. Bundle JS khoảng 636 kB trước gzip.
- Model MediaPipe trong repo tải và suy luận đạt với ảnh thử đen; chưa phải benchmark độ chính xác.
- Hai firmware build và upload thành công, hash flash verified.

## Phần cứng

- Windows nhận SmartCap ở COM5, không phải COM4. Đã xác nhận bằng log `SmartCap: http://192.168.137.111:81/stream` và MAC 30:76:f5:e5:66:d8.
- SmartWrist ở COM7, MAC 68:09:47:df:56:00.
- Sau khi bật hotspot và chạy MQTT/NTP, lượt thu đầu 60 giây có 0 JPEG, 0 wrist; camera trả HTTP 503 (chưa NTP).
- Sau nạp/reset, SmartCap gửi JPEG thật khoảng 18 FPS trong lượt raw 15 giây; SmartWrist vẫn 0 mẫu.
- Log reset SmartWrist báo **`MPU6050 missing at 0x68`**. Firmware dừng ở bước này trước khi khởi động Wi-Fi/MQTT. Cần kiểm tra cảm biến, nguồn và dây: SDA21, SCL22, VCC3.3V, GND chung, AD0 nối GND; xác nhận loại IMU và chân thực nếu khác.

## Camera → AI → API xem trước

- Đã gọi capture hardware qua API; job `90b59386caa44b1381a8454bf4ae2044` chuyển recording, trả JPEG 320×240 và metadata MediaPipe cùng frame.
- Quan sát frame 128 tại 8498 ms: `NO_HAND`, wrist missing, delta null. Ảnh thực gần như đen; cần hướng camera vào vùng sáng/tay phải để kiểm tra nhận diện thao tác.
- Đã gọi stop để giải phóng camera. Chưa nghiệm thu phiên measured hoàn chỉnh vì không có dữ liệu SmartWrist; không thay bằng sensor mô phỏng.
- Kiểm tra được HTML/API/JPEG; môi trường không cung cấp trình duyệt điều khiển nên chưa kiểm tra trực quan dashboard trong browser.

## Bằng chứng

- `current-preflight.json`: camera TCP, MQTT và NTP đạt sau reset; chỉ chứng minh kết nối dịch vụ.
- `ai/generated_data/sessions/hardware_raw_20261006_182843_695291_qo9zc1ss`: lượt raw 60 giây ban đầu.
- `ai/generated_data/sessions/hardware_20261006_183414_838765_5p36fcph`: lượt AI timeout trước reset bổ sung.
- `ai/generated_data/sessions/hardware_raw_20261006_183619_826769_1ftaxau6`: camera khoảng 18 FPS, wrist vắng.
- `ai/generated_data/sessions/hardware_20261006_183643_821797_zvnhjy8p`: lượt capture từ API.
- `backend/data/verification-preview.jpg`: ảnh xem trước đã kiểm tra.

## Chạy lại

Nếu PowerShell chặn `.ps1`, dùng `powershell.exe -NoProfile -ExecutionPolicy Bypass -File deployment/start-backend.ps1` (chỉ áp dụng cho tiến trình này).
Đọc log bằng `.venv\Scripts\python.exe deployment/read-serial.py COM5 COM7 --reset` khi không đang thu; tùy chọn `--reset` khởi động lại bo.
Sau khi sửa MPU6050, thu lại ít nhất 60 giây và xác nhận JPEG, MQTT, ghép ±10 ms, AI, publish và hiển thị kết quả. Chưa chứng minh KPI 25–30 FPS, 50 Hz, sai lệch đồng hồ, độ chính xác AI, Newton hoặc tọa độ robot.
