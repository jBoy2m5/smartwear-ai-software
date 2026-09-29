# Ghép camera và cảm biến mô phỏng

## Chạy tự động từ camera

```powershell
cd C:\Task\smartwear-ai
python -B .\ai\camera_test.py
```

Thao tác trước camera, nhấn Q trong cửa sổ camera để dừng. Chương trình đóng
file ghi, tắt camera rồi tự chạy chuẩn hóa → mô phỏng cảm biến → ghép multimodal.
Nhận diện và hiển thị nhãn camera hoạt động như trước.

File camera gốc vẫn ở `C:\Task\smartwear-ai\ai\camera_data_<ngày giờ>.jsonl`.
Kết quả xử lý mới nằm trong một thư mục riêng cho mỗi lần chạy:

```text
C:\Task\smartwear-ai\data\sessions\camera_data_<ngày giờ>_<mã riêng>\
    camera.normalized.jsonl
    sensors.jsonl
    sensors.meta.json
    multimodal.jsonl          ← kết quả cuối cùng
```

PowerShell hiện tiến độ 1/3, 2/3, 3/3 và đường dẫn kết quả khi hoàn tất.
Số dòng tùy bản quay mới, không cố định 403. Nếu camera chưa ghi được dòng nào,
chương trình báo không có dữ liệu. Nếu xử lý lỗi, các bước sau dừng, dữ liệu gốc
được giữ và PowerShell hiện lệnh thử lại. Các lần thử lại dùng thư mục mới.
Việc đóng cưỡng bức chương trình không kích hoạt bước xử lý sau camera.

Để tự động xử lý một file camera đã có, dùng:

```powershell
python -B .\ai\process_recording.py --input .\ai\camera_data_20260928_232738_214687.jsonl
```

Pipeline dùng cùng Python đang chạy để gọi các bước, không cài thêm thư viện.
Chỉ khởi động camera cần Python có OpenCV/MediaPipe. Bộ xử lý sau camera dùng
thư viện chuẩn Python. Dữ liệu mô phỏng tiếp tục được ghi nguồn gốc rõ ràng.

## Chạy riêng bước ghép

`build_multimodal.py` tạo một dòng chung cho mỗi thời điểm: camera nhìn thấy
bàn tay thế nào, nhãn hành động ước đoán là gì và các số cảm biến giả là bao nhiêu.
Không cần quay lại camera. Dùng cặp file đã có cùng phiên ghi:

```powershell
cd C:\Task\smartwear-ai
.\ai\.venv\Scripts\python.exe -B .\ai\preprocessing\build_multimodal.py --camera-file .\data\processed\camera_data_20260928_225209_301112.normalized.jsonl --sensor-file .\data\simulated\sensors_from_camera_20260928_225209_301112.jsonl --output .\data\processed\multimodal_20260928_225209_301112.jsonl
```

Nếu đầu ra đã tồn tại, đổi tên `--output`, ví dụ thêm `_run2`. Chương trình từ
chối ghi đè, không thay đổi đầu vào. Không dùng hai file demo theo chu kỳ cũ
`sensors_default.jsonl` / `sensors_camera_duration.jsonl` cho bước ghép này.

## Dữ liệu đầu ra mới: smartwear.multimodal.v1

- Giữ nguyên `frame_id`, `timestamp_ms`, `relative_time_s`, `camera`, `hands`,
  `action_estimate` từ camera đã chuẩn hóa. `hands` là các điểm do MediaPipe
  ước lượng từ hình ảnh thật, không phải ảnh/video được lưu trong JSONL.
- Giữ nguyên `imu_head`, `imu_wrist`, `force_emg_raw`, `torque` từ file cảm biến.
- Thêm `schema_version` và `provenance` ghi rõ nguồn camera, nhãn ước đoán,
  những trường mô phỏng, cách ghép thời gian và SHA-256 của hai file đầu vào.

Đây là schema mới cho bước ghép nội bộ, chưa phải Analysis Result JSON hay
API Contract của Layer 4. Schema file camera/cảm biến cũ không đổi.

`force_emg_raw` không có đơn vị, không phải Newton hay sóng sEMG sinh lý.
Gia tốc m/s², vận tốc góc rad/s, torque N·m và góc độ là quy ước mô phỏng.
Nhãn GRAB/ASSEMBLY không chứng minh đã cầm vật/lắp ráp thật.

## Quy tắc ghép

Chỉ chấp nhận hai file cùng số dòng, timestamp tăng và khớp chính xác từng dòng.
File `.meta.json` cạnh file sensor phải xác nhận nguồn mô phỏng, SHA-256 của
đúng file camera, số mẫu và khoảng thời gian. Có thể chỉ định metadata bằng
`--sensor-metadata`. Không tự bù dữ liệu thiếu hoặc ghép thời điểm gần nhất.
Mọi kiểm tra dữ liệu hoàn tất trước khi tạo đầu ra.

Timestamp cảm biến được sao chép từ camera; bước này không đồng bộ các đồng hồ
phần cứng độc lập. Toàn bộ phiên được đọc vào bộ nhớ, phù hợp bản demo ngắn.

## Xem kết quả và kiểm thử

```powershell
Get-Content .\data\processed\multimodal_20260928_225209_301112.jsonl |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.action_estimate.label -eq 'GRAB' } |
    Select-Object -First 5 timestamp_ms,
        @{Name='action'; Expression={$_.action_estimate.label}},
        force_emg_raw, @{Name='torque'; Expression={$_.torque.torque}}

.\ai\.venv\Scripts\python.exe -B -m unittest discover -s .\ai\preprocessing -p "test_*.py" -v
```

File mẫu có 403 dòng, từ 702 đến 16737 ms. Không đổi mốc bắt đầu thành 0.
