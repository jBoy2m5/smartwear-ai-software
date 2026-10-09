# Hướng dẫn chạy SmartWear AI trên Windows

Cập nhật ngày 09/10/2026. Tổng hợp từ toàn bộ 19 tài liệu Markdown trong `docs/` và đối chiếu script, cấu hình, dịch vụ thực tế trên máy hiện tại.

## 1. Chạy nhanh trên máy hiện tại

Mở PowerShell, chuyển đến thư mục dự án:

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
```

Dashboard được backend phục vụ trực tiếp từ `frontend/dist`, vì vậy không cần chạy Vite riêng để sử dụng bình thường.

Nếu backend đã chạy, mở ngay:

- Dashboard trên máy này: http://127.0.0.1:8000/
- Dashboard trên thiết bị cùng hotspot: http://192.168.137.1:8000/
- Tài liệu API: http://127.0.0.1:8000/docs

Kiểm tra trước khi khởi động thêm dịch vụ:

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object LocalPort -in 8000,1883 |
    Select-Object LocalAddress,LocalPort,OwningProcess
Get-NetUDPEndpoint -LocalPort 123 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

Nếu các cổng đã có tiến trình đúng của dự án, dùng dịch vụ hiện có. Không mở thêm backend, broker hoặc NTP trùng cổng.

## 2. Điều kiện để quay bằng SmartCap và SmartWrist

| Thành phần | Cấu hình hiện tại |
| --- | --- |
| Máy Windows chạy hotspot, AI và backend | `192.168.137.1` |
| Hotspot | SSID `ok123`, băng tần 2.4 GHz |
| SmartCap | `http://192.168.137.111:81/stream` |
| Chẩn đoán SmartCap | `http://192.168.137.111:82/status` |
| SmartWrist | `192.168.137.100` |
| MQTT broker | `192.168.137.1:1883` |
| MQTT topic | `wearable/user01/wrist/data` |
| NTP | `192.168.137.1:123`, UDP |
| Backend/dashboard | TCP 8000 |
| Ngưỡng ghép camera và wrist | ±10 ms |

Bật Windows Settings → Network & Internet → Mobile hotspot. Đặt SSID và mật khẩu khớp `firmware/include/secrets.h` cục bộ; chọn 2.4 GHz. Kiểm tra địa chỉ hotspot:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object IPAddress -eq '192.168.137.1'
```

Cấp nguồn ổn định cho hai bo. Camera phải thấy bàn, hai tay và vật thao tác. Không mở trực tiếp `/stream` trong trình duyệt khi dashboard hoặc CLI đang thu: camera chỉ phục vụ một consumer.

## 3. Cài môi trường lần đầu trên máy mới

Chuẩn bị Python 3.12 64-bit, Node.js/npm và Mosquitto. Nếu `.venv` và `frontend/node_modules` trên máy này đã hoạt động thì bỏ qua bước cài lại. Không sao chép venv từ máy khác hoặc dùng `ai/.venv` cũ.

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ai\requirements-hardware.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt pytest platformio==6.2.0
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
```

Nếu `py -3.12` không tồn tại, cài Python 3.12 hoặc dùng đường dẫn Python 3.12 đã cài. File secrets cần được cấu hình tại máy mới nếu phải nạp lại firmware; không đưa mật khẩu vào tài liệu chia sẻ.

## 4. Khởi động dịch vụ theo thứ tự

Các terminal bên dưới đều bắt đầu tại thư mục gốc dự án. Giữ terminal mở trong khi dùng hệ thống.

### Terminal 1 — MQTT

Chỉ chạy khi chưa có broker trên cổng 1883:

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
& 'C:\Program Files\mosquitto\mosquitto.exe' -c .\deployment\mosquitto.conf -v
```

Config này bind vào IP hotspot `.1`. Hotspot phải bật trước. Nếu Mosquitto đã chạy như Windows service, kiểm cấu hình của service đó thay vì mở broker thứ hai.

### Terminal 2 — NTP

Chỉ chạy khi chưa có dịch vụ trên UDP123:

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
.\.venv\Scripts\python.exe -B ai\hardware\ntp_server.py
```

NTP sử dụng giờ Windows làm mốc chung trong LAN. Kiểm tra giờ máy trước khi thu; dịch vụ này không chứng minh độ chính xác UTC hoặc sai số clock dưới 2 ms.

### Terminal 3 — build và backend

