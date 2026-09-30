# SmartWear AI — camera và xử lý hai tay

## Chạy một lần

```powershell
cd C:\Task\smartwear-ai
python -B .\ai\camera_test.py
```

Camera hiện hai dòng riêng: LEFT (tay trái) và RIGHT (tay phải).
Một tay có thể GRAB trong khi tay kia OPEN hoặc REACH. Nhấn Q để dừng.
Chương trình tự chạy: chuẩn hóa → cảm biến giả → multimodal → chia đoạn từng tay
→ trích ảnh tiêu biểu → chọn mẫu demo gần nhất → so sánh.

Ngay khi camera mở, chương trình tạo một thư mục phiên và ghi cả ba file gốc
`camera.jsonl`, `camera.avi`, `camera.video.json` trực tiếp trong thư mục đó.
Video chứa hình đã lật gương
giống hình MediaPipe phân tích, không có chữ hoặc điểm vẽ lên. Mỗi dòng JSONL
có `video_frame_index`: số thứ tự đúng của hình trong video, bắt đầu từ 0.

Mỗi lần quay và xử lý dùng chung một thư mục riêng:
```text
C:\Task\smartwear-ai\ai\generated_data\sessions\camera_data_<ngày giờ>_<mã riêng>\
    camera.jsonl             ← bàn tay, nhãn, timestamp và video_frame_index
    camera.avi               ← video của chính phiên này
    camera.video.json        ← số khung và SHA-256 để đối chiếu hai file gốc
    camera.normalized.jsonl
    sensors.jsonl
    sensors.meta.json
    multimodal.jsonl
    action_segments.json
    keyframes.json          ← danh sách ảnh và lý do bỏ qua từng đoạn
    keyframes/              ← các ảnh PNG thật của các đoạn hợp lệ
    session_role.json       ← phiên công nhân khi dùng các mẫu demo
    analysis_result.json    ← so sánh với mẫu demo gần nhất
```

## Thử so sánh bằng ba video mẫu có sẵn

Chỉ cần chạy `python -B .\ai\camera_test.py`, quay thao tác của bạn và nhấn Q.
Chương trình tự xử lý phiên của bạn như một phiên worker, chọn đoạn mẫu demo gần
nhất trong `ai/generated_data/reference_samples`, rồi tạo `analysis_result.json`
trong thư mục phiên của bạn. Không cần gõ vai trò hay chép đường dẫn mẫu.

Ba đoạn mẫu được **cắt từ một video camera đã ghi trước đó**, mỗi đoạn khoảng
2 giây. Chúng là bài tập để thử chức năng, chưa được chuyên gia nhà máy xác nhận:

- `01_two_hands_reach_grab`: hai tay mở/đưa tới rồi nắm; cuối đoạn tay trái mở.
- `02_right_hand_grab_hold`: hai tay nắm; tay trái rời khung, tay phải tiếp tục giữ.
- `03_left_hand_grab_release`: tay trái nắm, thả rồi mở; tay phải không thấy rõ.

Mỗi mẫu có `camera.avi` để xem, `reference_sample.json` ghi mô tả và nguồn gốc,
cùng các file xử lý như một phiên thường. `session_role.json` ghi đây là mẫu demo.
Phần chọn mẫu dùng DTW để tìm đoạn gần nhất trong **ba mẫu có sẵn**, không tự tạo
một thao tác chuẩn mới.

File kết quả so sánh hai tay riêng biệt bằng DTW trên các đoạn hành động nhìn thấy từ camera;
`alignment` nêu hai đoạn được ghép, chênh lệch thời gian và đường dẫn ảnh tiêu biểu
nếu video có ảnh. `review_candidates` chỉ là các đoạn cần xem lại video, chưa phải
kết luận thao tác sai hoặc Muda. Chỉ số `normalized_dtw_cost` càng thấp thì chuỗi
hành động nhìn thấy càng giống; đây không phải điểm chất lượng đã hiệu chuẩn.

