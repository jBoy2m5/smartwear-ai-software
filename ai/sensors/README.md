# Cảm biến giả cho hai tay

Chạy camera như trước:
```powershell
cd C:\Task\smartwear-ai
python -B .\ai\camera_test.py
```
Nhấn Q: phần xử lý tự tạo sensors.jsonl và sensors.meta.json trong thư mục
C:\Task\smartwear-ai\data\sessions\<tên phiên>.

## Dữ liệu mới (v2)

- imu_head: một IMU đầu giả.
- hand_sensors.left: số giả cho cổ tay trái, tín hiệu lực và torque.
- hand_sensors.right: số giả cho cổ tay phải, tín hiệu lực và torque.
- tracking_status: detected, missing hoặc ambiguous.
- Mỗi tay dùng nhãn camera và tọa độ của chính tay đó; trạng thái, tín hiệu,
  seed nhiễu độc lập. Thay đổi tay trái không làm đổi số giả của tay phải.
- Nếu tay mất/không xác định: imu_wrist, force_emg_raw và torque là null.
  Khi thấy lại tay, bắt đầu tín hiệu mới, không nối lực/torque cũ qua khoảng mất.
- Đổi thứ tự các bàn tay trong kết quả MediaPipe không hoán đổi số giả hai bên.
- Timestamp sao chép từ khung camera, không phải đồng bộ hai đồng hồ thiết bị.
- Các nguồn v1 vẫn đọc được theo cách một tay cũ; không trộn v1/v2.

Số giả biến đổi theo hình bàn tay, không phải đo lực thật. force_emg_raw không
có đơn vị, không phải Newton hoặc sóng sEMG sinh lý. IMU m/s² và rad/s, torque
N·m và góc độ chỉ là quy ước của mô phỏng, chưa hiệu chuẩn.

## Metadata

File .meta.json ghi schema_version, SHA-256 camera/cảm biến, seed, noise_level,
số mẫu, khoảng thời gian, số lượng nhãn riêng từng tay và simulated_fields.
Cùng dữ liệu/cấu hình/seed sinh lại kết quả nhất quán trong môi trường hiện tại.
Các file cũ data/simulated/sensors_default.jsonl và sensors_camera_duration.jsonl
là demo theo lịch cố định; không dùng để ghép với bản camera mới.

## Chạy riêng nếu cần

```powershell
.\ai\.venv\Scripts\python.exe -B .\ai\sensors\simulate_sensors.py --camera-file .\data\sessions\<tên phiên>\camera.normalized.jsonl --output .\data\simulated\sensors_new.jsonl
```

Đổi đường dẫn <tên phiên> thành thư mục thực tế. Không ghi đè đầu ra.
Để chuyển bản camera cũ sang cả pipeline hai tay, chạy process_recording.py
với --input là file camera gốc. Chi tiết schema và luồng: ai/preprocessing/README.md.
