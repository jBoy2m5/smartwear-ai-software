# Mẫu thử: tay phải nắm, giữ, thả và mở

Mẫu này được sửa nhãn tay từ một video camera đã quay trước đó. Đây là bài tập demo, không phải thao tác chuẩn nhà máy. Mở `camera.avi` để xem trước. Chỉ dùng **tay phải thật**; để tay trái ngoài khung hình.

Camera ghi năm đoạn nhìn thấy: `GRAB` (0–0,812 s), `ASSEMBLY` (0,812–1,576 s), `GRAB` (1,576–1,623 s), `RELEASE` (1,623–2,314 s), `OPEN` (2,314–4,802 s). `GRAB` thứ hai chỉ 47 ms và được bộ tìm bước thêm/bỏ sót/lặp bỏ qua như nhãn thoáng qua. Bốn bước ổn định là **nắm → giữ tay nắm yên → thả → mở tay**. `ASSEMBLY` chỉ là nhãn suy đoán từ bàn tay đóng đứng yên.

Chạy từ thư mục gốc dự án:

```powershell
python -B .\ai\camera_test.py --practice-sample 04_right_grab_hold_release_open
```

Mỗi lần quay chỉ thử **một thay đổi**, rồi nhấn Q. Chương trình dùng đúng mẫu này thay vì tự chọn mẫu khác.

| Lần quay | Thao tác với tay phải | Dấu hiệu muốn kiểm tra |
| --- | --- | --- |
| Gần giống mẫu | Nắm ~0,8 s → giữ tay nắm đứng yên ~0,8 s → mở, giữ mở ~2,5 s. | Lần đối chứng. |
| Làm thêm | Làm đủ bốn bước, rồi nắm thêm 0,5–1 s trước khi nhấn Q. | `extra_visible_action`. |
| Lặp lại | Nắm → giữ yên đến khi hiện `ASSEMBLY` → di chuyển tay vẫn nắm để trở lại `GRAB` → giữ yên lần nữa đến `ASSEMBLY` → thả → mở. | `repeated_visible_action` nếu cả hai nhãn lặp rõ. |
| Bỏ sót | Nắm khoảng 0,5 s rồi mở ngay, không giữ yên đến khi hiện `ASSEMBLY`; sau đó giữ mở. | `missing_visible_action` nếu camera ghi `GRAB → RELEASE → OPEN`. |
| Kéo dài | Làm như mẫu nhưng giữ tay `OPEN` khoảng 5 s rồi nhấn Q. | `longer_visible_action` cho `OPEN`. |

Mở `analysis_result.json → muda_review → hands → right → candidates` trong thư mục phiên vừa quay. `worker_time_hint_ms` ở trường hợp bỏ sót chỉ là mốc gần vị trí dự kiến. Các mục này cần xem lại video, không phải kết luận Muda.
