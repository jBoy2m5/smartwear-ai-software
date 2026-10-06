# Kết quả kiểm chứng — 05/10/2026

## Đã chạy và đạt

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Python hardware + backend | **48 passed, 2 subtests passed** | [tests.log](tests.log) |
| Firmware SmartCap | **SUCCESS**, RAM 49,624 / 327,680 B, Flash 861,493 / 3,145,728 B | [firmware-build.log](firmware-build.log) |
| Firmware SmartWrist | **SUCCESS**, RAM 45,644 / 327,680 B, Flash 789,445 / 1,310,720 B | [firmware-build.log](firmware-build.log) |
| Frontend TypeScript + Vite | Build thành công | [frontend-build.log](frontend-build.log) |
| MediaPipe thực + model trong repo | Load/suy luận thành công, ảnh đen synthetic không phát hiện tay | [ai-smoke.log](ai-smoke.log) |
| Kiểm tra patch | `git diff --check` thành công | Chạy sau thay đổi code |

Firmware dùng PlatformIO 6.2.0, espressif32 6.9.0, Arduino ESP32 2.0.17, PubSubClient 2.8. Python test dùng 3.12.14, MediaPipe 1.0.1. Vite có cảnh báo bundle >500kB, không làm build thất bại.

## Phạm vi test

Parser MQTT/MJPEG; raw payload và receipt time; mất seq/reset; ghép measured và hash; thiếu mẫu không sinh DEMO; buffer 100 mẫu, biên 10ms, mẫu tương lai, xóa buffer khi reset; hợp đồng handoff BGR; NTP origin/mode; retry hardware giữ provenance; failure manifest; API, capture manager, xuất artifact backend.

Test mới có chạy **MediaPipe thật trên ba ảnh JPEG synthetic**, qua `record_hardware`, callback multimodal, JSON/video/manifest. Nguồn camera/MQTT trong test này được thay bằng fixture cục bộ. Điều này kiểm tra pipeline phần mềm, **không phải thử nghiệm trên ESP32**. Test fixtures không được đưa vào thư mục session đo thật.

## Chưa đạt điều kiện chạy thiết bị thật

| Kiểm tra thực tế | Kết quả |
|---|---|
| IP Wi-Fi máy làm việc | `10.41.22.38`, khác mạng thiết bị |
| SmartCap `.111:81` | TCP timeout |
| MQTT `.107:1883` | TCP timeout |
| NTP `.107:123/UDP` | Timeout |
| USB serial | Người dùng xác nhận SmartWrist COM7 (CP210x), SmartCap COM5 (CH340) |
| Nạp firmware | SmartWrist COM7 và SmartCap COM5: SUCCESS, hash verified; xem smartwrist-upload.log và smartcap-upload.log |
| Broker/NTP trên .107 | Đã cung cấp cấu hình/lệnh; chưa khởi chạy được trên máy đích |
| Thu phiên đo thật end-to-end | Chưa thực hiện |

Chi tiết: [preflight.json](preflight.json), [serial-ports.log](serial-ports.log). Kết quả phản ánh thời điểm kiểm tra, không kết luận thiết bị hỏng.

## Điều kiện để nghiệm thu phần cứng

1. Xác định `.107` là máy này sau khi đổi Wi-Fi hay máy Layer 3 khác; chạy dịch vụ trên đúng máy.
2. Xác định cổng USB từng bo, nạp đúng target; xác nhận nguồn/PSRAM/pinout và NTP.
3. Thu ≥60 giây raw thật, kiểm tra JSON/header, tốc độ và seq/reset/drop counters.
4. Thu/ghép/AI một phiên measured; kiểm tra matched/missing và max/p95 offset, ảnh/video/metadata.
5. Đo latency và sai lệch đồng hồ độc lập, kiểm thử chịu mất Wi-Fi/broker, đo lực để hiệu chuẩn nếu cần Newton.

Các mục F1>88%, TCN/ensemble trained, 25–30FPS thực, 50Hz thực, LAN<5ms, clock gap≤10ms, BOM/trọng lượng và robot calibration chưa được chứng minh trong đợt làm việc này.
