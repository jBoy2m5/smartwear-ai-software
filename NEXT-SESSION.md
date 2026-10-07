# Tiến trình SmartWear AI — bàn giao phiên tiếp theo

Cập nhật: 07/10/2026. Mở file này trước khi tiếp tục công việc.

## Mục tiêu còn đang làm

### Trạng thái mới nhất sau đổi cáp/cổng USB

Kiểm tra nhấn FSR 60 giây: nhận 3003 MQTT samples; min/max bốn ADC (GPIO32/33/34/35) lần lượt **0–4095, 0–942, 0–917, 0–0**. Kênh 1 có các đợt tăng/giảm rõ; kênh 2/3 có biến động nhưng chưa đối chiếu từng cảm biến độc lập; kênh 4 chưa phản hồi. Không kết luận đủ bốn FSR hoạt động hoặc chuyển ADC sang Newton. Dữ liệu: `docs/layer1-layer3/fsr-press-20261007.jsonl`; công cụ `deployment/monitor-fsr.py` chỉ dùng MQTT, không mở serial/camera.

- Người dùng đã đổi cáp/cổng. **SmartCap hiện COM5**, SmartWrist COM7; PlatformIO và RUNBOOK đã cập nhật theo cổng Windows thực tế.
- Hai phiên dashboard/API không truy cập serial trong lúc quay đã **completed và publish**: `MEASURED_hardware_20261007_150222_805884_vbnd6kdk` (10 keyframes/phases) và `MEASURED_hardware_20261007_150625_216050_uk5sxhc9` (21 keyframes/phases).
- Lượt cuối: 92.343 giây, 1555 JPEG/inferred frames, **16.839 FPS camera / 49.923 Hz wrist**, không stream errors hoặc seq gaps được ghi nhận. Tải lại HTML qua HTTP và GET lại cùng job ID vẫn recording, preview frame tiếp tục tăng. Chưa kiểm tra reload bằng browser automation vì không có browser khả dụng.
- Lượt ở giữa `e05ec83591ee489582aacfc244ed5508` bị camera sequence/clock reset trong lúc agent mở serial COM5. Serial boot xuất hiện ngay thời điểm đó; việc mở serial có thể reset ESP32-CAM-MB qua driver dù không có `--reset`. **Không mở serial/monitor, reset hoặc upload khi đang thu raw/AI.** Đã sửa docstring script để ghi rõ.
- Không cần tiếp tục thay firmware khi camera đang chạy ổn định. Người dùng có thể reload rồi bấm `Quay ESP32 + vòng tay` để tạo phiên mới; phiên lỗi cũ trong sessionStorage không đại diện trạng thái phần cứng hiện tại.
- SmartCap không dùng IMU theo chủ đích; SmartWrist IMU vẫn unavailable, bốn ADC giữ nguyên dữ liệu thật. Brownout từng được ghi trước đổi cáp; chưa đo điện áp để kết luận linh kiện nào gây sụt áp hoặc ổn định dài hạn.

Các mục sau là lịch sử chẩn đoán trước/sau trong ngày, không thay thế trạng thái mới nhất ở trên.

### Kết quả tiếp tục ngày 07/10/2026

**Trạng thái mới nhất sau lỗi reload dashboard:** Camera lại không phục hồi ổn định. Phiên dashboard `d21ed42f42d2434880484482021ad559` đã completed/publish `MEASURED_hardware_20261007_144341_614548_vg3d6ibp`; các phiên sau không có JPEG. Serial COM4 xác nhận watchdog `TG1WDT_SYS_RESET`, dừng ở `Network: initializing WiFi station` ngay cả trước camera init. Không có tiến trình capture còn giữ stream ở lúc kiểm tra; chưa có bằng chứng reload tạo consumer trùng. Lượt thu raw 60+15 giây đạt bên dưới chỉ là kiểm chứng trước thời điểm lỗi tái diễn.

