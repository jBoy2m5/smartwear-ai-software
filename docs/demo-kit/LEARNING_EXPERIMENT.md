# Thí nghiệm học việc có bằng chứng

Trạng thái: công cụ thu, review và so sánh đã triển khai; chưa có người tham gia hoặc kết quả được xác nhận trong lượt sửa này.

## Chuẩn bị

- Chọn bài LOG_KIT v1 (soạn bộ) hoặc HAND_ASSEMBLY v1 (lắp bằng tay). Người hướng dẫn xác nhận vật dụng, tiêu chí đầu ra và 4 bước.
- Chuẩn bị một người hướng dẫn, một người mới và người đánh giá; dùng bí danh, xác nhận đồng ý ghi hình trước từng phiên.
- Cố định ánh sáng, vật, gá và bố trí. Viết một mô tả điều kiện được người đánh giá xác nhận; dùng cùng mô tả cho hai lượt nếu điều kiện thật sự tương đương.
- Kiểm camera, MQTT, NTP trên dashboard; hình cần thấy tay và vật. Không mở serial/reset/flash trong khi quay.

## Thực hiện

1. Ghi mẫu hướng dẫn thật, đúng task/version. Người hướng dẫn ghi instruction/why/tips và người đánh giá xem video, gán start/end từng bước, kiểm đầu ra rồi duyệt SOP.
2. Ghi người mới, chọn cùng mẫu đã duyệt, chọn **Trước khi học SOP**. Người mới nhận phiếu công việc tối thiểu. Đánh giá cả lượt thất bại, không dàn dựng lỗi rồi coi là lỗi tự nhiên.
3. Cho người mới xem SOP/video mẫu đã duyệt. Ghi việc đã xem bằng xác nhận của người đánh giá ở lượt sau.
4. Ghi **Sau khi học SOP**, cùng bí danh, task/version, reference và bản duyệt mẫu. Giữ điều kiện tương đương, ghi các thay đổi nếu có.
5. Trong mỗi phiên người học, điền mốc thao tác thật từng bước, kết quả sản phẩm, người duyệt/lý do, số gợi ý và số lỗi đã xác nhận. Ghi 0 khi đã đánh giá và không có; để trống nếu chưa đo. Duyệt cả lượt đạt và không đạt khi đủ bằng chứng.
6. Mở **Thí nghiệm học việc — bằng chứng trước/sau**, tải các lượt, chọn rõ hai session rồi kiểm bằng chứng. Báo cáo chỉ tính chênh lệch khi đủ gate. Tải JSON cùng nguồn archive; giữ session/review revision/hash trong báo cáo.

## Tải và xác minh bằng chứng

Từ PowerShell trong repo, thay hai session ID và tên file mới bằng dữ liệu thật:

```powershell
.\.venv\Scripts\python.exe -B deployment/export-learning-evidence.py --before MEASURED_BEFORE --after MEASURED_AFTER --output backend/data/learning-evidence-NEW.json
```

Lệnh kiểm lại SHA256 và size của archive trước, sau và mẫu; mã thoát 2 nghĩa báo cáo còn thiếu bằng chứng hoặc checksum không đạt. File có sẵn không bị ghi đè.

## Cách đọc kết quả

- Cycle time là từ start của bước đầu đến end của bước cuối đã duyệt, bao gồm khoảng giữa các bước; không dùng tổng thời lượng quay.
- Chênh lệch = sau − trước. Thời gian giảm % = (trước − sau) / trước × 100. Phải đọc cùng đầu ra, số lỗi và số gợi ý; làm nhanh hơn nhưng sản phẩm không đạt chưa chứng minh cải thiện.
- Một cặp trước/sau là trường hợp thực nghiệm, có thể có hiệu ứng quen bài. Lặp trên vài người; nếu cần đánh giá hiệu quả riêng của SmartWear, thêm nhóm dùng hướng dẫn hiện tại trong điều kiện tương đương.
- Không đổi dữ liệu kỹ thuật cũ thành phiên chuyên gia hoặc người học. Fixture test và benchmark phần mềm không phải bằng chứng người mới học được.
