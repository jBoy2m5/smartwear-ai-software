# Hợp đồng dữ liệu đang triển khai

## Layer 1

SmartCap chỉ có OV2640, không MPU6050. AI-Thinker pinout dùng trong `firmware/src/smartcap.cpp`; JPEG QVGA 320×240, quality 12, PSRAM hai buffer, grab latest. HTTP port 81 chỉ một consumer; dashboard dùng preview từ backend, không mở thêm stream trên camera.

Mỗi phần MJPEG có `Content-Type: image/jpeg`, `Content-Length`, `X-Timestamp-Ms`, `X-Frame-Seq`. Timestamp lấy từ `camera_fb_t.timestamp` (mốc DMA từ lúc boot) rồi chuyển sang epoch bằng anchor NTP. Không dùng thời điểm gửi/nhận ảnh làm thời điểm chụp. Chưa sync NTP trả 503. Seq tăng toàn boot, không reset khi nối lại HTTP.

SmartWrist: MPU6050 address `0x68`, SDA21/SCL22, VCC3V3, GND chung, AD0 nối GND. FSR phân áp 0–3.3V trên ADC1 GPIO32/33/34/35 theo thứ tự `force[0..3]`. Theo đặc tả: ngón cái, trỏ, giữa, áp út/lòng bàn tay; **cần kiểm tra đúng dây thực tế**. Không cấp tín hiệu analog 5V vào ESP32.

Firmware đặt MPU6050 ±2g, ±250°/s; acc chia 16384 (g), gyro chia 131 (°/s), burst 14 byte. Chu kỳ task 20 ms, MQTT task riêng để reconnect không chặn lấy mẫu. Queue 100, bỏ backlog cũ hơn 200 ms, QoS0/retain false; seq gap bộc lộ mất mẫu. Tốc độ thực phải đo từ phiên thu.

```json
{"t_ms":1791110000000,"seq":123,"acc":[0.01,0.02,1.0],"gyro":[0.0,0.0,0.0],"force":[120,340,560,780]}
```

Ví dụ này minh họa format, không phải mẫu thật. Mỗi lần publish một object UTF-8 lên `wearable/user01/wrist/data`, broker `.1:1883`. Receiver giới hạn 4096 byte; epoch nguyên ≥1577836800000; seq nguyên ≥0; acc/gyro đúng ba số hữu hạn; force đúng bốn **số nguyên JSON** 0..4095 (không nhận 1.0/boolean). Thiếu dữ liệu không thay bằng số giả.

Firmware mới xác định đơn vị g/°/s qua code, nhưng metadata AI vẫn giữ `firmware_acc_raw_unverified`/`firmware_gyro_raw_unverified` cho tới khi xác nhận bo thực đang chạy đúng firmware này. ADC không phải Newton/sEMG. Không tự nhận dạng phiên firmware từ IP.

## Layer 2 → Layer 3

Callback `record_hardware(..., on_multimodal=handler)` nhận:

```python
{
    "frame_id": camera_seq,
    "t_ms": camera_epoch_ms,
    "delta_ms": abs(wrist_epoch_ms - camera_epoch_ms),
    "frame": frame_bgr_ndarray,   # ảnh gốc trước mirror cho MediaPipe
    "wrist": {"seq": wrist_seq, "acc": [ax, ay, az],
              "gyro": [gx, gy, gz], "force": [f0, f1, f2, f3]},
    "head": None
}
```

Đây là đối tượng trong tiến trình, không JSON truyền qua HTTP. Khi thiếu mẫu: `wrist=None`, `delta_ms=None`. Callback phải nhanh; consumer nặng cần queue riêng. Callback lỗi làm phiên thất bại, dữ liệu raw vẫn còn.

Online có buffer 100 mẫu, chờ tối đa 40 ms để nhận mẫu phía sau thời điểm camera rồi chọn gần nhất. **40 ms ở đây là thời gian chờ mạng, không phải ngưỡng ghép**. Ngưỡng chấp nhận mặc định ±10 ms, biên 10 được nhận, 11 bị loại. Mẫu quá cũ và reset không được tái sử dụng. Nếu AI chậm hơn cửa sổ buffer, online có thể missing; ghép offline vẫn dùng raw toàn phiên.

Offline tạo một dòng `real_sensors.jsonl` cho mỗi frame chuẩn hóa; ngoài ngưỡng thì giá trị sensor `null`. Toàn phiên không có mẫu khớp hoặc có wrist reboot/clock reset: xử lý thất bại, không fallback simulator. Camera clock/seq giảm: yêu cầu bắt đầu phiên mới.

## File output

| File | Nội dung |
|---|---|
| `camera_raw.mjpeg` + `camera_packets.jsonl` | JPEG nguyên gốc, offset, length, SHA256, epoch/seq nguồn và giờ nhận |
| `wrist_raw.jsonl` | Payload gốc, trường đã kiểm tra, topic, giờ nhận, generation |
| `hardware_capture.json` | Cấu hình, trạng thái, số mẫu, lỗi, tốc độ |
| `camera.jsonl` + `camera.avi` + manifest | Quan sát tay phải, ảnh AI, nguồn giờ, thông tin ghép online |
| `camera.normalized.jsonl` | `smartwear.camera.v2` |
| `real_sensors.jsonl` + `.meta.json` | `smartwear.sensors.v2`, hash, matched/missing, offset, đơn vị |
| `multimodal.jsonl` | `smartwear.multimodal.v2`, measured provenance |
| `action_segments.json`, `keyframes.json`, `keyframes/` | Quan sát thao tác và ảnh đại diện |
| `session_role.json`, `analysis_result.json` | Vai trò; phân tích so sánh nếu có phiên tham chiếu |
| `backend_payload_measured.json` + receipt | Dữ liệu AI → backend, khác hoàn toàn MQTT input |

`imu_head`/torque/force Newton không có nguồn đo nên để null; robot trajectory rỗng khi chưa hiệu chuẩn. Mẫu DEMO được giữ riêng và ghi nguồn mô phỏng. Action/MUDA là suy đoán cần người kiểm tra.

## Giới hạn đồng hồ

`ntp_server.py` phát đồng hồ Windows của `192.168.137.1` với stratum10/offline; không tuyên bố UTC chuẩn. Firmware khóa anchor khi NTP hợp lệ lần đầu, dùng monotonic để tránh bước nhảy giữa phiên. Clock drift trong thời gian dài vẫn tồn tại: reboot/re-sync trước đợt đo và nghiệm thu offset thực trên hai bo. Delta ghép ≤10 ms không chứng minh sai số đồng hồ hay LAN latency <5 ms.

Nguồn API đã đối chiếu: [Espressif camera timestamp](https://github.com/espressif/esp32-camera/blob/v2.0.4/driver/include/esp_camera.h), [Arduino ESP32 HTTP camera example](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/ESP32/examples/Camera/CameraWebServer/app_httpd.cpp). Build cố định PlatformIO espressif32 6.9.0 / Arduino 2.0.17.