`analysis_result.json` cũng có `muda_review`: các **đoạn nghi vấn để con người
xem lại**, không phải kết luận Muda. `longer_visible_action` chỉ xuất hiện khi
một đoạn cùng nhãn được ghép một-một với mẫu, dài hơn ít nhất 500 ms và 1,5 lần.
`inserted_visible_action` là đoạn khác nhãn, dài ít nhất 300 ms và nằm giữa hai
đoạn của worker cùng khớp một bước mẫu. Mỗi mục có tay, thời điểm, nhãn và ảnh
để mở lại video. Đoạn khác nhãn đơn lẻ, mất tay hoặc ghép DTW nhiều-một không
được tự động coi là lãng phí. Mẫu demo chưa phải quy trình chuẩn, nên cần xem
video trước khi đưa ra nhận định.

Phần mở rộng tìm `extra_visible_action` khi có một đoạn hành động nhìn thấy
chen giữa hai nhãn khớp mẫu; `repeated_visible_action` khi chuỗi từ hai hành
động trở lên được thực hiện lại; và `missing_visible_action` khi một bước mẫu
ở giữa hai bước khớp không xuất hiện trong chuỗi camera của worker. Mỗi đoạn
thêm phải dài ít nhất 300 ms. Trường hợp bỏ sót không có một khung worker thật
cho hành động vắng mặt: `worker_time_hint_ms` là mốc gần vị trí đó,
`expert_image_path` là ảnh bước mẫu, còn `start_ms`/`end_ms` là null. Nếu camera
mất tay/không chắc ở mốc này, chương trình không kết luận bỏ sót. Các nhãn bị
thay thế mơ hồ hoặc thiếu ở đầu/cuối bản quay cũng không được tự động gọi là
bỏ sót. `review_candidates` cũ vẫn được giữ nguyên.

Tay không thấy rõ (`NO_HAND`, `OTHER`, `ambiguous`) được ghi trong `*_omitted`,
không chấm như hành động đúng. Nếu không có hành động nhìn thấy để so sánh,
chương trình báo thiếu dữ liệu.

`analysis_result.json` phiên bản v2 có thêm `sensor_comparison`. Với mỗi cặp đoạn
đã ghép, file ghi trung bình và đỉnh của `force_emg_raw`, torque, cùng mức chuyển
động IMU cổ tay và đầu. `worker_minus_expert` là số của phiên worker trừ mẫu
khi **cùng nhãn hành động**. Nếu hai nhãn khác nhau, vẫn hiện số của hai bên
để xem nhưng không lấy hiệu.
Chương trình lấy dữ liệu theo thứ tự: `real_sensors.jsonl` có metadata hợp lệ,
rồi `sensors.jsonl` mô phỏng đã được lưu, cuối cùng sinh số mô phỏng trong bộ nhớ
nếu file sensor không còn. Nguồn của **cả hai phiên** được ghi trong kết quả.
Nếu một bên đo thật còn bên kia mô phỏng, hai bộ số chỉ được đặt cạnh nhau,
`worker_minus_expert` là `null` vì chúng không cùng thang đo. Hai bộ đo thật chỉ
được trừ khi cùng đơn vị và `calibration_id`. Hai bộ số mô phỏng vẫn có chênh
lệch để xem demo, nhưng không đại diện lực người thật tạo ra.

Để bộ thu phần cứng sau này được ưu tiên, lưu `real_sensors.jsonl` trong thư mục
phiên với cùng schema `smartwear.sensors.v2` và timestamp khớp **từng khung camera**.
File `real_sensors.meta.json` cần `source: measured_hardware`,
`schema_version: smartwear.sensors_meta.v2`, SHA-256 của camera và sensor,
`sample_count`, `first_timestamp_ms`, `last_timestamp_ms`, `calibration_id` và
`units` gồm `force`, `torque`, `angle`, `acceleration`, `angular_speed`. Chưa có adapter
phần cứng hoặc đồng bộ đồng hồ thiết bị tự động. File thật sai nguồn/hash/thời
gian sẽ báo lỗi, không âm thầm thay bằng số giả. `force_emg_raw` của bộ mô phỏng
không phải Newton; đơn vị thật chỉ lấy từ metadata thiết bị.

