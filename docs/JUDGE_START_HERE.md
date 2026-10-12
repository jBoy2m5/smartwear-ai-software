# Chạy SmartWear bằng Docker

Repo GitHub chứa mã nguồn để Docker tự build; **không cần đưa file TAR lớn lên GitHub**. Có ba cách dùng trên Windows:

| Muốn thử gì? | Nhấp đúp file | Trên giao diện |
| --- | --- | --- |
| Tải video có sẵn | `START_JUDGE.cmd` | Tải video lên và phân tích hai tay. Không có lực/IMU thật. |
| Quay bằng webcam máy tính | `START_JUDGE.cmd` hoặc `START_HARDWARE.cmd` | Trình duyệt quay webcam, sau đó tải video vừa quay lên để AI phân tích. |
| Có ESP32-CAM và SmartWrist | `START_HARDWARE.cmd` | Quay trực tiếp bằng thiết bị, nhận dữ liệu vòng tay phải; vẫn có thể tải video lên. |

## Chuẩn bị chung

1. Cài và mở [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/); chờ dòng **Engine running**.
2. Trên GitHub, chọn **Code → Download ZIP** rồi giải nén repo. Nếu repo riêng tư, giám khảo cần được cấp quyền truy cập.
3. Mở thư mục gốc repo, nơi có `START_JUDGE.cmd` và `START_HARDWARE.cmd`. Lần build đầu cần Internet và có thể mất vài phút. Không cần cài Node hoặc thư viện AI trên máy chấm.

## Cách 1 — Không có thiết bị: tải video lên hoặc quay webcam

1. Nhấp đúp **`START_JUDGE.cmd`**. Chờ cửa sổ báo `SmartWear is ready`; trang `http://localhost:8000` sẽ mở.
2. Chọn video MP4/MOV/AVI/WebM (tối đa 50 MiB, 3 phút, Full HD), xác nhận quyền sử dụng rồi bấm **Tải lên và phân tích**.
3. Chờ xử lý, chọn phiên đã lưu để xem hành động tay trái và tay phải, ảnh và báo cáo. Video tải lên không cung cấp dữ liệu lực/FSR hay IMU thật.

Nếu muốn dùng **camera máy tính**, bấm **Quay bằng camera máy tính**, cho phép Chrome sử dụng camera, xem hình trực tiếp rồi bấm **Dừng quay webcam**. Sau khi video xuất hiện, xác nhận quyền sử dụng và bấm **Tải lên và phân tích**. Video được quay trong trình duyệt (tối đa 3 phút), AI phân tích **sau khi dừng và tải lên**; khi đang quay chưa có nhãn AI trực tiếp. Không cần ESP32-CAM hoặc SmartWrist. Dùng `localhost` hoặc HTTPS để trình duyệt cho phép mở webcam.

## Cách 2 — Có ESP32-CAM và SmartWrist: quay trực tiếp

1. Bật Windows Mobile Hotspot 2.4 GHz; cho ESP32-CAM và SmartWrist kết nối cùng hotspot. Cấu hình mặc định dùng gateway `192.168.137.1` và camera `http://192.168.137.111:81/stream`.
2. Trên **Windows host**, chạy MQTT broker (TCP 1883) theo `deployment/mosquitto.conf` và NTP (UDP 123) bằng `ai/hardware/ntp_server.py`. Docker không tự bật hai dịch vụ này. Xem lệnh cài/chạy ở [README — Khởi động phần cứng](../README.md#khởi-động-phần-cứng) và [hướng dẫn Docker phần cứng](HARDWARE_DOCKER.md).
3. Nhấp đúp **`START_HARDWARE.cmd`**. Chờ `SmartWear is ready`, rồi mở `http://localhost:8000`.
4. Chọn **Quay trực tiếp**, điền thông tin phiên và kiểm trạng thái camera, MQTT, NTP trên giao diện trước khi bấm quay. AI theo dõi hai tay; SmartWrist cung cấp dữ liệu cảm biến của tay phải. Nếu muốn thử mà không dùng thiết bị, chọn **Tải video lên · không cần thiết bị** hoặc **Quay camera máy tính (DEMO)**. Nút webcam trong bản Docker dùng camera của **trình duyệt trên máy đang mở trang**, không phải camera của container.

Nếu IP camera khác mặc định, mở CMD tại thư mục repo rồi chạy, ví dụ:

```cmd
set SMARTWEAR_CAMERA_URL=http://192.168.137.101:81/stream
START_HARDWARE.cmd
```

Thông báo `SmartWear is ready` chỉ xác nhận ứng dụng chạy; nó **không xác nhận** camera đã gửi khung hình hoặc vòng tay đã gửi mẫu. Muốn kiểm tra phần cứng, phải quay thử một phiên và xem trạng thái/ảnh trực tiếp. Hai chế độ dùng chung dữ liệu backend; chuyển chế độ bằng cách chạy script tương ứng, không cần xóa volume.

## Kiểm tra, dừng và xử lý lỗi

- Mở `http://localhost:8000/ready`; kết quả mong đợi là `{"status":"ready"}`. Nếu cổng 8000 đã được dùng, đặt `SMARTWEAR_PORT=8001` trước khi chạy script và mở `http://localhost:8001`.
- Xem log: `docker compose -f compose.judge.yaml logs --tail 100 smartwear` hoặc thay bằng `compose.hardware.yaml` nếu đang dùng phần cứng.
- Dừng mà giữ dữ liệu: `docker compose -f compose.judge.yaml down` hoặc `docker compose -f compose.hardware.yaml down`. **Không dùng `down -v`** nếu cần giữ phiên đã lưu.

Máy giám khảo có thể build lại từ repo GitHub; file TAR chỉ cần khi muốn nạp image hoàn toàn offline. Xem thêm [hướng dẫn chấm thử](JUDGE_QUICKSTART.md) và [hướng dẫn Docker phần cứng](HARDWARE_DOCKER.md).
