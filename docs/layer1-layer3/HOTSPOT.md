# Mobile Hotspot — 06/10/2026

Cấu hình mới đã lưu trong firmware, Python collector, NTP server, Mosquitto config và script môi trường:

| Thành phần | Cấu hình |
|---|---|
| SSID | `ok123` (không có dấu cách cuối) |
| Password | Đã cập nhật trong `firmware/include/secrets.h` cục bộ |
| Băng tần hotspot | 2.4 GHz |
| Máy Windows tạo hotspot, MQTT/NTP/AI | `192.168.137.1` |
| SmartWrist | `192.168.137.100`, COM7 |
| SmartCap | `192.168.137.111`, COM5, stream port81 |
| Netmask | `255.255.255.0` |

Gateway Windows là `.1`; firmware có `GATEWAY_HOST` dùng chung cho MQTT và NTP. Chuyển SSID/subnet đòi nạp lại firmware của cả hai bo. Firmware đã nạp ở phiên trước còn dùng mạng cũ cho đến khi nạp bản mới.

## Chạy từ PowerShell trong repo

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
. .\deployment\hardware.ps1
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v
```

Đóng Serial Monitor, cắm hai bo rồi nạp đúng cổng đã xác nhận:

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartwrist -t upload
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartcap -t upload
```

`platformio.ini` đã lưu đường dẫn toolchain trong repo, COM7 cho wrist và COM5 cho cap; terminal mới không cần đặt `PLATFORMIO_CORE_DIR` riêng. Nếu Windows gán cổng khác, cập nhật port hoặc dùng `--upload-port`.

Bật Windows Mobile Hotspot với SSID `ok123`, mật khẩu đã cung cấp, 2.4GHz. `ipconfig` cần hiển thị adapter hotspot có `192.168.137.1`; adapter Wi-Fi upstream vẫn có IP riêng. Chạy MQTT và NTP trong hai terminal trên **chính máy tạo hotspot**:

```powershell
& 'C:\Program Files\mosquitto\mosquitto.exe' -c .\deployment\mosquitto.conf -v
```

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\ntp_server.py
```

Restart dịch vụ đang dùng cấu hình mạng cũ. NTP và MQTT là hai dịch vụ khác nhau; hotspot không tự cung cấp broker hay NTP. Firewall cần cho phép TCP1883/8000 và UDP123 từ `192.168.137.0/24`; lệnh cụ thể trong RUNBOOK. Các rule cũ cho `192.168.0.0/24` không đủ cho subnet mới.

Reset hai bo sau khi dịch vụ sẵn sàng, rồi kiểm tra:

```powershell
. .\deployment\hardware.ps1
.\.venv\Scripts\python.exe -B ai\hardware\preflight.py --output docs\layer1-layer3\hotspot-preflight.json
.\.venv\Scripts\python.exe -B ai\hardware\raw_capture.py --duration-s 60
```

Dashboard: chạy `deployment/start-backend.ps1`, mở `http://192.168.137.1:8000/`.

## Trạng thái lần sửa này

Máy hiện tại không liệt kê COM5/COM7 khi kiểm tra và chưa thấy adapter hotspot `.1`. Vì vậy chỉ xác nhận thay đổi code/build/test; chưa nạp hoặc nghiệm thu kết nối thật với cấu hình mới. Các log phiên cũ và dữ liệu session lịch sử giữ nguyên IP đã thu để bảo toàn provenance.

Kiểm chứng ngày 06/10/2026: hai target firmware build SUCCESS ([hotspot-firmware-build.log](hotspot-firmware-build.log)); **48 test và 2 subtest đạt** ([hotspot-tests-verified.log](hotspot-tests-verified.log)). Cổng camera, MQTT và NTP mới đều timeout ([hotspot-preflight.json](hotspot-preflight.json)).
