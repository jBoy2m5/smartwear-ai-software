# Camera thật và cảm biến giả theo cùng bản quay

Camera lưu điểm bàn tay **thật** và `action_estimate` từ các điểm đó. `hand_state` là `OPEN`, `CLOSED`, `OTHER` hoặc `NONE`. `label` là nhãn ước đoán `REACH`, `GRAB`, `ASSEMBLY`, `RELEASE`, `OPEN`, `OTHER` hoặc `NO_HAND`. Nắm tay trong hình không chứng minh rằng người đó thật sự cầm vật. `ASSEMBLY` chỉ nghĩa là tay khép và tương đối yên.

IMU, lực và torque **vẫn là số mô phỏng** vì chưa có các thiết bị đo tương ứng. Chương trình mới nhìn trạng thái bàn tay trong bản quay để thay đổi các số giả; nó không còn gán “giây 2–4 luôn là nắm”. Số lực giả tăng khi camera thấy tay khép, nhưng không phải số đo lực của người trong video. Torque giả khi nhãn `ASSEMBLY` cũng không xác nhận có dụng cụ siết.

## Chạy với bản camera mới đã ghi

Từ `C:\Task\smartwear-ai`:

```powershell
.\ai\.venv\Scripts\python.exe -B .\ai\preprocessing\normalize_camera.py --input .\ai\camera_data_20260928_225209_301112.jsonl --output .\data\processed\camera_data_20260928_225209_301112.normalized.jsonl
.\ai\.venv\Scripts\python.exe -B .\ai\sensors\simulate_sensors.py --camera-file .\data\processed\camera_data_20260928_225209_301112.normalized.jsonl --output .\data\simulated\sensors_from_camera_20260928_225209_301112.jsonl
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s .\ai\sensors -p "test_*.py" -v
```

Để ghi bản mới bằng webcam, chạy `python -B .\ai\camera_test.py` bằng Python hệ thống có OpenCV/MediaPipe. Camera tạo file `ai\camera_data_<thời gian>.jsonl` mới, gồm `timestamp`, `camera`, `hands`, `action_estimate`. Đưa đường dẫn file đó vào `--input` khi chuẩn hóa. Các lệnh mở đầu ra bằng chế độ tạo mới, **không ghi đè** dữ liệu cũ; đổi tên `--output` nếu chạy lại.

## File và nguồn gốc

- `normalized_camera...jsonl`: `frame_id`, `timestamp_ms`, `relative_time_s`, `camera`, `hands`, `action_estimate`. Dữ liệu bàn tay đến từ webcam/MediaPipe; nhãn là **ước đoán từ hình bàn tay**.
- `sensors_from_camera...jsonl`: `timestamp_ms`, `imu_head`, `imu_wrist`, `force_emg_raw`, `torque`. Chỉ các giá trị cảm biến này được tạo giả. Mỗi bản ghi dùng timestamp của một khung camera; đây **không phải hai đồng hồ được đồng bộ độc lập**.
- `sensors_from_camera...meta.json`: ghi file camera nguồn, SHA-256, seed, số mẫu và các trường giả lập.

Gia tốc m/s², vận tốc góc rad/s, torque N·m, góc độ chỉ là **quy ước của bộ mô phỏng**, chưa được hiệu chuẩn. `force_emg_raw` không có đơn vị, không phải Newton hay Fx/Fy/Fz. Bộ mô phỏng không dùng những con số này để xác nhận hành động thật.

Hai file cũ `sensors_default.jsonl` và `sensors_camera_duration.jsonl` là **bản demo theo kịch bản thời gian trước đây**; giữ lại để đối chiếu, không dùng chúng làm bằng chứng cho hành động trong camera. Bộ mô phỏng hiện tại yêu cầu `--camera-file` có `action_estimate` từ camera.
