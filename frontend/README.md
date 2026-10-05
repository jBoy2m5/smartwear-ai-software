# SmartWear AI dashboard

## Công nhân sử dụng

Mở **http://127.0.0.1:8000/** trên Chrome của máy chạy SmartWear AI. Bấm **Bắt đầu quay**, làm thao tác bằng **tay phải** trước camera, rồi bấm **Kết thúc** trên trang. Camera chỉ lưu tọa độ và hành động của tay phải trong phiên mới. Backend gửi hình camera chưa vẽ chữ kèm nhãn/tọa độ đúng khung hình; dashboard tự vẽ chữ và điểm tay rõ nét lên hình. Trang tự xử lý, so với mẫu gần nhất, lưu lên backend và mở kết quả vừa quay. Không cần PowerShell, cửa sổ OpenCV hay phím Q.

Nút camera trên dashboard yêu cầu **ESP32-CAM + SmartWrist**. Nếu ESP32 không gửi ảnh, trang báo lỗi; nó không lấy webcam của máy tính để thay thế. Nếu mở trang từ máy khác, nguồn ảnh vẫn là ESP32 mà máy chủ AI kết nối tới. Mỗi máy chủ hiện chỉ quay một phiên cùng lúc; một phiên tối đa 3 phút.

Quản trị viên cấu hình địa chỉ ESP32-CAM/SmartWrist trước khi chạy backend. Công nhân vẫn dùng
hai nút trên trang; dữ liệu ADC đo thật hiện dưới mã phiên `MEASURED_`, còn chế
độ webcam/số mô phỏng giữ mã `DEMO_` khi API được gọi với `capture_mode=demo`. Xem hướng dẫn thiết lập, kiểm tra đồng hồ
thiết bị và dữ liệu gốc tại `ai/hardware/README.md`. Camera ESP32 hiện chỉ
phát QVGA 320×240 nên UI không thể tạo thêm chi tiết ảnh vượt nguồn gốc.

Dashboard có danh sách phiên, ảnh mẫu/ảnh công nhân, hành động tay phải, cặp DTW và chênh lệch thời gian, nghi vấn MUDA với thời điểm/ảnh, số cảm biến, biểu đồ, SOP, video AVI, ZIP dữ liệu AI và toàn bộ JSON. Phiên cũ đã quay hai tay vẫn đọc được. Số lực, điểm so sánh và đường đi robot được ghi rõ là **DEMO**.

## Quản trị viên thiết lập một lần

Trên máy có camera, cài Python với OpenCV/MediaPipe cho AI, môi trường backend và Node.js cho việc build. Tại `C:\Task\smartwear-ai`:

```powershell
cd frontend
npm.cmd install
npm.cmd run build -- --configLoader native
cd ..
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Backend phục vụ frontend đã build tại `/`, nên **không cần chạy Vite** khi công nhân dùng. Để máy chủ tự chạy khi bật máy, quản trị viên cấu hình dịch vụ hoặc tác vụ khởi động của Windows cho lệnh backend. Máy chạy backend cần thấy webcam và Python có `cv2`, `mediapipe`; nếu Python AI nằm ở nơi khác, đặt `SMARTWEAR_AI_PYTHON` thành đường dẫn tới `python.exe` đó. Nếu backend dùng cổng khác, đặt thêm `SMARTWEAR_CAPTURE_BACKEND_URL` tương ứng để AI gửi kết quả về đúng máy chủ.

Lập trình viên vẫn có thể dùng `npm.cmd run dev -- --configLoader native` tại `frontend/` để phát triển giao diện ở cổng `5173`; Vite chuyển `/api` tới backend cổng `8000`.

Kết quả AI được lưu trong `ai/generated_data/sessions/`; backend lưu dữ liệu riêng dưới `backend/`. Nếu xử lý thất bại, bản ghi camera đã tạo được giữ lại để quản trị viên kiểm tra và phục hồi. Bản demo hiện cần camera gắn với máy chạy AI; camera trên một thiết bị truy cập từ xa chưa được gửi trực tiếp qua trình duyệt.
