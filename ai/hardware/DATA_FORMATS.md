# SmartWear AI — hợp đồng và đường đi dữ liệu

Tài liệu này mô tả **code hiện tại đang nhận và tạo dữ liệu gì**. Các con số trong
khối ví dụ chỉ minh họa cấu trúc, **không phải dữ liệu phần cứng đã đo**. Đây là
tài liệu trao đổi giữa nhóm phần cứng, AI, backend và frontend; khi firmware đổi
format, phải sửa bộ nhận và kiểm thử cùng lúc.

## 1. Nhìn toàn bộ luồng

```text
SmartWrist -- JSON từng mẫu qua MQTT ----┐
                                         ├─> AI lưu raw ─> ghép theo giờ thiết bị
ESP32-CAM -- JPEG liên tục qua HTTP -----┘                 ─> nhận diện tay phải
                                                           ─> chia hành động, ảnh, phân tích
                                                           ─> backend ─> frontend
```

**Phần cứng không gửi `real_sensors.jsonl`, `analysis_result.json` hay payload
`/sessions/ingest`.** Đó là dữ liệu AI tạo *sau khi nhận* hai luồng đầu vào.
Trong một file `.jsonl`, **mỗi dòng là một JSON hoàn chỉnh**; file `.json` thường
chứa một JSON cho cả tài liệu.

## 2. Input thật số 1: SmartWrist → MQTT

| Mục | Code hiện chờ |
| --- | --- |
| Broker | `192.168.0.109`, cổng TCP `1883` |
| Topic | `wearable/user01/wrist/data` (đúng cả chữ hoa/thường) |
| Cách gửi | Mỗi lần đo publish **một JSON object UTF-8**, tối đa 4096 byte; subscriber dùng QoS 0 |
| Mục tiêu tốc độ | Khoảng 50 mẫu/giây; đây là mục tiêu, không phải số đã nghiệm thu |
| Tay đeo | Tay phải theo cấu hình hiện tại |

**Ví dụ hợp lệ về cấu trúc** (không phải số đo thực):

```json
{"t_ms": 1791110000000, "seq": 123, "acc": [0.01, 0.02, 1.0], "gyro": [0.0, 0.0, 0.0], "force": [120, 340, 560, 780]}
```

| Trường | Kiểu và giới hạn code kiểm tra | Ý nghĩa |
| --- | --- | --- |
| `t_ms` | Số nguyên, Unix epoch **mili giây**, từ `1577836800000` trở đi | Thời điểm **thiết bị lấy mẫu**, không phải lúc PC nhận MQTT |
| `seq` | Số nguyên `>= 0` | Số thứ tự mẫu; tăng theo mẫu, có thể reset khi thiết bị khởi động lại |
| `acc` | Mảng **đúng 3 số hữu hạn** | Ba trục gia tốc từ firmware; **đơn vị chưa xác minh** |
| `gyro` | Mảng **đúng 3 số hữu hạn** | Ba trục vận tốc góc từ firmware; **đơn vị chưa xác minh** |
| `force` | Mảng **đúng 4 số nguyên**, mỗi số trong `0..4095` | Bốn kênh ADC thô; **không phải Newton hoặc sEMG** |

Sai tên trường (`fsr` thay `force`), thiếu một phần tử, `NaN`, giờ không hợp lệ
hoặc ADC ngoài phạm vi sẽ bị loại và tăng bộ đếm `malformed`. Code nhận **không
đòi firmware gửi** `device_id`, `generation`, `received_epoch_ms`, `topic` hay
`raw_payload`; các thông tin đó do AI cấu hình/tự thêm sau khi nhận. Thứ tự
bốn kênh ADC phải được nhóm phần cứng cung cấp riêng: hiện **chưa xác nhận kênh
nào nằm ở vị trí nào trên tay**. Xem [bộ kiểm tra MQTT](mqtt_wrist.py).

### AI lưu lại tin MQTT: `wrist_raw.jsonl`

Mỗi dòng giữ lại năm trường gốc ở trên, đồng thời AI thêm:

| Trường AI thêm | Ý nghĩa |
| --- | --- |
| `raw_payload` | Nguyên văn chuỗi JSON firmware gửi, dùng đối chiếu lỗi |
| `topic` | Topic đã nhận |
| `received_epoch_ms` | Giờ **máy tính nhận** tin; khác với `t_ms` |
| `generation` | Bộ đếm do AI tăng khi `seq` hoặc giờ thiết bị reset |

Đây là **file AI lưu**, không phải file firmware phải truyền qua mạng. Mẫu lỗi,
mẫu bị mất hoặc reset được ghi vào thống kê của phiên; tin sai định dạng không
được ghi như mẫu hợp lệ.