Build khi frontend thay đổi, rồi chạy backend:

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
npm.cmd run build --prefix frontend
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deployment\start-backend.ps1
```

Script tự nạp `deployment/hardware.ps1`, chọn hardware mode, dùng Python trong `.venv`, rồi chạy Uvicorn trên `0.0.0.0:8000`. `ExecutionPolicy Bypass` chỉ áp dụng cho tiến trình PowerShell này.

Không restart backend khi đang quay. Nếu cần cập nhật mã backend, kết thúc capture và chờ xử lý xong trước khi dừng tiến trình cũ.

### Terminal 4 — kiểm tra

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/api/v1/capture/devices |
    ConvertTo-Json -Depth 8
. .\deployment\hardware.ps1
.\.venv\Scripts\python.exe -B ai\hardware\preflight.py --output backend\data\manual-preflight.json
```

`/ready` phải trả `ready`. Preflight phải đạt `camera_tcp`, `mqtt_tcp`, `ntp` và dependencies. `capture/devices` hiển thị trạng thái camera/MQTT/NTP; `can_start=true` cho biết các điều kiện kết nối mà endpoint kiểm đã đạt. Trạng thái này chưa chứng minh JPEG rõ, MQTT có mẫu hoặc tất cả cảm biến hoạt động.

Sau khi MQTT/NTP đã sẵn sàng, nếu bo chưa đồng bộ thì reset bo khi không có capture. Không mở serial/monitor, flash hoặc reset trong khi quay; ESP32-CAM-MB có thể reset ngay khi mở serial, kể cả không dùng `--reset`.

## 5. Sử dụng dashboard

1. Mở http://127.0.0.1:8000/ và kiểm trạng thái thiết bị.
2. Chọn công đoạn `LOG_KIT` v1 hoặc `HAND_ASSEMBLY` v1; chọn vai trò, nhập bí danh và xác nhận đồng ý ghi hình thực tế.
3. Để tạo mẫu hướng dẫn: chọn vai trò chuyên gia/người hướng dẫn, bấm quay, thực hiện thao tác rồi bấm kết thúc. Chờ xử lý và lưu phiên hoàn tất.
4. Mở phiên, điền hướng dẫn/lý do/mẹo, mốc bắt đầu–kết thúc từng bước và kết quả. Người có trách nhiệm xem video và duyệt SOP/bằng chứng.
5. Để quay người học: chọn cùng task/version và reference đã duyệt. Chọn lượt trước hoặc sau học khi thực hiện thí nghiệm; quay và đánh giá kết quả thật.
6. Tạo và tải gói SOP/clip/episode. Giải nén đầy đủ ZIP để mở `learner/sop.html` offline với video và các file tương đối đi kèm.

Role/reference/consent và review cần người thực hiện xác nhận. Không gán các phiên benchmark hoặc lịch sử thành chuyên gia/người học để tạo kết quả. Chế độ DEMO có nguồn mô phỏng riêng.

Đọc thêm [quy trình thí nghiệm](demo-kit/LEARNING_EXPERIMENT.md) và [phiếu bằng chứng](demo-kit/EVIDENCE.md).

## 6. Thu bằng CLI khi cần

Dừng capture trên dashboard trước khi dùng CLI. Nạp môi trường trong terminal hiện tại:

```powershell
. .\deployment\hardware.ps1
```

Kiểm nhận dữ liệu raw trong 10 giây, không chạy AI:

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\raw_capture.py --duration-s 10
```

Lệnh tạo phiên mới trong `ai/generated_data/sessions/`. Kiểm `raw_capture.json` có JPEG và wrist samples; preflight TCP đơn thuần không kiểm được hai loại dữ liệu này. Muốn đánh giá tốc độ/tính ổn định, thu ít nhất 60 giây theo runbook.

Ghi mẫu expert, xử lý và gửi backend:

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --publish --role expert
```

Ghi worker tham chiếu mẫu thật; thay đường dẫn dưới đây bằng thư mục expert vừa được tạo:

```powershell
$expertSessionPath = 'D:\MyProject\Denso2\smartwear-ai-software\ai\generated_data\sessions\TEN_PHIEN_EXPERT_THAT'
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --publish --role worker --expert-session $expertSessionPath
```

CLI này không thay thế đầy đủ metadata task/consent/review của workflow dashboard. Dùng dashboard cho bài học có SOP được duyệt. Tổng thời gian quay không phải thời gian chu kỳ thao tác.

## 7. Dừng dự án

Trước tiên bấm kết thúc quay, chờ xử lý/lưu hoàn tất. Nếu chạy bằng các terminal ở mục 4, nhấn Ctrl+C lần lượt ở terminal backend, NTP và broker do bạn khởi động.

Nếu chạy nền, tìm PID hiện tại rồi kiểm đúng tiến trình trước khi dừng:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue |
    Select-Object OwningProcess