**Cập nhật cuối sau xác nhận cấp nguồn ESP32-CAM-MB:** Đã thử target `smartcap_wifi_diag` chỉ Wi-Fi, OV2640 PWDN high: vẫn watchdog/IllegalInstruction trong khởi tạo radio PHY (`correct_rfpll_offset`, `esp_phy_load_cal_and_init`), không phải lỗi cần camera hoạt động. Đã khôi phục/nạp target `smartcap` COM4 SUCCESS/hash verified; firmware giữ sensor powered down trong Wi-Fi startup, chờ kết nối tối đa 15 giây rồi init camera. Log sau khôi phục ghi rõ **`Brownout detector was triggered`** tại Wi-Fi init: có bằng chứng bo phát hiện sụt điện áp. Camera vẫn TCP timeout; MQTT/NTP đạt. Cần thử cáp USB khác và cổng USB trực tiếp/nguồn ổn định cho MB; chưa xác định cáp, cổng hay MB là linh kiện gây sụt áp. Không vô hiệu hóa brownout detector. Bản chẩn đoán không còn nằm trên bo; normal/default targets vẫn smartcap/smartwrist.

- Đã sửa phòng vệ firmware: nhường CPU ở nhánh timestamp camera không tăng, đóng stream sau 2 giây timestamp đứng; HTTP cho tối đa 2 sockets để nối lại khi socket cũ đóng, vẫn một handler stream đồng bộ; bật LRU purge và send/recv timeout 2 giây. Nạp COM4 SUCCESS/hash verified.
- `camera_receiver.py` lưu `last_stream_error`; `record_hardware.py` in thống kê kết nối trước timeout. Kiểm thử 52 passed, 8 subtests passed.
- Phiên API kiểm tra `582dfc18e83e47069095afedba793d08` vẫn failed timeout sau sửa. **Chưa xác nhận sửa hết lỗi hoặc có thể quay lại bình thường.**
- Đang chờ người dùng cho biết nguồn SmartCap (ESP32-CAM-MB hay USB–UART) và thử cáp/nguồn 5V khác ổn định. Không kết luận nguồn hỏng; cần phân biệt phần cứng với firmware. Sau khi đổi nguồn, kiểm tra log không reset rồi chạy hai phiên dashboard start/stop nối tiếp và phục hồi status sau reload.

