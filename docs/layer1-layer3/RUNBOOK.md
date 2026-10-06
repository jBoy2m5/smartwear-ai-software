# Chạy trên máy Layer 3 192.168.137.1

## 1. Chuẩn bị môi trường

Mở PowerShell trong repo. Dùng Python 3.12 64-bit trên máy đích. `.venv` hiện có trên máy làm việc đã được cài và kiểm thử; venv không di chuyển được giữa máy. Không dùng `ai/.venv` cũ: nó trỏ Python trên máy `jboyn` không còn ở đây.

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ai\requirements-hardware.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt pytest platformio==6.2.0
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
```

Nếu máy này không có `py -3.12`, cài Python 3.12 hoặc dùng đường dẫn Python thực đã cài. Đừng ghi đè một venv đang được chương trình khác sử dụng.

## 2. Mạng và dịch vụ Layer 2

Bật Windows Mobile Hotspot trên máy chạy AI, SSID `ok123`, mật khẩu theo file secrets cục bộ, băng tần **2.4 GHz**. Máy chủ có IP adapter hotspot `192.168.137.1`; hai bo kết nối vào hotspot, dùng IP tĩnh SmartWrist `192.168.137.100`, SmartCap `192.168.137.111`. Kiểm tra hai địa chỉ tĩnh không bị client khác dùng. Không cần đổi IP của adapter Wi-Fi upstream thành `.1`. Xem [HOTSPOT.md](HOTSPOT.md).

Cài Mosquitto trên máy đích, sau đó chạy foreground trong một terminal:

```powershell
& 'C:\Program Files\mosquitto\mosquitto.exe' -c .\deployment\mosquitto.conf -v
```

Nếu dịch vụ Mosquitto đã chiếm 1883, cấu hình dịch vụ hiện có thay vì mở broker thứ hai. Config cung cấp chỉ bind `192.168.137.1`, anonymous cho LAN riêng theo đặc tả; không forward ra Internet.

Terminal NTP riêng (giữ mở):

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\ntp_server.py
```

NTP này dùng giờ Windows để làm mốc chung trong LAN, không cần Internet. Kiểm tra giờ máy đúng trước khi chạy. Nếu Windows Time/Chrony đã nghe UDP123, dùng một dịch vụ NTP duy nhất. Lỗi bind nghĩa IP chưa thuộc máy hoặc cổng đang bị chiếm.

Nếu firewall chặn, trên **máy đích 192.168.137.1** dùng PowerShell Administrator:

```powershell
New-NetFirewallRule -DisplayName 'SmartWear MQTT LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1883 -RemoteAddress 192.168.137.0/24
New-NetFirewallRule -DisplayName 'SmartWear NTP LAN' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 123 -RemoteAddress 192.168.137.0/24
New-NetFirewallRule -DisplayName 'SmartWear Dashboard LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -RemoteAddress 192.168.137.0/24
```

Các lệnh firewall là hướng dẫn cho máy đích; chưa được chạy trên máy làm việc hiện tại.

## 3. Build và nạp firmware

Người dùng đã xác nhận: **SmartCap = COM5 (CH340)**, **SmartWrist = COM7 (CP210x)**. `firmware/platformio.ini` đã lưu cả `upload_port` và `monitor_port` cho từng target, baud monitor 115200. Khi bo vẫn dùng các cổng này, có thể bỏ `--upload-port`:

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartcap -t upload
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartwrist -t upload
.\.venv\Scripts\python.exe -m platformio device monitor -d firmware -e smartcap
.\.venv\Scripts\python.exe -m platformio device monitor -d firmware -e smartwrist
```

Chạy mỗi monitor ở terminal riêng và nhấn Ctrl+C đóng monitor trước khi nạp lại bo tương ứng.

Nếu terminal mới báo `UnknownPlatform: espressif32@6.9.0`, đặt lại `$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location) '.platformio'`. Biến môi trường này chỉ thuộc terminal hiện tại. Có thể dùng script tự đặt đường dẫn, không cần nhớ biến:

```powershell
.\deployment\monitor.ps1 -Device smartwrist
# Terminal khác:
.\deployment\monitor.ps1 -Device smartcap
```

`firmware/include/secrets.h` cục bộ đã có SSID/password theo tài liệu. Khi chuyển qua Git, phải tạo lại từ `secrets.example.h`, nhập mật khẩu tại máy đích. SSID mới không có dấu cách cuối. Kiểm tra đúng board AI-Thinker và ESP32-WROOM.

```powershell
$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location) '.platformio'
.\.venv\Scripts\python.exe -m platformio run -d firmware
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v
```

Sau khi xác định cổng của từng bo (thay `COM_CAP`/`COM_WRIST` bằng cổng thật):

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartcap -t upload --upload-port COM_CAP
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartwrist -t upload --upload-port COM_WRIST
.\.venv\Scripts\python.exe -m platformio device monitor --port COM_WRIST --baud 115200
```