Mẫu gần nhất vẫn được chọn bằng **hành động camera và thời gian**; số cảm biến
được báo cáo sau đó, không làm thay đổi mẫu được chọn.
Nếu sau này có video thao tác chuẩn thật của chuyên gia, vẫn có thể quay mẫu đó
bằng `python -B .\ai\camera_test.py --role expert` và chọn thủ công khi quay worker
bằng `--role worker --expert-session <đường dẫn phiên chuyên gia>`.
Các phiên cũ chưa có `session_role.json` vẫn có thể so sánh khi chỉ rõ hai
đường dẫn bằng lệnh sau:

```powershell
python -B .\ai\analysis\compare_sessions.py --expert-session "<duong_dan_phien_mau>" --worker-session "<duong_dan_phien_cong_nhan>"
```

File kết quả không ghi đè. Muốn so sánh lại, dùng một tên file `.json` mới trong
chính thư mục phiên worker với tùy chọn `--output`.

Không ghi đè dữ liệu. Nếu lỗi, dừng các bước sau và giữ bản camera để thử lại.
Đóng cưỡng bức chương trình không tự chạy bước xử lý. Chạy lại một bản camera
cũ bằng `python -B .\ai\process_recording.py --input <đường dẫn camera.jsonl>`
sẽ tạo phiên xử lý mới; file gốc và phiên trước vẫn được giữ nguyên.

## Vai trò các file Python

- camera_test.py: ghi hình bàn tay, vẽ điểm, hiện hai nhãn; Q kích hoạt xử lý.
- hand_observation.py: nhận diện riêng cho trái/phải, quản lý lịch sử mỗi tay.
- normalize_camera.py: chuẩn hóa bản ghi mới hoặc chuyển bản camera cũ sang v2.
- sensors/simulate_sensors.py: tạo số giả độc lập cho mỗi tay.
- build_multimodal.py: kiểm tra nguồn/thời điểm và ghép camera với số giả.
- segment_actions.py: gom nhãn liên tiếp riêng cho từng tay.
- video_recording.py: ghi video, đánh số khung và lập metadata nguồn.
- extract_keyframes.py: dùng video và thời điểm trong đoạn để xuất ảnh PNG.
- process_recording.py: gọi năm bước tự động.

## Ảnh tiêu biểu

Chương trình chọn khung được quan sát gần **giữa thời gian** của từng đoạn;
không chọn theo số thứ tự khung và không giả định camera luôn đúng 30 FPS.
Nếu hai khung cách đều giữa đoạn, chọn khung trước. Ảnh là toàn khung camera,
không cắt riêng bàn tay. File ảnh ghi rõ `left` hoặc `right` trong tên; hai tay
có thể tạo hai ảnh khác nhau ở cùng một thời điểm.

`keyframes.json` có một mục cho **mọi đoạn** trong `action_segments.json`,
liên kết bằng `segment_id`, chứa `hand`, `label`, `timestamp_ms`, `frame_id`,
`image_path` và `status`. Đoạn `NO_HAND`, tay không xác định hoặc nhãn `OTHER`
được ghi `skipped` với lý do; không tạo ảnh giả. Nếu bản ghi cũ không có video,
toàn bộ mục ghi `no_recorded_video`, không báo đã trích ảnh thành công.

File `.video.json` ghi SHA-256 của JSONL camera và video, số khung, kích thước,
codec MJPG/AVI. Trước khi trích, chương trình kiểm tra metadata, chuỗi thời gian,
nhãn và số lượng khung giải mã. Nếu video thiếu hoặc bị đổi, bước này báo lỗi;
file camera gốc vẫn còn. Tốc độ phát video là quy ước mã hóa 30 FPS; thời gian
thật lấy từ `timestamp` trong JSONL. Đây là điểm cần lưu ý khi xem lại video.