## 3. Input thật số 2: ESP32-CAM → HTTP MJPEG

AI thực hiện HTTP `GET` tới `http://<IP-camera>:81/stream`. IP có thể đổi sau
khi camera kết nối Wi-Fi; mặc định trong code cũ là `.101`, còn lần người dùng
mở gần đây là `.111`. **Phải cấu hình `SMARTWEAR_CAMERA_URL` theo IP đang dùng.**

Response hợp lệ có `Content-Type: multipart/x-mixed-replace; boundary=...`.
Mỗi phần của luồng chứa header và byte ảnh như sau (minh họa):

```text
--<boundary>
Content-Type: image/jpeg
Content-Length: <số byte JPEG>
X-Timestamp-Ms: <Unix epoch mili giây lúc camera chụp>
X-Frame-Seq: <số thứ tự ảnh>

<byte ảnh JPEG; không phải chuỗi JSON>
```

| Thành phần | Code hiện kiểm tra |
| --- | --- |
| `Content-Length` | Số nguyên dương, tối đa **2.000.000 byte** |
| `X-Timestamp-Ms` | Epoch mili giây từ `1577836800000` trở đi |
| `X-Frame-Seq` | Số nguyên `>= 0` |
| JPEG | Bắt đầu/kết thúc đúng marker JPEG; giải mã được để AI xử lý |
| Thứ tự | `X-Frame-Seq` **và** giờ camera tăng qua các ảnh trong một phiên |

Header mỗi phần không phân biệt chữ hoa/thường. Camera báo HTTP 503 hoặc
`NTP not synchronized` thì **chưa có ảnh hợp lệ**; không thay giờ camera bằng giờ
PC để che lỗi. Trình duyệt đang giữ `/stream` có thể chiếm kết nối duy nhất
của firmware, nên đóng tab đó trước khi quay trên dashboard. Xem
[parser MJPEG](mjpeg.py) và [bộ nhận camera](camera_receiver.py).

### AI lưu lại luồng camera

| File trong thư mục phiên | Format | Nội dung |
| --- | --- | --- |
| `camera_raw.mjpeg` | Byte nhị phân | Các JPEG **nguyên gốc nối tiếp** do bộ nhận ghi; tên `.mjpeg` không có nghĩa đây là một file video MP4 hoặc JSON |
| `camera_packets.jsonl` | Một JSON/dòng ảnh | `seq`, `epoch_ms`, `received_epoch_ms`, `offset`, `length`, `sha256` để tìm đúng JPEG trong file raw |
| `camera.jsonl` | Một JSON/dòng ảnh đã xử lý | Thời gian tương đối, điểm bàn tay phải và nhãn camera suy đoán |
| `camera.avi` | Video AVI | Khung hình đã giải mã và ghi cho phiên, có thể ít hơn số JPEG raw khi AI xử lý không kịp |
| `camera.video.json` | JSON manifest | Tên video, kích thước, số frame và hash ghép video với `camera.jsonl` |

`camera_packets.jsonl` có thể có nhiều dòng hơn `camera.jsonl`, vì bộ nhận
ưu tiên giữ JPEG gốc nhưng có thể bỏ bớt frame khỏi hàng đợi AI. Mỗi dòng
`camera.jsonl` dùng schema `smartwear.camera_raw.v2` và có các nhóm chính:

```text
schema_version = "smartwear.camera_raw.v2"
timestamp                   # mili giây tương đối từ ảnh đầu tiên của phiên
camera = {frame_width, frame_height}
hands = [bàn tay phải với 21 landmarks + 21 world_landmarks, nếu nhìn thấy]
hand_actions = {left: ..., right: ...}
source_epoch_ms             # X-Timestamp-Ms từ ESP32-CAM
source_frame_seq            # X-Frame-Seq từ ESP32-CAM
received_epoch_ms           # giờ PC nhận ảnh
video_frame_index           # vị trí khung hình tương ứng trong camera.avi
```

`hand_actions.right` chứa `label`, `hand_state`, `source`, `tracking_status`,
`hand_index`. Nhãn có thể là `OPEN`, `REACH`, `GRAB`, `ASSEMBLY`, `RELEASE`,
`OTHER`, `NO_HAND`. Đây là **ước lượng từ hình bàn tay**, không chứng minh
người dùng đã nắm/lắp một vật thật. Nhánh phần cứng chỉ đưa **tọa độ tay phải**
vào `hands`; schema vẫn có khóa `left` với trạng thái `NO_HAND`/`missing` để
pipeline cũ đọc được. Xem [camera_test.py](../camera_test.py) và
[hand_observation.py](../hand_observation.py).

## 4. AI ghép hai nguồn theo giờ thiết bị

