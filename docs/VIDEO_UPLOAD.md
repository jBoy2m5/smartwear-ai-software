# Phân tích video tải lên — không cần phần cứng

Trên dashboard chọn **Tải video lên · không cần thiết bị** (mặc định), chọn file,
xác nhận quyền sử dụng và xử lý video, rồi bấm **Tải lên và phân tích**.
Không cần hotspot, ESP32, SmartWrist, MQTT, NTP hoặc webcam.
Tab **Quay trực tiếp** giữ luồng phần cứng và webcam DEMO hiện có.

## Video được hỗ trợ

- MP4, MOV, AVI, WebM; khuyến nghị MP4 H.264 để xem trước trên trình duyệt.
- Tối đa 50 MiB, 180 giây, 1920×1080 pixels và 1–120 FPS.
- Container/codec phải được OpenCV trên máy chủ giải mã được. File hỏng hoặc
  không đủ khung hình bị báo lỗi; không tự coi phần đọc được là phiên hoàn tất.
- Phân tích tối đa 10 ảnh/giây và giảm ảnh phân tích về tối đa 960×540.
  Lật ngang ảnh phân tích để dùng cùng quy ước handedness của pipeline camera;
  video nguồn không bị sửa. Không coi kích thước/FPS phân tích là acquisition thực.
- Timeline lấy từ decoder `POS_MSEC`; nếu decoder không trả mốc tăng, dùng
  frame index / FPS khai báo. Số khung dùng fallback được ghi trong manifest.
  Đây là thời gian tương đối video, không phải đồng hồ NTP hay thời gian nhận ảnh.

## Kết quả

AI nhận diện hai tay, ước lượng nhãn hành động, phân đoạn và trích keyframe.
Video không thấy tay vẫn hoàn tất với trạng thái không thấy tay/không có phase;
không tạo nhãn giả để ép có kết quả. Phiên có ID `VIDEO_<job_id>`.

FSR/lực, IMU và torque đều giữ `null`, provenance
`missing_from_uploaded_video`, `simulated_fields=[]`. Không có mẫu so sánh,
không tính DTW/MUDA; các trường số legacy giữ 0 để tương thích ingest, giao diện
và báo cáo hiển thị chưa đánh giá. Không tạo robot trajectory hoặc robot export.
Vai trò legacy `TRAINEE` không xác nhận đây là một thí nghiệm người học.

Kết quả gồm báo cáo HTML/PDF nháp, keyframe, JSON/JSONL, video phân tích AVI
và ZIP nguồn. Video nguyên bản nằm trong ZIP dưới tên `source_video.<extension>`;
`uploaded_video.json` giữ hash, kích thước nguồn, frame count, timeline và biến đổi.
Video AVI phân tích không phải bản nguồn và có thể cần trình phát ngoài trình duyệt.
Luồng này chưa thêm chọn hai video để so sánh, duyệt mẫu expert hoặc xuất gói
HDF5/MCAP cho video upload. Không tự đưa video upload vào thí nghiệm học việc.

Job/status/preview dùng cơ chế hiện có; reload trang khôi phục job ID.
Hủy khi đang phân tích giữ file nguồn và dữ liệu tạm, không publish phiên hoàn tất.
Không chạy upload đồng thời với capture hoặc một job AI khác.

## API

`POST /api/v1/capture/upload?filename=video.mp4&consent=true`

Body là bytes video (không phải multipart). Server stream vào file tạm và kiểm
50 MiB kể cả khi không có Content-Length; tên lưu do server tạo, không dùng
đường dẫn người dùng. API trả 201 với job ID; định dạng/codec/thời lượng được
kiểm trong worker, job chuyển `failed` nếu không hợp lệ. Dùng các endpoint
`GET /capture/{job_id}`, preview/frame và `POST /capture/{job_id}/stop` hiện có.

## Chuẩn bị Docker

Đây là luồng phần mềm đã bổ sung, chưa phải gói Docker nộp hoàn chỉnh.
Image cần Python, backend, frontend dist, AI, model `ai/hand_landmarker.task`,
OpenCV/MediaPipe và dependencies xuất báo cáo. Worker upload không tải model
từ Internet; thiếu model thì báo lỗi rõ. Backend gọi worker bằng Python được
cấu hình; cần đặt `SMARTWEAR_AI_PYTHON` thành executable trong container.
Lưu `backend/data/capture_jobs` và các artifact backend bằng volume phù hợp.
Không cần đóng gói các phiên người dùng hoặc dữ liệu mẫu để khởi động.

Kiểm thử upload sử dụng video synthetic trong thư mục tạm, MediaPipe thật và
backend test riêng; không phải bằng chứng độ chính xác nhận diện tay trên tác vụ thật.
