# Dữ liệu cảm biến mô phỏng

Chỉ dùng thư viện chuẩn Python. Không chạy webcam, chuẩn hóa camera hoặc ghép dữ liệu.

## Chạy bằng PowerShell

```powershell
Set-Location C:\Task\smartwear-ai
.\ai\.venv\Scripts\python.exe -B .\ai\sensors\simulate_sensors.py
.\ai\.venv\Scripts\python.exe -B .\ai\sensors\simulate_sensors.py --duration-s 14 --sampling-rate-hz 100 --random-seed 42 --noise-level 0.02 --output .\data\simulated\sensors_14s.jsonl
.\ai\.venv\Scripts\python.exe -B .\ai\sensors\simulate_sensors.py --camera-file --output .\data\simulated\sensors_camera_duration.jsonl
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s .\ai\sensors -p "test_*.py" -v
```

Mặc định: `duration_s=7`, `sampling_rate_hz=100`, `random_seed=42`, `noise_level=0.02`; 700 dòng từ 0 đến 6990 ms. Đường dẫn đầu ra mặc định luôn tính từ repository. `--output` và đường dẫn `--camera-file` do người dùng cung cấp tính từ thư mục làm việc nếu là đường dẫn tương đối.

**Không ghi đè:** chương trình mở đầu ra bằng chế độ `x`; file tồn tại gây lỗi. Khi chạy lại hãy chọn tên mới bằng `--output`. Không có cờ ghi đè. Nếu quá trình bị ngắt, file một phần có thể còn lại; hãy dùng tên mới.

## Schema và giả định

Mỗi dòng JSON chứa:

| Trường | Ý nghĩa / đơn vị giả định |
|---|---|
| `timestamp_ms` | Số nguyên ms tương đối từ đầu phiên mô phỏng |
| `imu_head`, `imu_wrist` | Mỗi đối tượng gồm `ax, ay, az, gx, gy, gz` |
| `ax, ay, az` | Gia tốc giả định m/s², nền trọng lực +9.81 trên trục z |
| `gx, gy, gz` | Vận tốc góc giả định rad/s |
| `force_emg_raw` | Giá trị thô giả lập không đơn vị, nền khoảng 100, giữ lực khoảng 800; **KHÔNG phải Newton hay Fx/Fy/Fz** |
| `torque.torque` | Mô-men giả định N·m, đỉnh khoảng 3 |
| `torque.angle` | Góc dụng cụ giả định độ, khoảng 0–30 |

Các đơn vị và trục là quy ước của bộ mô phỏng, chưa hiệu chuẩn thiết bị. Gia tốc/góc không được tích phân thành mô hình vật lý. Góc tăng trong ASSEMBLY và trở về 0 trong RELEASE. `force_emg_raw` chỉ là một tín hiệu đại diện, không phải hai phép đo FSR và sEMG độc lập, cũng không phải sóng sEMG sinh lý.

Chu kỳ lập trình sẵn: [0,2) s REACH (cổ tay chuyển động nhiều), [2,4) GRAB (lực tăng mượt), [4,6) ASSEMBLY (cổ tay ổn định, giữ lực, torque hoạt động), [6,7) RELEASE (lực giảm). Lặp mỗi 7 giây. Không ghi nhãn thao tác vào bản ghi; đây không phải AI phân đoạn. Dữ liệu **chưa căn chỉnh theo hành động thực trong video**.

Nhiễu uniform độc lập, tái tạo bằng seed. `noise_level` trong [0,1], mặc định 0.02; hệ số biên độ lần lượt: gia tốc 1, vận tốc góc 0.2, tín hiệu thô 1000, torque 3, góc 30. Lực/torque/góc chặn dưới tại 0. Mức nhiễu cao có thể che xu hướng; 0 tắt nhiễu. Tái tạo byte giống nhau với cùng cấu hình và cùng môi trường Python.

Thời lượng phải hữu hạn và >0; tần số phải nguyên trong [1,1000] Hz để timestamp ms không trùng. Timestamp được tính trực tiếp `i*1000//rate`, không cộng dồn số thực. Với tần số không chia hết 1000, khoảng cách xen kẽ các số ms nguyên (ví dụ 60 Hz: 16/17 ms). Số mẫu bình thường là ceil(duration_s*rate), khoảng thời gian lý tưởng không gồm điểm cuối.

`--camera-file` không kèm đường dẫn đọc `data/processed/normalized_camera.jsonl` chỉ đọc. Có thể chỉ định đường dẫn khác. Chế độ này thay thế thời lượng bằng mốc cuối camera và lấy thêm mẫu tới hoặc vượt mốc đó tối đa một khoảng lấy mẫu. Camera hiện tại kết thúc ở 48240 ms: 4825 mẫu 100 Hz từ 0 đến 48240. Mốc camera đầu 303 ms không bị dịch về 0. Không ghép hàng, không đồng bộ thời gian, không suy luận thao tác từ camera.

## Giao diện đọc thay thế được

`read_sensor_records(path)` trả iterator các dict đã kiểm tra schema, số hữu hạn và timestamp tăng. `simulated_records(...)` cũng trả iterator cùng cấu trúc. Phần tiêu thụ chỉ cần nhận iterable và lặp `for record in source`. Sau này nguồn phần cứng có thể trả cùng cấu trúc qua iterator khác; cần chuyển đổi đơn vị và quy ước thời gian trong adapter phần cứng. Chưa triển khai adapter hay đồng bộ thật.
