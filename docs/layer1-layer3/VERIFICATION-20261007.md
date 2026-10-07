# Kiểm chứng phần cứng ngày 07/10/2026

- SmartCap COM4 (xác nhận log boot); SmartWrist COM7. Cấu hình PlatformIO và RUNBOOK đã cập nhật.
- Firmware SmartWrist tách task I2C: build/upload thành công, hash flash verified. Python: 52 tests + 8 subtests đạt. Frontend build đạt. `git diff --check` đạt.
- Sau khi người dùng bật hotspot: máy chủ `192.168.137.1`, preflight camera TCP/MQTT/NTP và dependency đều đạt. MQTT/NTP chạy nền. Backend `/ready` trả `ready`. Lần thử khởi chạy thêm backend báo cổng 8000 đã được dùng; backend có sẵn tiếp tục phục vụ.

## Raw 15 giây

`ai/generated_data/sessions/hardware_raw_20261007_142220_851221_7ohbgvuf`

- `raw_complete`: 269 JPEG, 758 wrist samples; 17.839 FPS và 50.269 Hz trong 15.079 giây.
- Không seq gap, không malformed MQTT, không camera stream error được ghi nhận.
- Cả 758 mẫu IMU unavailable; giữ `acc`/`gyro` null và bốn ADC thật.
- ADC min/max theo kênh: 0–4095, 853–959, 0–4095, 0–0. Chưa hiệu chuẩn lực; kênh thứ tư luôn bằng 0 trong phiên.
- Ảnh trích [raw-preview-20261007.jpg](raw-preview-20261007.jpg) hướng lên trần/đèn, có ánh sáng nhưng không thấy tay.

## AI 60 giây

`ai/generated_data/sessions/hardware_20261007_142254_436256_i1uwuwl2`

- Capture complete: 1077 JPEG, 1063 inferred frames, 3041 wrist samples trong 60.984 giây.
- Trung bình camera 17.660 FPS, inference 17.431 FPS, wrist 49.866 Hz. 8 ảnh dropped_for_inference; không seq gap được ghi nhận.
- Ghép offline 1061/1063 khung hình với ADC (99.81%); 2 missing; độ lệch tuyệt đối trung bình 4.993 ms, p95 9 ms, tối đa 10 ms. Đây là độ lệch ghép theo timestamp, không chứng minh độ chính xác đồng hồ.
- IMU không có trong toàn bộ phiên. ADC min/max: 0–4095, 813–949, 0–4095, 0–0.
- Cả hai tay `NO_HAND`/missing trong toàn bộ 1063 khung hình; 0 keyframe hành động.
- Chuẩn hóa/ghép/phân đoạn hoàn tất; bước chọn mẫu demo dừng với `No usable demo reference for visible actions in this recording`. Chưa publish backend; chưa xác nhận nhãn trái/phải bằng tay thật.
- Đã yêu cầu người dùng chỉnh camera xuống vùng thao tác rồi báo `camera đã chỉnh`. Sau đó cần thu lại `--headless --duration-s 60 --process --publish`, kiểm tra hành động thật và API/dashboard.

Không xóa hoặc sửa provenance của phiên đã thu. `deployment/inspect-hardware-session.py` hỗ trợ đọc manifest, ADC, trạng thái tay và trích preview từ JPEG gốc.

## Sau khi chỉnh camera: đã publish

`ai/generated_data/sessions/hardware_20261007_142905_239538_mxqm9lvr`

- Capture 61.171 giây: 879 JPEG/inferred frames, 3049 wrist samples, 49.844 Hz wrist. Camera khoảng 17–18 FPS khi nhận ảnh, nhưng hai stream errors và không có ảnh khoảng 10 giây cuối; toàn phiên trung bình 14.370 FPS.
- Tay trái detected 149 frames, tay phải detected 282 frames, cả hai detected cùng lúc 2 frames; 37 frames ambiguous cho mỗi bên. Có nhãn riêng LEFT/RIGHT; chưa có kiểm tra có người đối chiếu bên giải phẫu trực tiếp.
- 39 ảnh hành động, 38 action phases được backend nhận. Ghép offline 877/879 frames, mean absolute offset 5.002 ms, max/p95 10 ms. IMU unavailable toàn phiên; ADC kênh thứ tư vẫn 0.
- So sánh chọn mẫu demo `01_two_hands_reach_grab`; mẫu không phải chuẩn chuyên gia được chứng nhận. Cảm biến mẫu mô phỏng khác nguồn ADC đo thật, nên không tính chênh lệch lực số.
- Lệnh capture xử lý xong nhưng dừng khi in tiêu đề tiếng Việt do cp1252. Đã sửa stdout CLI `record_hardware.py` sang UTF-8 và publish lại từ dữ liệu hiện có thành công.
- Backend session: `MEASURED_hardware_20261007_142905_239538_mxqm9lvr`; export_status COMPLETED. GET detail, analysis-result, recording, source-data, keyframe đều thành công. Video 4312376 bytes, archive 7408457 bytes. Dashboard HTTP 200. Browser automation không có browser khả dụng, nên chưa kiểm tra trực quan UI.
- Kiểm thử sau sửa log: 52 passed, 8 subtests passed; diff check đạt.