Không nạp dựa vào tên USB bridge: CP210x không chứng minh đó là bo nào. Camera dùng nguồn 5V ổn định/MB, có PSRAM. Chân cảm biến theo [CONTRACT.md](CONTRACT.md). Sau nạp, reboot hai bo để lấy anchor NTP từ `192.168.137.1`.

## 4. Kiểm tra dữ liệu thật

```powershell
. .\deployment\hardware.ps1
.\.venv\Scripts\python.exe -B ai\hardware\preflight.py
.\.venv\Scripts\python.exe -B ai\hardware\raw_capture.py --duration-s 60
```

Preflight chỉ thử TCP/NTP; không chiếm luồng camera. Raw capture mới chứng minh nhận đúng payload/header. Không mở `/stream` trong browser trong lúc collector chạy. Kiểm tra `raw_capture.json`: có JPEG, có wrist, không malformed/reset; đối chiếu một dòng `wrist_raw.jsonl` với Serial/firmware.

NTP lỗi/503: kiểm tra server UDP123/firewall/SSID đúng và reboot thiết bị sau khi server sẵn sàng. MQTT connects nhưng received=0: kiểm tra firmware đang publish tới `.1:1883` và topic đúng; `.100` không phải broker.

## 5. Ghi → xử lý Layer 3

Ghi mẫu chuyên gia đo thật trước:

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --role expert
```

Ghi công nhân và so với thư mục mẫu vừa tạo:

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --role worker --expert-session .\ai\generated_data\sessions\TEN_PHIEN_EXPERT
```

Không chỉ định role thì hành vi có sẵn là chọn reference DEMO đi kèm; kết quả sẽ ghi nguồn khác nhau. Dùng `--role expert/worker` để có quy trình tham chiếu đo thật. `--force-channel 0..3` chỉ khi đã chọn kênh lực đại diện; bỏ tham số vẫn lưu đủ bốn ADC. `--window-ms` cho phép override có ghi metadata; yêu cầu dự án là giữ **10 ms**.

Output tự lưu trong `ai/generated_data/sessions/hardware_.../`. `--process --publish` thêm bước gửi backend. Khi phiên lỗi, raw giữ lại; không sửa marker thành complete để ép dữ liệu qua pipeline. Lệnh xử lý lại không ghi đè output đã tồn tại.

## 6. Dashboard

```powershell
.\deployment\start-backend.ps1
```

Mở `http://192.168.137.1:8000/` trên LAN hoặc `http://127.0.0.1:8000/` trên chính máy đích. Bấm Bắt đầu quay/Kết thúc. Backend tự dùng hardware mode, thu tối đa 180 giây, phân tích và lưu kết quả. Preview hiển thị lực ADC và độ lệch ghép; không có mẫu phù hợp sẽ báo thiếu.

## 7. Kiểm thử lặp lại

```powershell
.\.venv\Scripts\python.exe -B -m pytest ai\hardware backend\tests -q
.\.venv\Scripts\python.exe -B deployment\verify-ai.py
npm.cmd run build --prefix frontend
$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location) '.platformio'
.\.venv\Scripts\python.exe -m platformio run -d firmware
```

KPI nghiệm thu thật: ghi tối thiểu 60 giây, đếm tốc độ MQTT và JPEG, matched/missing, max/p95 delta, mất seq, disconnect/reset; đo latency riêng. Mục tiêu 50Hz, 25–30FPS, LAN<5ms và lệch≤10ms không suy ra chỉ từ firmware build thành công. Với camera 25–30FPS, lượng frame AI còn phụ thuộc CPU; raw và AI FPS được báo riêng.