Get-NetUDPEndpoint -LocalPort 123 -ErrorAction SilentlyContinue |
    Select-Object OwningProcess
# Thay 12345 bằng PID đã xác minh của dịch vụ cần dừng:
Get-CimInstance Win32_Process -Filter 'ProcessId = 12345' |
    Select-Object ProcessId,Name,CommandLine
Stop-Process -Id 12345
```

Không dùng PID cũ trong báo cáo lịch sử. Không dừng tất cả tiến trình Python/Mosquitto trên máy.

## 8. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không mở được dashboard | Kiểm listener 8000 và `/ready`; chạy `start-backend.ps1` nếu chưa có backend. |
| Cổng 8000/1883/123 bị chiếm | Kiểm PID/command line; dùng dịch vụ đúng đang chạy hoặc dừng đúng tiến trình cũ sau khi hết capture. |
| NTP bind lỗi hoặc không có `.1` | Bật Mobile Hotspot, kiểm IP và UDP123. |
| Camera 503 hoặc NTP chưa ready | Kiểm NTP/firewall; reset bo sau khi dịch vụ sẵn sàng và không đang thu. |
| JPEG timeout | Kiểm hotspot, nguồn/cáp SmartCap, `:82/status`; đóng consumer stream khác. Không mở serial khi đang quay. |
| MQTT kết nối nhưng không có wrist samples | Kiểm nguồn SmartWrist, firmware, broker `.1:1883` và topic; `.100` là wrist, không phải broker. |
| Không thấy tay hoặc không có reference dùng được | Chỉnh camera/ánh sáng để thấy tay và vật; worker chọn đúng reference đã duyệt cùng task/version. |
| COM bị Access denied | Đóng Arduino/PlatformIO Serial Monitor trước khi upload; liệt kê lại cổng khi capture đã dừng. |
| Không truy cập được dashboard từ thiết bị LAN | Kiểm cùng hotspot, IP `.1` và firewall TCP8000. |
| `UnknownPlatform: espressif32@6.9.0` | Dot-source `deployment/hardware.ps1` để đặt `PLATFORMIO_CORE_DIR` về repo. |

Nếu firewall thực sự chặn, tham khảo các lệnh PowerShell Administrator giới hạn subnet trong [RUNBOOK.md](layer1-layer3/RUNBOOK.md). Không cần đổi firewall khi dịch vụ đang kết nối tốt.

Chỉ build/upload firmware khi cần đổi cấu hình hoặc sửa firmware; chạy dự án thông thường không cần nạp lại bo. Cổng gần nhất trong tài liệu là SmartCap COM5 và SmartWrist COM7, phải kiểm lại trước upload.

## 9. Dữ liệu và giới hạn

- Raw/video/JSONL/manifest: `ai/generated_data/sessions/`.
- Database mặc định: `backend/data/smartwear.db`.
- Frontend đã build: `frontend/dist/`.
- Log backend của lần chạy này: `backend/data/project-run.stdout.log`, `project-run.stderr.log`.
- Log NTP của lần chạy này: `backend/data/project-ntp.stdout.log`, `project-ntp.stderr.log`.
- Báo cáo preflight của lần kiểm này: `backend/data/project-run-preflight-20261009.json`.

Không sửa raw/checksum hoặc đổi dữ liệu thiếu thành số giả. FSR hiện là ADC, chưa phải Newton; IMU có lịch sử unavailable và kênh FSR thứ tư có lịch sử không phản hồi. SmartCap không có IMU đầu. Dataset hiện phục vụ quan sát, chưa có action robot được kiểm chứng. Nhãn AI/MUDA cần người xem xác nhận.

## 10. Kết quả kiểm tra lần chạy ngày 09/10/2026

Frontend TypeScript/Vite đã build thành công trong lượt khởi động trước cùng phiên làm việc. Backend đang phục vụ dashboard tại cổng 8000 và `/ready` trả `ready`. MQTT đã chạy sẵn. NTP đã được khởi động bổ sung, preflight đạt camera TCP, MQTT TCP, NTP stratum 10 và bốn dependencies `cv2`, `mediapipe`, `paho`, `fastapi`.

Không tự thu phiên người tham gia, duyệt SOP hoặc thay đổi firmware trong lượt chạy này. Kết quả kết nối không thay thế kiểm tra chất lượng JPEG/sensor hoặc nghiệm thu FPS/clock/calibration.

Tài liệu chi tiết: [runbook](layer1-layer3/RUNBOOK.md), [hợp đồng dữ liệu](layer1-layer3/CONTRACT.md), [cải tiến mới nhất](IMPROVEMENTS_20261009.md), [hai workflow demo](DEMO_TWO_WORKFLOWS.md).