- SmartCap xác nhận bằng log boot trên **COM4**, SmartWrist **COM7**. `firmware/platformio.ini` và RUNBOOK đã cập nhật.
- Bản firmware tách tác vụ I2C đã build SUCCESS, upload COM7 SUCCESS, hash flash verified.
- Kiểm thử sau thay đổi cuối: **52 passed, 8 subtests passed**; frontend TypeScript/Vite build đạt; `git diff --check` đạt.
- Backend đã khởi chạy, `/health` = `ok`, `/ready` = `ready`, dashboard `http://127.0.0.1:8000/`. Luôn kiểm tra tiến trình/cổng trước khi khởi chạy lại.
- Kiểm tra mạng đầu phiên chưa có `192.168.137.1` (adapter hotspot đang là địa chỉ link-local); chưa có MQTT/NTP nghe cổng. Đã yêu cầu người dùng bật hotspot `ok123`, 2.4 GHz và đặt camera đủ sáng.
- Sau reset, SmartCap chờ Wi-Fi/NTP; SmartWrist `WiFi=1`, `NTP=waiting`, `MQTT=waiting`, `published=0`; MPU6050 vẫn không trả lời `0x68/0x69`.
- Người dùng đã bật hotspot; preflight camera/MQTT/NTP đạt. Raw 15 giây đạt **50.269 Hz wrist / 17.839 FPS camera**, không seq gap hoặc malformed MQTT. Phiên raw: `hardware_raw_20261007_142220_851221_7ohbgvuf`.
- AI 60 giây đã thu và chuẩn hóa: **3041 wrist samples, 1077 JPEG, 1063 inferred frames**, wrist **49.866 Hz**; ghép offline 1061/1063 frames. IMU vẫn unavailable, ADC kênh 4 luôn 0 trong phiên.
- Camera hướng lên trần/đèn, cả hai tay `NO_HAND` toàn bộ phiên, nên chọn mẫu tham chiếu dừng và **chưa publish**. Không đổi vai trò hoặc tạo hành động giả để vượt qua điều kiện này. Phiên AI: `hardware_20261007_142254_436256_i1uwuwl2`.
- Sau khi người dùng chỉnh camera, phiên `hardware_20261007_142905_239538_mxqm9lvr` đã nhận diện LEFT/RIGHT riêng (149/282 frames detected, 2 frames cả hai), xử lý và **publish thành công**: `MEASURED_hardware_20261007_142905_239538_mxqm9lvr`. Backend có 39 keyframes, 38 phases, video, archive nguồn và phân tích; các GET API đạt, dashboard HTTP 200. Chưa đối chiếu bên giải phẫu bằng người xem hoặc kiểm tra trực quan dashboard vì browser automation không khả dụng.
- Đã sửa stdout CLI `ai/hardware/record_hardware.py` sang UTF-8 để tránh lỗi in tiêu đề tiếng Việt trên Windows. Tests sau sửa: 52 passed, 8 subtests passed.
- **Camera chưa ổn định**: phiên có hai stream errors, mất ảnh khoảng 10 giây cuối. Hai lượt raw tiếp theo không có JPEG; reset COM4 cho log watchdog `TG0WDT_SYS_RESET`, chưa thấy camera ready. Preflight cuối camera timeout, MQTT/NTP đạt, wrist vẫn ~50 Hz. Chưa xác định nguyên nhân vật lý/firmware.
- Người dùng xác nhận đã bỏ IMU trên SmartCap để tối ưu thời gian; SmartCap chỉ dùng OV2640, `imu_head=null` là chủ đích. Lỗi MPU6050 unavailable thuộc **SmartWrist**, không phải SmartCap.
- Sau cắm lại, đã bổ sung log boot/PSRAM/camera và từng bước mạng, nạp COM4 hash verified. Log cho thấy camera init đạt nhưng dừng tại `WiFi.mode(WIFI_STA)` khi camera khởi tạo trước. Đã chuyển SmartCap sang khởi tạo Wi-Fi/NTP trước camera; cả hai target firmware build đạt. COM7 vẫn chạy bản đã upload trước đó (header mới chỉ thêm log, chưa nạp lại COM7).
- **SmartCap hiện phục hồi**: raw 60 giây `hardware_raw_20261007_144047_922512_2a3gcbiz` đạt 1035 JPEG (**17.250 FPS**), 3003 wrist (**50.050 Hz**), không stream errors/seq gaps/malformed MQTT. Mở lại stream raw 15 giây `hardware_raw_20261007_144159_675815_wxwm9s9z` cũng raw_complete và không lỗi.
- Serial sau đo: `WiFi=3`, NTP ready, frames tăng. Một boot sau đổi thứ tự đã có spinlock assertion rồi tự reboot trước khi phục hồi; chưa chứng minh hết lỗi boot ngắt quãng hoặc ổn định lâu dài. Giữ log chẩn đoán để theo dõi; không cần gắn lại IMU đầu.
- Chi tiết: `docs/layer1-layer3/VERIFICATION-20261007.md`. Phiên AI đã publish được giữ nguyên; dữ liệu raw kiểm tra sau phục hồi là các phiên mới riêng biệt.

Các trạng thái bên dưới là lịch sử ngày 06/10, không thay thế kết quả mới ở trên.

1. Cho SmartWrist phát dữ liệu phần cứng ổn định, giữ bốn kênh ADC ngay cả khi IMU không có tín hiệu.
2. Nhận diện và hiển thị riêng tay trái, tay phải trên dashboard, không tự mặc định một tay là tay phải.
3. Sau khi kiểm tra dây cảm biến và hướng camera, chạy lại một phiên thật từ thiết bị → AI → backend → giao diện.

## Phần cứng và mạng đã xác nhận

