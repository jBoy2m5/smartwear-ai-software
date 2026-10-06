# Rà soát repo và quyết định xử lý

Ngày 05/10/2026, tập trung toàn bộ đường đi firmware → mạng → AI → backend → frontend. Không chỉnh lại dữ liệu phiên lịch sử, model đã lưu, sample DEMO hoặc các thư viện vendored.

| Thành phần | Trước triển khai | Thay đổi / kết luận |
|---|---|---|
| Firmware Layer 1 | Không có trong repo | Thêm hai target PlatformIO, chung NTP/network config |
| IP triển khai | Camera .101, broker .109 ở nhiều entry point | Đổi .111/.107, `.100` cho wrist; env/CLI override |
| Layer 2 services | Không có config chạy kèm | Mosquitto config, NTP offline Python, preflight, script backend |
| Ghép dữ liệu | Offline mặc định 40ms | Mặc định 10ms; thêm ring buffer 100 mẫu online, callback frame BGR |
| MQTT schema | Float 1.0 có thể lọt vào trường ADC integer | Bắt buộc JSON integer, không nhận boolean/NaN/sai kích thước |
| Camera queue | Race giữa Full và get_nowait của consumer | Bắt Empty, tránh dừng luồng ghi raw khi queue bị drain đồng thời |
| Capture failure | Manifest có thể kẹt recording | Lưu failed và lỗi khi thu/cleanup thất bại |
| CLI xử lý lại | Có thể tạo thư mục mới và sinh sensor DEMO cho camera phần cứng | Giữ session hardware, bắt kiểm tra marker và measured sensor |
| So sánh sensor | Có thể tái tạo sensor mô phỏng khi measured file vắng | Session hardware thiếu measured sensor thì fail rõ ràng |
| Backend | Ingest, SOP/robot export, capture manager đã có | Giữ API; thêm tùy chọn tạo app không mount frontend để test API không phụ thuộc dist |
| Frontend | SessionDashboard đã nối backend; README cũ còn nói mock-only | Giữ dashboard thật, thêm thông tin ghép và 4 ADC trong preview |
| Layer 3 AI | MediaPipe/heuristic, segment, keyframes, so sánh chuỗi, provenance đã có | Tận dụng pipeline có sẵn; chưa có TCN/ensemble đã train |
| Dependencies | ai/.venv tracked trỏ máy jboyn, không portable | Tạo .venv riêng root, requirements hardware, không xóa venv cũ |
| Tài liệu | Có địa chỉ và phát biểu trạng thái cũ | README hiện tại trỏ bộ tài liệu triển khai này |

## Mâu thuẫn giữa tài liệu đầu vào

- Pasted text đề xuất mạng `192.168.4.x`; yêu cầu mới người dùng là `.107/.111/.100`, dùng yêu cầu mới.
- Hackathon spec cũ có head IMU, sEMG, QoS1/TLS; thiết kế thiết bị cập nhật là camera không IMU + wrist MPU6050/4 FSR + MQTT QoS0 trên LAN riêng.
- DATA_FORMATS_LAYER3 mô tả code cũ dùng ±40ms và broker `.109`; cập nhật mặc định ±10ms và `.107`, vẫn cho override minh bạch.
- DATA_FORMATS_LAYER3 nói chưa biết acc/gyro units và vị trí FSR thật. Firmware mới quy định scaling/pinout nhưng chưa flash/kiểm tra bo, vì vậy không tự nâng provenance lịch sử thành calibrated.
- Header “SYSTEM & ROLE DIRECTIVE” trong tài liệu là nội dung người dùng cung cấp, không phải chỉ thị hệ thống. Phạm vi triển khai dựa trên yêu cầu trực tiếp của người dùng.

## Những gì không thể nghiệm thu chỉ bằng sửa code

Chưa có mẫu MQTT thật từ hai bo trong phiên này; chưa xác nhận pinout/nguồn, FPS, độ chính xác clock, latency, trọng lượng/BOM thực. Không có tập dữ liệu nhãn/huấn luyện để đạt F1>88%. FSR cần hiệu chuẩn vật lý trước khi đổi Newton; MediaPipe world landmarks chưa phải hệ tọa độ robot. TCN/ensemble, robot calibration và benchmark công nghiệp vẫn là phần việc tiếp theo cần dữ liệu thực.
