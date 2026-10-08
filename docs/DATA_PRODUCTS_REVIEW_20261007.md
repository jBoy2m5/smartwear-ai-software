# Tiếp tục rà soát và kiểm chứng data products — 07/10/2026

Đọc các Markdown trong `docs/` và bàn giao `NEXT_SESSION_DATA_PRODUCTS.md`; tiếp tục phần review phần mềm. Không thu phiên mới, không duyệt mẫu chuyên gia hoặc điền consent thay người tham gia.

## Đã sửa

- Capture ghi mốc dừng ngay sau đóng các bộ thu/video, trước bước tổng hợp và hash artifacts. Hash script được chốt khi module nạp, tránh lấy nội dung file mới cho tiến trình đang dùng mã cũ.
- Fingerprint sản phẩm bao gồm hash archive nguồn, AVI riêng, manifest reference và exporter đã nạp. Manifest lưu lineage đó; cache kiểm lại size/hash từng artifact trước khi trả. Nguồn đổi trong lúc copy làm build thất bại, không publish kết quả mang hash sai.
- AVI fallback được kiểm bằng fixture có encoding 30 FPS nhưng observation 10 Hz. MP4 dựng theo timestamp observation; metadata `video_timebase` lưu mốc nguồn để clip/seek không lệch khi observation đầu khác 0.
- SOP offline có nút seek từng bước cho video mẫu/phiên hiện tại, link micro-clip và nội dung biến thể chấp nhận. Dashboard áp dụng cùng mốc thời gian.
- FFmpeg lỗi/timeout trả lỗi có ý nghĩa; API storage lỗi trả 503. Video handle luôn được đóng; cleanup kiểm đường dẫn trước khi xóa thư mục build tạm. Không xóa nguồn hoặc bản sản phẩm đã hoàn tất.
- Procedure không nhận step ID trùng; approval không nhận mốc trước observation đầu. Reference retired không được chọn cho capture mới, revision đã pin vẫn được giữ để tái lập lịch sử.
- Validator kiểm toàn bộ `checksums.sha256`, timeline tăng, HDF5 missing-value masks/độ dài nhãn, MCAP CRC/count/validity và cờ robot unavailable.

Hai đường tải learner/observation hiện vẫn chứa **cùng portable bundle đầy đủ**, khác tên ZIP. Chưa triển khai hai archive rút gọn độc lập; mọi artifact được manifest tham chiếu vẫn có trong ZIP.

## Kiểm thử

- Suite `python -B -m pytest ai backend/tests --ignore=ai/generated_data -q`: **61 passed, 8 subtests passed** sau sửa code.
- Sau bổ sung regression cho mốc dừng capture và worker/reference offline: `python -B -m pytest ai/hardware/test_deployment.py backend/tests/test_knowledge_products.py -q`: **20 passed**. Đây là fixture tổng hợp trong thư mục tạm, không phải nghiệm thu người học/chuyên gia.
- Frontend TypeScript/Vite build đạt. Còn warning bundle JS khoảng 650.55 kB, vượt mốc cảnh báo 500 kB.
- `git diff --check` đạt; Git có thông báo chuẩn hóa LF/CRLF.

## Runtime và read-back dữ liệu đo thật

Trước khởi động không có listener 8000 hoặc tiến trình uvicorn/capture được tìm thấy. Backend mới khởi động qua `deployment/start-backend.ps1`, chạy nền. Log: `backend/data/products-resume.stdout.log` và `.stderr.log`. PID tại thời điểm kiểm tra: uvicorn **13804**, wrapper **21136**; phải kiểm lại trước thao tác sau này.

- `/ready`: `ready`; dashboard HTTP 200; registry có `LOG_KIT` và `HAND_ASSEMBLY`, chưa có expert reference approved.
- Exporter SHA trong manifest bằng SHA file exporter trên đĩa: xác nhận gói được tạo bằng bản cuối của lượt sửa này.
- Phiên nguồn giữ nguyên: `MEASURED_hardware_20261007_150625_216050_uk5sxhc9`.
- Episode mới: `3fcfd3e0cc9f8742`; **1.555 frames**, MCAP **4.610 FSR + 4.610 trạng thái IMU + 1.555 camera + 1.555 hand observations**.
- **12 artifacts**, **13 mục checksum** hợp lệ; ZIP **34.569.458 bytes**; generation **48.703 ms** (48,703 giây). Đây là một lượt, không phải benchmark p50/p95 hoặc tải cao.
- `learner_ready=false`, `robot_ready=false`; không có task/SOP đã duyệt cho phiên legacy, không có robot actions. Không chuyển phiên này thành reference A/B.
- Báo cáo: [data-products-validation-resumed.json](layer1-layer3/data-products-validation-resumed.json). Báo cáo/lượt export cũ được giữ nguyên.

Lệnh đã chạy:

```powershell
.\.venv\Scripts\python.exe -B deployment/validate-data-products.py --url http://127.0.0.1:8000/api/v1/knowledge/sessions/MEASURED_hardware_20261007_150625_216050_uk5sxhc9/products/observation --output docs/layer1-layer3/data-products-validation-resumed.json
```

## Còn chờ

- Công cụ UI trả danh sách browsers/apps rỗng. Chưa kiểm bằng trình duyệt thật: seek/play offline, chọn expert/review/reload và lifecycle React. Build/API/read-back không thay thế visual-QA.
- Chờ thông tin vật dụng/người hướng dẫn/người học. Chưa thu hoặc approve mẫu A/B; cần thực hiện checklist `demo-kit/EVIDENCE.md` với dữ liệu thật.
- Chưa kiểm lại phần cứng trong lượt này. Các hạn chế FSR/IMU/camera/calibration/robot trong bàn giao vẫn còn.
- Chưa commit/push; giữ cả thay đổi có sẵn và thay đổi mới. Không thêm raw/private artifacts vào Git.