Video và ảnh chứa hình camera thật. Nếu quay người khác ở nhà máy, cần xử lý
quyền riêng tư trước khi chia sẻ file.

## Cách xác định tay

Dùng nhãn Left/Right của MediaPipe, không dùng vị trí trong danh sách hoặc
bên trái/bên phải màn hình. Thứ tự phát hiện đảo vẫn giữ lịch sử theo tay.
Chương trình dành cho **hai tay của một người**, không nhận dạng danh tính nhiều người.

Mỗi tay có tracking_status:
- detected: có đúng một tay hợp lệ mang nhãn bên này.
- missing: không thấy tay đó, label = NO_HAND, hand_state = NONE.
- ambiguous: không phân biệt chắc tay (nhãn trùng, unknown, điểm lỗi...);
  label = OTHER, hand_state = OTHER; màn hình hiện UNCERTAIN.

Nếu có nhãn unknown hoặc hai tay cùng được gán Left/Right, cả hai nhánh chuyển
ambiguous để không chọn bừa. Điểm gốc vẫn được lưu. Tay mất/không xác định sẽ
đặt lại lịch sử; tay còn lại không bị ảnh hưởng khi vẫn xác định được.
Khoảng cách khung >500 ms cũng đặt lại lịch sử nhận diện.

Trái/phải phụ thuộc MediaPipe. Che khuất, giao nhau hoặc góc khó vẫn có thể làm
mô hình gán sai bên; chương trình chưa bảo đảm theo dõi danh tính khi nhãn bị
đảo sai. Các nhãn hành động là quy tắc hình bàn tay, không chứng minh công nhân
đã cầm vật hay lắp ráp thật.

## Schema v2 — thay đổi so với v1

Raw: smartwear.camera_raw.v2. Chuẩn hóa: smartwear.camera.v2.
Giữ hands là danh sách tọa độ gốc; thay action_estimate chung bằng:
```json
{
  "hand_actions": {
    "left": {
      "label": "GRAB", "hand_state": "CLOSED",
      "source": "camera_landmarks", "tracking_status": "detected", "hand_index": 1
    },
    "right": {
      "label": "OPEN", "hand_state": "OPEN",
      "source": "camera_landmarks", "tracking_status": "detected", "hand_index": 0
    }
  }
}
```

hand_index chỉ liên kết với hands trong cùng khung; left/right mới là nhánh
xuyên suốt phiên. action_origin cho biết recorded_per_hand (đã ghi lúc quay)
hay recomputed_from_legacy_landmarks (tính lại từ bản cũ).

Sensor: smartwear.sensors.v2. Một imu_head chung, và:
```text
hand_sensors.left  → tracking_status, imu_wrist, force_emg_raw, torque
hand_sensors.right → tracking_status, imu_wrist, force_emg_raw, torque
```

Khi missing/ambiguous, các giá trị cảm biến của tay đó là null, không phải 0.
Các số được sinh có nguồn simulated_from_camera_observations; không phải đo thật.

Multimodal: smartwear.multimodal.v2, gồm timestamp_ms, frame_id, relative_time_s,
camera, hands, hand_actions, action_origin, imu_head, hand_sensors và provenance.
Chỉ ghép nếu cùng schema, cùng số dòng, timestamp tăng/khớp và SHA-256 đúng.
Metadata ghi nguồn camera, hash cảm biến, danh sách các trường giả và số nhãn
riêng cho mỗi tay. Không nội suy hoặc bù khung thiếu.

force_emg_raw không có đơn vị, không phải Newton hay sóng sEMG sinh lý.
IMU m/s² và rad/s, torque N·m và góc độ là quy ước mô phỏng.
Timestamp sensor được sao chép từ camera, chưa đồng bộ đồng hồ phần cứng độc lập.

