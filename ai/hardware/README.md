# SmartWear: ESP32-CAM + SmartWrist trên máy 192.168.0.109

Luồng phần cứng là **tùy chọn**. Chế độ DEMO/webcam cũ vẫn chạy khi không đặt
`SMARTWEAR_CAPTURE_MODE=hardware`. Phần cứng đã được cấu hình để đeo vòng ở **tay
phải**. AI vẫn chỉ nhận diện và lưu tọa độ tay phải.

## Quản trị viên chuẩn bị một lần

Máy hiện có IP `192.168.0.109` và Mosquitto cổng 1883. Python hệ thống hiện có
OpenCV, MediaPipe và Paho MQTT; `ai\.venv` chưa có OpenCV. Không cần cài lại
backend. Nếu chuyển máy, cài Python phù hợp và các gói này vào **cùng một** môi
trường Python được đặt ở `SMARTWEAR_AI_PYTHON`.

Trước khi bật phần cứng, xác nhận SmartWrist gửi JSON thực lên topic
`wearable/user01/wrist/data` và ESP32-CAM trả stream JPEG tại URL đang dùng.
Lệnh kiểm tra cổng trên PowerShell:

```powershell
Test-NetConnection 192.168.0.109 -Port 1883
Test-NetConnection 192.168.0.101 -Port 81
```

Nếu camera đổi IP DHCP, thay URL theo IP in ở Serial của ESP32-CAM. Đóng tab
browser đang mở `/stream` trước khi ghi vì firmware chỉ có một consumer trực
tiếp. MQTT broker không cấp NTP: **cả camera và vòng tay cần tự có thời gian NTP
hợp lệ**. Mã không bịa thời gian thiết bị khi NTP lỗi.

Thu thử dữ liệu gốc trong 60 giây, **chưa chạy MediaPipe và chưa gửi backend**:

```powershell
cd C:\Task\smartwear-ai
python -B ai\hardware\raw_capture.py --duration-s 60
```

Thư mục phiên được in ngay khi bắt đầu, chứa `camera_raw.mjpeg`,
`camera_packets.jsonl`, `wrist_raw.jsonl`, `raw_capture.json`. File cuối ghi
FPS JPEG, tốc độ gói MQTT, bộ đếm lỗi và SHA-256. Trong `wrist_raw.jsonl`, mỗi
dòng giữ cả `raw_payload` nguyên bản, topic, giờ nhận và `generation` của bo.
Nếu một nguồn không gửi mẫu, trạng thái là `incomplete_inputs` và lệnh trả mã
lỗi; dữ liệu đã nhận vẫn còn. Lệnh `--help` cho phép đổi URL/IP/topic hoặc chọn
`--output-dir` mới. Trên phiên raw-only, chưa có ảnh MediaPipe, cảm biến đã ghép
hay `analysis_result.json`.

Chạy thử collector độc lập, chỉ giữ file trên máy:

```powershell
cd C:\Task\smartwear-ai
python -B ai\hardware\record_hardware.py --camera-url http://192.168.0.101:81/stream --mqtt-host 192.168.0.109 --duration-s 60
```

Nhấn **Q** để dừng. Thêm `--process` để chuẩn hóa, ghép ADC/IMU và phân tích sau
khi dừng. `--force-channel 0`, `1`, `2` hoặc `3` chỉ dùng khi bạn đã xác nhận
kênh cần so; không truyền tham số này thì **cả bốn kênh vẫn được lưu, còn lực
scalar để trống**. Số ADC không phải Newton hay sEMG. Xem tùy chọn thật bằng
`python -B ai\hardware\record_hardware.py --help`.

Sau khi đã xác nhận cả camera và vòng tay có mẫu thật, có thể quay, xử lý và
gửi backend bằng một lệnh (nhấn **Q** để kết thúc):

```powershell
python -B ai\hardware\record_hardware.py --duration-s 60 --process --publish --backend-url http://127.0.0.1:8000
```

Chế độ web ở bên dưới làm ba bước này tự động sau nút **Kết thúc**; công nhân
không cần chạy lệnh.

