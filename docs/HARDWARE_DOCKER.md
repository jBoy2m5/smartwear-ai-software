# Chạy SmartWear với phần cứng trong Docker (Windows)

`START_JUDGE.cmd` là bản chấm bằng **video tải lên**, nên không hiện nút quay ESP32-CAM. Để dùng **ESP32-CAM + SmartWrist** và vẫn giữ chức năng tải video, dùng `START_HARDWARE.cmd` ở thư mục gốc repo. Cả hai chế độ nhận diện **tay trái và tay phải**; SmartWrist cung cấp cảm biến của tay đeo vòng.

## Chuẩn bị một lần

1. Cài Docker Desktop và đợi trạng thái **Engine running**. Lần build đầu cần Internet.
2. Bật Windows Mobile Hotspot 2.4 GHz có địa chỉ `192.168.137.1`; cho ESP32-CAM và SmartWrist kết nối cùng hotspot. Địa chỉ mặc định của camera là `192.168.137.111:81`.
3. Trên **Windows host**, chạy MQTT broker theo `deployment/mosquitto.conf` (TCP 1883) và NTP theo `ai/hardware/ntp_server.py` (UDP 123). Hai dịch vụ này phục vụ cả thiết bị trên hotspot lẫn ứng dụng trong container; Docker không thay thế chúng. Xem lệnh khởi động trong [README](../README.md#khởi-động-phần-cứng). Nếu Windows Firewall chặn Docker Desktop truy cập các cổng này, cho phép `com.docker.backend.exe` trên mạng riêng.

## Bật ứng dụng

Nhấp đúp `START_HARDWARE.cmd`. Script build image có giao diện quay trực tiếp, tạo container và mở `http://localhost:8000`. Trong trang, chọn **Quay trực tiếp**, chọn công đoạn/loại phiên, rồi kiểm trạng thái camera, MQTT và NTP trước khi quay. Có thể chọn **Tải video lên · không cần thiết bị** trên cùng giao diện.

Nút **Quay camera máy tính (DEMO)** trong bản Docker mở webcam qua trình duyệt. Sau khi dừng quay, xác nhận quyền sử dụng và bấm **Tải lên và phân tích**. AI xử lý video sau khi tải lên; webcam không có dữ liệu lực/IMU và không tạo phiên đo phần cứng. Trình duyệt cần `localhost` hoặc HTTPS để cho phép mở camera.

Lần chạy này dùng lại volume dữ liệu backend của `START_JUDGE.cmd`, nên các phiên đã lưu vẫn còn. Khi chuyển giữa hai chế độ, chỉ chạy một script tại một thời điểm; Compose sẽ thay container ứng dụng nhưng giữ các volume.

Nếu camera dùng IP khác, đặt biến `SMARTWEAR_CAMERA_URL` trước khi chạy, ví dụ trong CMD:

```cmd
set SMARTWEAR_CAMERA_URL=http://192.168.137.101:81/stream
START_HARDWARE.cmd
```

Tương tự có thể đặt `SMARTWEAR_MQTT_HOST`, `SMARTWEAR_MQTT_PORT`, `SMARTWEAR_MQTT_TOPIC`, và `SMARTWEAR_PORT`. Với cấu hình mặc định, container kiểm kết nối tới camera `192.168.137.111:81`, broker `192.168.137.1:1883`, NTP `192.168.137.1:123/udp`. Nếu thiết bị không kết nối được, giao diện báo riêng trạng thái từng nguồn; không chuyển ngầm sang webcam.

Kiểm tra từ container khi cần:

```cmd
docker compose -f compose.hardware.yaml exec smartwear python -c "from ai.hardware.config import HardwareConfig; from backend.services.device_health import diagnose; print(diagnose(HardwareConfig.from_environment()))"
docker compose -f compose.hardware.yaml logs --tail 100 smartwear
```

Để dừng và giữ dữ liệu: `docker compose -f compose.hardware.yaml down`. Video/phiên lưu trong Docker volumes; đừng xóa volumes nếu muốn giữ dữ liệu. Chưa thể xác nhận đường truyền phần cứng chỉ bằng việc container báo `/ready`: cần camera có khung hình và SmartWrist gửi mẫu MQTT khi quay thử.