## action_segments.json — hai dòng thời gian độc lập

Schema smartwear.action_segments.v2. Mỗi phần tử segments có:
- hand: left hoặc right; label; tracking_status.
- segment_id: mã đoạn trong toàn file.
- start_frame_id / end_frame_id: khung đầu/cuối, tính cả hai.
- frame_count: số khung trong đoạn.
- start_ms: thời điểm khung đầu.
- last_observed_ms: thời điểm khung cuối thực sự mang nhãn này.
- end_ms, duration_ms: mốc cuối dùng tính thời lượng và end_ms - start_ms.
- end_reason: label_change, data_gap, recording_end.
- end_is_observation_limit: true nếu hết dữ liệu/gián đoạn, chưa biết thao tác
  ngoài đời đã kết thúc chưa.

Mỗi khung thuộc đúng một đoạn **trên mỗi tay**. Đổi nhãn hoặc tracking_status
thì tách đoạn. Giữ NO_HAND/OTHER và các đoạn ngắn. Không dùng số giả để nhận diện.
Hai tay có thể có đoạn chồng thời gian; không cộng thời lượng hai tay để tính
thời gian làm việc của công nhân. segment_counts_by_hand thống kê từng bên.

Đổi nhãn bình thường: end_ms là mốc khung đầu của nhãn sau.
Gián đoạn >500 ms: tách đoạn, chốt tại khung trước gián đoạn và ghi data_gaps.
Đoạn cuối: chốt tại timestamp cuối, không tự cộng thời gian. Đoạn một khung ở
cuối có duration_ms = 0 vì không có thêm thời gian quan sát.
Có thể đổi ngưỡng khi chạy riêng segment_actions.py bằng --max-gap-ms.

## Bản ghi cũ

Các file v1 vẫn giữ nguyên. Chạy process_recording.py với raw camera cũ để tạo
phiên v2 mới; nhãn chung cũ không bị sao chép thành nhãn của cả hai tay.
Hành động trái/phải được tính lại từ landmarks và handedness gốc. Nếu bản cũ
không có đủ thông tin phân biệt bên, trạng thái là ambiguous.

Đọc/ghép sensor và chia đoạn v1 vẫn được hỗ trợ theo chế độ một tay cũ.
Không ghép lẫn v1/v2; không thể suy ra số cảm biến riêng của hai tay từ file sensor
v1. Hãy chạy lại từ bản camera gốc để tạo đầy đủ v2.

```powershell
python -B .\ai\process_recording.py --input .\ai\camera_data_20260929_112902_905889.jsonl
```

## Xem kết quả

Thay đường dẫn phiên dưới đây bằng đường dẫn PowerShell thông báo:
```powershell
$session = 'C:\Task\smartwear-ai\ai\generated_data\sessions\<tên phiên>'
Get-Content "$session\multimodal.jsonl" |
  ForEach-Object { $_ | ConvertFrom-Json } |
  Select-Object -First 20 timestamp_ms,
    @{Name='TayTrai'; Expression={$_.hand_actions.left.label}},
    @{Name='TayPhai'; Expression={$_.hand_actions.right.label}}

$result = Get-Content "$session\action_segments.json" -Raw | ConvertFrom-Json
$result.segments | Format-Table hand,label,tracking_status,start_ms,end_ms,duration_ms
```

## Kiểm thử

```powershell
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s .\ai\preprocessing -p "test_*.py" -v
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s .\ai\sensors -p "test_*.py" -v
```

Kiểm thử dùng điểm bàn tay mẫu, cả hai động tác đối lập, đảo thứ tự, đổi vị trí,
mất/xuất hiện lại tay, nhãn mơ hồ, chuyển đổi dữ liệu cũ và pipeline thật qua các
file. Chưa thay thế kiểm tra độ chính xác ngoài đời với webcam.
Các bước xử lý dùng thư viện chuẩn Python; chỉ camera cần OpenCV/MediaPipe.