- SmartCap hiện là **COM5** sau đổi cáp/cổng USB ngày 07/10/2026 (đầu phiên COM4; MAC `30:76:f5:e5:66:d8`). Cấu hình upload/monitor theo cổng hiện tại.
- SmartWrist là **COM7** (CP210x, MAC `68:09:47:df:56:00`).
- Hotspot của máy chủ: `192.168.137.1`; SmartCap `192.168.137.111`; SmartWrist `192.168.137.100`.
- MQTT `192.168.137.1:1883`, topic `wearable/user01/wrist/data`; NTP UDP 123.
- Trước khi thử lần sau, kiểm tra hotspot, camera, broker và NTP. Kết quả kiểm tra cũ có thể hết hạn: xem `docs/layer1-layer3/current-preflight.json`.

## Những gì đã thay đổi trong mã

- `firmware/src/smartwrist.cpp`: dò MPU6050 tại `0x68`/`0x69`, xác thực `WHO_AM_I`, thử kết nối lại; khi IMU lỗi, ghi `acc`/`gyro` là `null` và tiếp tục gửi ADC; thêm log Wi-Fi, NTP, MQTT và số bản tin. Một sửa đổi mới nhất tách tác vụ đọc I2C khỏi lấy mẫu ADC và thêm `imu_age_ms` để I2C lỗi không chặn ADC.
- `ai/hardware/mqtt_wrist.py`, `ai/hardware/align.py`, `ai/hardware/live_alignment.py`: nhận IMU thiếu một cách tường minh; vẫn giữ ADC đã đo và không tạo số mô phỏng.
- `ai/camera_test.py`, `ai/hand_observation.py`, `ai/hardware/record_hardware.py`: bỏ quy tắc ép bàn tay duy nhất thành tay phải; giữ trái/phải theo handedness của MediaPipe sau khi lật hình; hiển thị cả hai nhãn khi chạy camera.
- `ai/integration/frontend_capture.py`, `frontend/src/backendApi.ts`, `frontend/src/components/CapturePanel.tsx`: gửi tọa độ và nhãn riêng từng tay lên dashboard, vẽ màu riêng, hiện trạng thái IMU.
- `ai/hardware/test_hardware.py`: kiểm thử từng tay, thứ tự tay thay đổi, trường hợp phân loại mơ hồ và dữ liệu ADC khi thiếu IMU.
- Các chỉnh sửa có sẵn từ lượt trước: `backend/tests/test_capture_manager.py`, `ai/hardware/DATA_FORMATS.md`, `docs/layer1-layer3/CONTRACT.md`, `deployment/read-serial.py`, báo cáo `docs/layer1-layer3/VERIFICATION-20261006-EVENING.md`.

## Trạng thái thực tế gần nhất

- Mã sửa nhận diện hai tay và dashboard đã build Vite/TypeScript thành công. Kiểm thử Python gần nhất: **52 passed, 8 subtests passed**. Đây là kết quả trước sửa đổi cuối cùng tách task IMU và thêm `imu_age_ms`; phải chạy lại kiểm tra.
- SmartWrist firmware trước sửa đổi tách task đã build và upload COM7 thành công, hash flash xác minh đạt. Log xác nhận `WiFi=3 IP=192.168.137.100 NTP=ready MQTT=connected` và `published` tăng. MQTT đã nhận các payload thật có bốn ADC, `acc:null`, `gyro:null`, `imu_status:"unavailable"`. Nhiều bản tin hoàn chỉnh được ghi trong `hardware_raw_.../wrist_raw.jsonl`.
- Serial COM7 vẫn báo không có MPU tại cả `0x68` lẫn `0x69`. Đây là vấn đề phía cảm biến/dây thực tế cho đến khi I2C tìm thấy thiết bị. Kiểm tra **SDA GPIO21, SCL GPIO22, VCC 3.3V, GND chung, AD0/GND** và xác nhận bo cảm biến thực sự là MPU6050. Firmware cần tiếp tục phát ADC kể cả khi IMU chưa sửa.
- SmartWrist thực tế đo khoảng 20–30 Hz trong lượt thử; mục tiêu firmware là 50 Hz. Lượt đó chưa đạt tốc độ mục tiêu và cũng chưa đạt phiên end-to-end.
- SmartCap từng phát ảnh QVGA khoảng 18 FPS sau reset. Lượt kiểm tra mới nhất lại timeout; `current-preflight.json` cuối phiên báo MQTT/NTP đạt, camera timeout. Camera và SmartWrist có thể cần reset lại sau khi hotspot hoạt động.
- Ảnh ESP32 đã xem ở lượt trước gần như đen và không có tay, nên chưa xác nhận đúng nhãn bằng thao tác thật. Cần đủ sáng, đặt camera thấy rõ cả tay, kiểm tra tay trái và tay phải xuất hiện riêng trên preview.
- Tệp firmware hiện tại có sửa đổi task I2C riêng **sau lần upload thành công gần nhất**. Cần build trước; nếu build đạt thì nạp lại COM7 rồi kiểm tra log và MQTT. Tình trạng tiến trình backend/MQTT/NTP có thể thay đổi khi bắt đầu phiên sau; kiểm tra trước khi khởi chạy để tránh mở trùng cổng.