1. `camera.normalized.jsonl`: mỗi dòng từ `camera.jsonl` thành
   `smartwear.camera.v2`, thêm `frame_id`, `timestamp_ms`, `relative_time_s`,
   giữ `source_epoch_ms`/`source_frame_seq`.
2. AI tìm mẫu SmartWrist có `t_ms` **gần nhất** với `source_epoch_ms` của mỗi
   ảnh. Ngưỡng mặc định là **±40 ms**; ngoài ngưỡng là `missing`, không giữ số
   cũ mãi hoặc sinh số giả. NTP trên hai thiết bị cần hoạt động, nhưng ghép
   trong ±40 ms **không chứng minh** sai số đồng hồ thực nhỏ hơn 40 ms.
3. `real_sensors.jsonl`: một dòng `smartwear.sensors.v2` **cho mỗi ảnh đã chuẩn
   hóa**, kể cả ảnh không ghép được cảm biến. Ví dụ cấu trúc của một dòng đã
   ghép (số minh họa):

```json
{
  "schema_version": "smartwear.sensors.v2",
  "sensor_source": "measured_hardware",
  "timestamp_ms": 1000,
  "imu_head": null,
  "hand_sensors": {
    "left": {"tracking_status": "missing", "imu_wrist": null, "force_emg_raw": null, "force_adc": null, "torque": null},
    "right": {
      "tracking_status": "detected",
      "sensor_status": "matched",
      "imu_wrist": {"ax": 0.01, "ay": 0.02, "az": 1.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
      "force_emg_raw": null,
      "force_adc": [120, 340, 560, 780],
      "force_channel": null,
      "torque": null,
      "source_epoch_ms": 1791110000020,
      "source_seq": 123,
      "alignment_offset_ms": 20
    }
  }
}
```

`alignment_offset_ms = t_ms của vòng tay - giờ chụp của camera`. `null` ở
`force_emg_raw` là có chủ ý: khi chưa biết chọn kênh ADC nào, AI giữ **cả bốn
số ở `force_adc`**. Nếu có cấu hình `force_channel` từ 0 đến 3, trường
`force_emg_raw` chứa đúng ADC của kênh đó, **vẫn không phải Newton/sEMG**.
`imu_head` và `torque` là `null` vì hiện không có nguồn đo hai đại lượng đó.
Nếu không tìm thấy mẫu vòng tay trong ngưỡng, `sensor_status` là `missing` và
các giá trị đo của dòng đó là `null`.

4. `real_sensors.meta.json`: một JSON `smartwear.sensors_meta.v2`, có
   `source: "measured_hardware"`, `sample_count`, `matched_count`,
   `missing_count`, `alignment_window_ms`, phân bố độ lệch, `device_id`,
   `force_channel`, `calibration_id`, `units`, hash SHA-256 của các file nguồn
   và `simulated_fields: []`. Đơn vị lực là `adc_count`; đơn vị `acc`/`gyro`
   ghi là **chưa xác minh từ firmware**.
5. `multimodal.jsonl`: một dòng `smartwear.multimodal.v2` cho mỗi ảnh, kết hợp
   camera chuẩn hóa và dòng sensor cùng `timestamp_ms`; chứa `hands`,
   `hand_actions`, `hand_sensors`, `imu_head`, `provenance`. Khi dùng phần cứng,
   `provenance.sensors` là `measured_hardware` và `simulated_fields` rỗng.

Xem [align.py](align.py), [normalize_camera.py](../preprocessing/normalize_camera.py)
và [build_multimodal.py](../preprocessing/build_multimodal.py).

## 5. File phân tích sau khi ghép

| File | Format chính | Vai trò |
| --- | --- | --- |
| `action_segments.json` | `smartwear.action_segments.v2` | `segments[]` có `segment_id`, `hand`, `label`, `start_ms`, `end_ms`, `duration_ms`, số frame và trạng thái nhìn thấy tay; nhánh mới chỉ có hành động nhìn thấy ở tay phải |
| `keyframes.json` | `smartwear.keyframes.v1` | `entries[]` chỉ đoạn nào lấy được ảnh đại diện, frame nào, `image_path` nào |
| `keyframes/*.png` | Ảnh PNG | Ảnh thật từ video, dùng kiểm tra lại hành động/nghi vấn |
| `session_role.json` | `smartwear.session_role.v1` | Vai trò `expert`, `worker` hoặc `demo_reference` và hash của file đoạn hành động |
| `analysis_result.json` | `smartwear.analysis_comparison.v2` | Có ở phiên công nhân được so với mẫu: `hands.right.alignment` (các cặp so), `review_candidates`, `sensor_comparison`, `muda_review`, ảnh và thời điểm cần xem lại |