Để công nhân chỉ dùng dashboard, quản trị viên đặt biến môi trường **trong cửa
sổ khởi động backend**, rồi chạy backend như thường:

```powershell
$env:SMARTWEAR_CAPTURE_MODE='hardware'
$env:SMARTWEAR_CAMERA_URL='http://192.168.0.101:81/stream'
$env:SMARTWEAR_MQTT_HOST='192.168.0.109'
$env:SMARTWEAR_AI_PYTHON='C:\Users\jboyn\AppData\Local\Programs\Python\Python311\python.exe'
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Nếu đã xác nhận kênh ADC, đặt thêm `$env:SMARTWEAR_FORCE_CHANNEL='0'` (đổi số
theo kênh đúng). Không đặt biến này khi chưa biết. Bỏ
`SMARTWEAR_CAPTURE_MODE` hoặc đặt `demo` để quay webcam/số mô phỏng như cũ.
Trên Chrome, công nhân mở `http://127.0.0.1:8000/`, bấm **Bắt đầu quay**, làm
thao tác tay phải, rồi bấm **Kết thúc**. Nếu thiếu camera/vòng tay hoặc không
ghép được mẫu, trang báo lỗi và **không chuyển sang số giả**.

## File trong mỗi phiên `ai/generated_data/sessions/hardware_.../`

- `camera_raw.mjpeg` chứa JPEG gốc nối tiếp; `camera_packets.jsonl` ghi offset,
  độ dài, SHA-256, thời gian thiết bị/nhận và số thứ tự cho từng JPEG.
- `wrist_raw.jsonl` chứa MQTT đã kiểm tra, bốn kênh ADC, IMU, thời gian/seq và
  số thế hệ sau reboot.
- `camera.jsonl` và `camera.avi` chứa **các khung đã kịp giải mã và chạy AI**;
  chúng có thể ít hơn số JPEG nhận được nếu hàng đợi đầy. Thời gian nguồn và
  thời gian nhận được giữ riêng; `camera.video.json` kiểm tra quan hệ JSON/video.
- `hardware_capture.json` ghi nguồn, số JPEG nhận, frame đã phân tích, frame
  rơi, lỗi kết nối, số MQTT/seq gap, FPS nhận và FPS AI. `status=complete` mới
  cho phép xử lý measured.
- `camera.normalized.jsonl`, `real_sensors.jsonl` và
  `real_sensors.meta.json` ghi kết quả ghép theo **thời gian từ hai thiết bị**.
  Cửa sổ ban đầu 40 ms, có số matched/missing và độ lệch từng mẫu. Mất mẫu thì
  dữ liệu sensor là `null`; toàn phiên không khớp thì lỗi, không tạo số giả.
- `multimodal.jsonl`, `action_segments.json`, `keyframes/` và
  `analysis_result.json` tiếp tục quy trình AI. Mã phiên gửi backend bắt đầu
  `MEASURED_`; video/ảnh/nguồn gốc được gửi như phiên DEMO, nhưng Newton và
  đường đi robot để trống khi chưa hiệu chuẩn.

Backend có ZIP dữ liệu nguồn nếu vừa giới hạn dung lượng. File
`camera_raw.mjpeg` lớn luôn được giữ **trên máy thu**; ZIP chỉ kèm file này khi
nhỏ. Kết quả worker so với mẫu DEMO sẽ ghi hai nguồn khác nhau và **không trừ
ADC đo thật với lực giả**.

## Điều chưa thể xác nhận bằng phần mềm

Firmware SmartWrist cần được sửa SSID/DHCP/NTP và xác minh mạch FSR/IMU trên
chính bo trước khi thử. Repo này không chứa firmware nên collector không tự nạp
bo. Không coi broker nhận `hello` là đã nhận cảm biến, không coi timestamp gần
nhau là đã chứng minh đồng hồ lệch dưới 10 ms, và không khẳng định ESP đạt 30
FPS trước khi xem `hardware_capture.json` của một phiên thật.
