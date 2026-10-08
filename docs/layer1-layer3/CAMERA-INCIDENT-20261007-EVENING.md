# Camera timeout — phiên tối 07/10/2026

Job `2298f986b42e48bb9eaa5072ed9d6ca5` thất bại lúc 20:11 giờ Việt Nam với `ESP32 camera did not supply a valid JPEG within 15 s`. Session raw `hardware_20261007_201131_822665_moubf91v` được giữ nguyên. `camera_raw.mjpeg`, `camera_packets.jsonl`, `camera.jsonl` và `wrist_raw.jsonl` đều **0 byte**; `inferred_frames=0`.

Log ghi camera `<urlopen error timed out>` và SmartWrist `MQTT wrist topic unavailable at 192.168.137.1:1883`. Kiểm tra cùng thời điểm: máy không có IP hotspot `192.168.137.1` (hai Wi-Fi Direct virtual adapters disconnected, chỉ có Wi-Fi `192.168.1.161` và WARP), `icssvc` dừng, không có listener MQTT 1883 hoặc NTP UDP123, camera `192.168.137.111:81` không kết nối được. Backend 8000 vẫn `ready`. **Nguyên nhân trước mắt là mạng hotspot/dịch vụ thu đã tắt**, chưa có bằng chứng camera hỏng hoặc JPEG sai định dạng.

Đã thêm preflight vào `CaptureManager`: khi bấm quay hardware mà máy chưa có `.1`, API trả lỗi hướng dẫn bật Mobile Hotspot `ok123` 2.4 GHz trước khi tạo job; khi camera chưa mở cổng 81, API báo kiểm nguồn/kết nối SmartCap. Hai kiểm thử cho trạng thái mất hotspot/mất camera đạt; bộ kiểm liên quan **17 passed**, `git diff --check` đạt. Backend đã nạp mã mới; `/ready` trả `ready`.

Khôi phục theo thứ tự sau khi người dùng bật lại hotspot:

1. Kiểm máy có `192.168.137.1`, SmartCap `.111`, SmartWrist `.100`. Không mở serial khi đang quay.
2. Khởi động MQTT và NTP trên máy `.1` theo [RUNBOOK.md](RUNBOOK.md); tránh mở trùng cổng.
3. Chạy `ai/hardware/preflight.py` vào báo cáo mới; kết nối TCP/NTP đạt mới thử raw ngắn và kiểm JPEG thực.
4. Chỉ khi ảnh rõ và wrist phát dữ liệu mới thử quay dashboard. Không thay vai trò/consent hoặc gán session lỗi thành mẫu expert.

Đến lúc ghi tài liệu, hotspot vẫn chưa được bật lại; chưa có phép thử camera/MQTT/NTP sau khôi phục.

Preflight cuối lúc 20:19 vẫn báo camera TCP, MQTT TCP và NTP timeout khi chạy ngoài sandbox; dependencies phần mềm đều có. Xem [camera-incident-preflight.json](camera-incident-preflight.json). Lượt chạy trong sandbox trước đó trả WinError 10013 do hạn chế socket của môi trường, đã được chạy lại ngoài sandbox để xác minh timeout thật.

## Sau khi bật lại hotspot

- Máy có `192.168.137.1`, camera `.111:81` mở. Đã khởi động MQTT và NTP nền; preflight mới [camera-incident-recovery-preflight.json](camera-incident-recovery-preflight.json) đạt camera TCP, MQTT TCP, NTP và dependencies.
- Raw thử 10 giây `hardware_raw_20261007_202546_973933_wp0187wm` đạt `raw_complete`: **179 JPEG, 501 wrist samples**, tốc độ 17,871 FPS và 50,02 Hz; không có camera stream error, wrist seq gap hoặc malformed MQTT được ghi nhận. Raw và hash được giữ trong session riêng.
- Đã giải mã ảnh JPEG ở giữa phiên. Ảnh hợp lệ, sáng, nhưng camera hiện hướng vào **khuôn mặt**, chưa thấy bàn/tay/vật thao tác. Preview riêng tư được lưu cục bộ ở `backend/data/recovery-preview.jpg` (không đưa vào docs/Git). Cần chỉnh góc xuống vùng thao tác trước khi quay expert A/B.
- SmartWrist IMU vẫn unavailable cả 501 mẫu; ADC kênh 4 bằng 0 trong lượt này. Không coi hai hạn chế này đã được sửa chỉ vì stream đã phục hồi.
- Backend `/ready` trả `ready`; chưa thử quay expert qua dashboard sau lượt raw vì khung hình chưa phù hợp. Không mở serial trong lúc thu.