## Trạng thái cuối: camera cần phục hồi phần cứng

- Raw kiểm tra tiếp `hardware_raw_20261007_143124_092568_p36rity4`: 0 JPEG, SmartWrist vẫn ~50 Hz.
- Reset COM4 rồi raw `hardware_raw_20261007_143206_280188_5j2tsdxf`: 0 JPEG, 763 wrist samples. Serial boot SmartCap có `TG0WDT_SYS_RESET`, không thấy dòng camera ready; chưa kết luận nguyên nhân.
- Preflight cuối: camera TCP timeout; MQTT và NTP vẫn đạt. Phiên đã publish được giữ nguyên và vẫn truy cập được.
- Đã yêu cầu người dùng rút/cắm lại nguồn SmartCap, kiểm tra cáp/nguồn 5V rồi báo `đã cắm lại SmartCap`. Sau đó đọc serial không reset, preflight/raw để xác minh phục hồi. Không tuyên bố camera đã ổn định liên tục.

## Phục hồi sau cắm lại và sửa thứ tự khởi tạo

- Người dùng xác nhận SmartCap đã bỏ IMU để tối ưu thời gian. SmartCap chỉ dùng camera; `imu_head=null` là chủ đích. MPU6050 unavailable trong MQTT thuộc SmartWrist.
- Bổ sung log boot heap/PSRAM, camera init/error code, heartbeat Wi-Fi/NTP/frame count và các bước `startNetwork` (không in secrets).
- Firmware COM4 build/upload/hash verified. Log chẩn đoán: PSRAM ready, camera init đạt; sau đó dừng tại `Network: initializing WiFi station` và báo `cam_hal: EV-VSYNC-OVF`.
- Chuyển `startNetwork` trước `esp_camera_init` trên SmartCap. Build/upload COM4 đạt; SmartWrist build đạt sau thay đổi header log chung, không nạp lại COM7.
- Một boot ghi `spinlock_release` assertion rồi tự reboot; boot tiếp đạt camera init, WiFi=3, NTP ready. Chưa kết luận nguyên nhân assertion hoặc chứng minh mọi cold boot đều đạt.
- Raw 60 giây `hardware_raw_20261007_144047_922512_2a3gcbiz`: raw_complete, 1035 JPEG, 3003 wrist samples; **17.250 FPS / 50.050 Hz**, không stream errors, seq gaps hoặc malformed MQTT. IMU wrist vẫn unavailable; ADC kênh 4 vẫn 0 trong phiên.
- Mở lại stream raw 15 giây `hardware_raw_20261007_144159_675815_wxwm9s9z` đạt raw_complete, tốc độ khoảng 17–18 FPS và 50 Hz, không lỗi được ghi nhận.
- Serial khi mở lại stream: WiFi=3, IP=192.168.137.111, NTP ready, frames tăng từ 1068 lên 1156; không có reboot trong lượt đọc này.
- Xác nhận phục hồi qua hai lượt thu, chưa tuyên bố ổn định dài hạn. Phiên AI/video/analysis đã publish trước đó không thay đổi provenance.

## Lỗi tái diễn khi dùng dashboard / reload

- Người dùng báo lượt đầu hình mượt, reload rồi nhận timeout JPEG 15 giây. Job `d21ed42f42d2434880484482021ad559` đã completed và publish session `MEASURED_hardware_20261007_144341_614548_vg3d6ibp`. Các job tiếp theo lưu 0 JPEG, vẫn nhận SmartWrist.
- Không thấy tiến trình frontend_capture còn chạy hoặc socket camera còn giữ lúc kiểm tra. Frontend hiện khôi phục job ID từ sessionStorage và GET status/preview; reload không tự POST tạo capture mới. Chưa có bằng chứng consumer trùng.
- Serial COM4: `TG1WDT_SYS_RESET` rồi dừng tại `Network: initializing WiFi station`, trước khi khởi tạo camera; camera TCP timeout, MQTT/NTP đạt. Đây là lỗi bo/network khởi động hiện có, không thể kết luận do reload.
- Sửa phòng vệ nhánh timestamp không tăng để không busy-spin; đóng stream sau 2 giây không có timestamp mới. HTTP max sockets 2, LRU purge, send/recv timeout 2 giây cho reconnect trong lúc socket cũ đóng. Vẫn một stream handler đồng bộ.
- Receiver ghi `last_stream_error` vào snapshot và manifest; timeout in diagnostics vào run.log, không chỉ đếm stream_errors. Test recovery kiểm tra trường lỗi; 52 tests + 8 subtests đạt.
- Build/upload firmware COM4 hash verified; API job `582dfc18e83e47069095afedba793d08` vẫn timeout sau sửa, vì bo vẫn watchdog trong Wi-Fi init. Chưa kiểm chứng reconnect live thành công với bản mới này.
- Đã hỏi người dùng cách cấp nguồn (CAM-MB/USB–UART), đề nghị thử cáp/nguồn 5V khác. Chưa chẩn đoán nguồn hỏng; cần kiểm tra hardware/firmware tiếp. Không tăng timeout để che lỗi, không xóa dữ liệu cũ.

