# COM7 xuất hiện nhưng không nạp được

Kiểm tra ngày 05/10/2026:

- Windows PnP: CP210x COM7, Status OK, CM_PROB_NONE.
- Mở trực tiếp bằng pySerial (cả ngoài sandbox): `PermissionError(13, 'Access is denied.', None, 5)`.
- Arduino IDE đang chạy, kèm `serial-monitor.exe` PID 6776 tại thời điểm kiểm tra.

Vì vậy thông báo esptool 4.5.1 “port doesn't exist” không mô tả đầy đủ lỗi thực. Cổng tồn tại nhưng bị từ chối truy cập; Serial Monitor đang chạy là nghi vấn chính, chưa xác minh ownership handle.

Lưu sketch rồi đóng Arduino IDE/Serial Monitor; đóng các terminal PlatformIO monitor nếu có. Chạy lại lệnh upload smartwrist COM7 khi đã xác nhận đúng bo. Nếu vẫn lỗi, rút/cắm USB rồi kiểm tra lại cổng. Chưa cần đổi code, baud hay bấm BOOT vì lỗi xảy ra ngay lúc mở cổng.

Tham khảo: https://docs.espressif.com/projects/esptool/en/release-v4/esp32/troubleshooting.html

## Đã xử lý

Dừng riêng `serial-monitor.exe` PID 6776, sau đó pySerial mở COM7 thành công (`COM7 OPEN_OK`). Điều này xác nhận Serial Monitor chiếm cổng. Đã chạy lại upload target `smartwrist` vào COM7: SUCCESS, hash flash verified, reset qua RTS. Log tại `smartwrist-upload.log`. Chưa xác nhận kết nối MQTT/NTP hoặc số đo cảm biến sau nạp.