## Tiếp tục từ PowerShell tại thư mục gốc

```powershell
cd D:\MyProject\Denso2\smartwear-ai-software
```

Kiểm tra build/tests/giao diện sau sửa đổi cuối:

```powershell
$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location) '.platformio'
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartwrist
.\.venv\Scripts\python.exe -B -m pytest ai\hardware backend\tests -q
npm.cmd run build --prefix frontend
git diff --check
```

Nếu build SmartWrist đạt, nạp firmware mới vào đúng cổng:

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e smartwrist -t upload --upload-port COM7
```

Sau đó đọc log boot và trạng thái thiết bị (script `--reset` phát xung reset EN/RTS; chỉ chạy khi dừng phiên thu):

```powershell
.\.venv\Scripts\python.exe deployment\read-serial.py COM5 COM7 --reset
```

Kiểm tra dịch vụ/thiết bị và chạy thử thu raw trong khi camera không bị ứng dụng khác mở:

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\preflight.py --output docs\layer1-layer3\current-preflight.json
.\.venv\Scripts\python.exe -B ai\hardware\raw_capture.py --duration-s 15
```

Xem `raw_capture.json` và `wrist_raw.jsonl` trong thư mục phiên được lệnh in ra. Xác nhận JSON hợp lệ, tốc độ mẫu, seq gap, số ảnh, status IMU và các giá trị ADC. Sau khi phần cứng đầu vào ổn định:

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --publish
```

Xem dashboard tại `http://127.0.0.1:8000/`. Kiểm tra cả hai tay trong preview và dữ liệu phiên ở backend.

## Cần nhớ khi kiểm tra tay trái/phải

Ảnh inference được lật bằng `cv2.flip(frame, 1)`. `anatomical_handedness()` hoán đổi nhãn model một lần để ánh xạ từ ảnh lật sang bên giải phẫu. Không gán phía theo vị trí trên ảnh hay theo giả định rằng chỉ có tay phải. Hai tay có thể được phát hiện theo thứ tự khác nhau; khi duplicate/unknown, kết quả là `ambiguous`. Xác nhận bằng cách đưa từng tay vào ảnh, rồi thử cả hai cùng lúc. Các hành động vẫn là nhận diện tư thế bàn tay, không chứng minh đã nắm vật.

## Bằng chứng phiên trước

- Log serial có thể đọc lại từ bo đang cắm; thông tin trước đây gồm MPU không trả lời nhưng Wi-Fi/NTP/MQTT đạt sau bản firmware có ADC fallback.
- Phiên raw SmartWrist có ADC thật: `ai/generated_data/sessions/hardware_raw_20261006_190722_267386_8jh5m_pc` (camera không ảnh ở thời điểm đó).
- Phiên capture camera/API trước đây có thể được tham chiếu trong `docs/layer1-layer3/VERIFICATION-20261006-EVENING.md`.
- Dự án có phiên dữ liệu bị khóa quyền truy cập bởi môi trường chạy. Đừng xóa hoặc ghi đè dữ liệu phiên cũ; tạo phiên mới theo script.