## Khoanh vùng nguồn sau xác nhận ESP32-CAM-MB

- Người dùng cấp nguồn qua ESP32-CAM-MB. Target chẩn đoán `smartcap_wifi_diag` chỉ Wi-Fi và đặt OV2640 PWDN high, không init camera.
- Một boot chẩn đoán kết nối/NTP đạt; boot tiếp watchdog và `IllegalInstruction`. Decode backtrace từ ELF chẩn đoán chỉ ra radio PHY init: `correct_rfpll_offset`, `register_chipv7_phy`, `esp_phy_load_cal_and_init`, `wifi_hw_start`. Lỗi vẫn có khi camera powered down.
- Khôi phục target `smartcap`, build/upload COM4 SUCCESS/hash verified. Firmware giữ OV2640 powered down khi khởi tạo radio, chờ Wi-Fi tối đa 15 giây rồi để driver cấp lại camera.
- Serial cuối ghi rõ `Brownout detector was triggered` trong bước khởi tạo Wi-Fi, rồi software reset. Đây là bằng chứng điện áp bo giảm tới ngưỡng brownout; chưa xác định sụt áp do cáp, cổng, MB/regulator hay bộ phận khác.
- Preflight cuối camera TCP timeout, MQTT/NTP đạt. Chưa chạy được hai phiên dashboard nối tiếp/reload sau sửa.
- Cần thử cáp USB/cổng cấp nguồn khác ổn định cho ESP32-CAM-MB rồi kiểm tra lại. Không disable brownout protection; giữ dữ liệu đã thu. Target chẩn đoán có trong repo để tái kiểm tra, nhưng firmware hiện trên COM4 là camera bình thường.

## Sau người dùng đổi cáp/cổng: hai phiên hoàn tất

- Windows đổi SmartCap CH340 sang COM5; SmartWrist vẫn COM7. Cấu hình upload/monitor đã cập nhật; không cần nạp lại firmware vì chuyển USB port.
- Job `3bdc163511f44b3d9bde4e1f035e85ef` completed/publish `MEASURED_hardware_20261007_150222_805884_vbnd6kdk`: 53.844 giây, 416 JPEG/410 inferred frames, 7.726 FPS camera, 49.922 Hz wrist, 410/410 ghép ADC, không stream error; backend 10 keyframes/10 phases, export COMPLETED.
- Job tiếp `e05ec83591ee489582aacfc244ed5508` nhận ảnh khoảng 111.5 giây rồi failed `Camera sequence or clock reset` trong lúc agent mở serial COM5 không --reset. Serial nhận boot ngay khi mở; có thể driver/MB pulse reset. Không quy kết lượt này là lỗi reload hoặc brownout sau đổi cáp. Dữ liệu được giữ, không ghép qua reboot.
- Đã lặp lại không mở serial: job `6d334e7f67cf40bdb5d7388e3f681031` completed/publish `MEASURED_hardware_20261007_150625_216050_uk5sxhc9`: 92.343 giây, 1555 JPEG và 1555 inferred frames, **16.839 FPS camera / 49.923 Hz wrist**, không stream errors hoặc wrist seq gaps được ghi nhận. Backend 21 keyframes/21 phases, export COMPLETED.
- Trong lượt cuối, GET HTML dashboard HTTP 200, GET status cùng job ID vẫn recording; frame tăng từ 1093 (63.932 s) tới 1553 (91.395 s). Xác minh đường HTTP/API khi reload; chưa trực tiếp kiểm tra lifecycle React bằng browser automation.
- `deployment/read-serial.py` docstring ghi rõ mở serial có thể reset ESP32-CAM-MB qua driver, chỉ dùng khi thu đã dừng, kể cả không --reset. Chưa dùng serial sau lượt cuối để tránh can thiệp lại.
- Camera phục hồi trong các lượt kiểm tra sau đổi cáp/cổng; không kết luận ổn định dài hạn hoặc linh kiện chính xác gây sụt điện áp trước đó. Các phiên lỗi trước được giữ nguyên.