Một cặp trong `analysis_result.json` có thể có `expert_duration_ms`,
`worker_duration_ms`, `worker_extra_ms` (công nhân trừ mẫu), hai nhãn và hai
đường dẫn ảnh. MUDA là **nghi vấn để con người xem lại**, chưa phải lỗi hay thời
gian lãng phí được xác nhận. File `analysis_result.json` có nhiều trường phụ
theo mẫu và tình huống; không dùng nó làm input trực tiếp cho firmware.

**Nhánh DEMO cũ:** thay `real_sensors.jsonl`/`.meta.json` bằng
`sensors.jsonl`/`sensors.meta.json` với nguồn
`simulated_from_camera_observations`. Dữ liệu này không phải số đo SmartWrist;
không trộn hay đổi tên để giả làm `measured_hardware`.

## 6. AI → backend → frontend

AI tạo `backend_payload_measured.json` hoặc `backend_payload_demo.json`, rồi
`POST /api/v1/sessions/ingest`. Payload này **khác JSON MQTT**:

```json
{
  "session_id": "MEASURED_<ten_phien>",
  "worker_type": "TRAINEE",
  "key_frames": ["segment_0001_right_GRAB_frame_000010.png"],
  "action_phases": [{"phase": "RIGHT_GRAB", "start_time": 1.0, "end_time": 1.5, "peak_force_N": null}],
  "dtw_metrics": {"similarity_score": 0.0, "muda_detected_seconds": 0.0},
  "robot_trajectory_points": []
}
```

Ví dụ trên chỉ cho thấy **kiểu trường**, không phải kết quả đo hoặc so sánh
thật. `start_time`/`end_time` dùng **giây tương đối trong phiên**; các phase
không chồng nhau. Với phiên đo thật chưa hiệu chuẩn lực Newton,
`peak_force_N` là `null` và `robot_trajectory_points` là `[]`. Điểm
`similarity_score` và số giây MUDA do bridge tính cho mục đích hiển thị demo,
không phải chỉ số chất lượng đã hiệu chuẩn. File `.meta.json` bên cạnh payload
ghi nguồn, hash, quy tắc chuyển đổi và giới hạn. Backend nhận thêm
`analysis_result.json`, ảnh, video và gói nguồn qua **các endpoint riêng**;
frontend chỉ đọc kết quả đã lưu từ backend. Xem
[SessionInput](../../backend/schemas/session.py) và
[backend_bridge.py](../integration/backend_bridge.py).

Khi đang quay, frontend đọc `/api/v1/capture/{job_id}` để lấy `stage`,
`message`, `capture_mode`, rồi lấy `/preview` và `/frame` để hiển thị ảnh,
nhãn tay phải và `wrist_status` (`receiving`/`missing`). Đây là **format
backend → frontend**, không phải phần cứng gửi trực tiếp vào trình duyệt.

## 7. Tình trạng đã xác nhận và bảng đối chiếu với nhóm phần cứng

Trong các phiên phần cứng đã kiểm tra đến **05/10/2026**, một phiên cũ đã lưu
678 JPEG camera nhưng **0 mẫu SmartWrist**; các phiên mới hơn chưa lưu được
JPEG hoặc mẫu vòng tay. Vì thế **chưa có một JSON SmartWrist thật để xác nhận
firmware hiện phát đúng format ở mục 2**. Camera ở địa chỉ `.111` từng trả
`NTP not synchronized`; không được coi đó là một khung hình hợp lệ. Các con số
này là trạng thái quan sát tại thời điểm viết, không phải cam kết lâu dài.

Nhóm phần cứng cần gửi **nguyên văn một tin nhắn MQTT thật** và xác nhận:

| Câu hỏi đối chiếu | Code AI hiện chờ |
| --- | --- |
| Topic, broker và cổng? | `wearable/user01/wrist/data` → `.109:1883` |
| Tên trường và mảng? | `t_ms`, `seq`, `acc[3]`, `gyro[3]`, `force[4]` |
| `t_ms` có phải epoch mili giây sau khi NTP hợp lệ? | Có |
| Bốn phần tử `force` nối với vị trí/chân nào? | Chưa biết; phải cung cấp ánh xạ |
| Đơn vị `acc` và `gyro` sau chuyển đổi trong firmware? | Chưa xác minh |
| Camera hiện có IP và NTP hợp lệ? | Cần trả MJPEG + `X-Timestamp-Ms` + `X-Frame-Seq` |

Nếu format thực tế khác bảng trên, **ghi lại format thực rồi thống nhất sửa
adapter AI hoặc firmware**; không đoán hoặc đổi ADC thành Newton chỉ để qua
kiểm tra. Mọi ví dụ trong tài liệu này được rút từ code hiện có, không chứng
minh phần cứng đã gửi được dữ liệu.
