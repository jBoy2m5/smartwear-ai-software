# Lộ trình dữ liệu đầu ra SmartWear: học viên và học máy

Cập nhật: 07/10/2026
Phạm vi: dữ liệu từ thiết bị SmartCap/SmartWrist qua AI, backend và dashboard; đầu ra cho đào tạo thao tác con người và cho huấn luyện/đánh giá robot.

Tài liệu ngắn để trình bày tính khả thi trước ban giám khảo: [Y_TUONG_DU_LIEU_CONG_NHAN_HUAN_LUYEN_HUMANOID.md](Y_TUONG_DU_LIEU_CONG_NHAN_HUAN_LUYEN_HUMANOID.md).

Triển khai và bằng chứng mới: [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md). Phần mềm đã bổ sung workflow expert/reference, review SOP và exporter observation HDF5/MCAP; các mục nghiệm thu vật lý/robot trong tài liệu này vẫn cần bằng chứng riêng.

Kế hoạch thực nghiệm trong 3 ngày, vật dụng cần chuẩn bị và hai công đoạn đại diện LOG/sản xuất: [DEMO_TWO_WORKFLOWS.md](DEMO_TWO_WORKFLOWS.md).

## 1. Mục tiêu và nguyên tắc thiết kế

Một phiên thao tác đã xử lý cần có thể tạo ra **hai sản phẩm dữ liệu** từ cùng một bản ghi nguồn:

1. **Learner Package**: nội dung dễ xem, dễ so sánh và có hướng dẫn để học viên biết làm gì, sai ở đâu, cần sửa ra sao.
2. **Machine Dataset Episode**: chuỗi observation–action theo thời gian, có schema, đơn vị, timestamp, calibration, chất lượng và nguồn gốc đủ để tái lập thí nghiệm hoặc huấn luyện.

Hai gói có mục đích khác nhau. Báo cáo đẹp không làm dữ liệu đạt chuẩn robot; file NPZ/MCAP không tự trở thành tài liệu đào tạo tốt. Cả hai phải trỏ về cùng `session_id`, checksum bản ghi nguồn và phiên bản pipeline để kết quả so sánh được.

Nguyên tắc bắt buộc:

- Không thay giá trị thiếu bằng DEMO, 0 giả, nội suy không gắn nhãn hoặc giá trị suy đoán. Giá trị thiếu phải có `valid=false`/`null` và lý do.
- Không đổi ADC thành Newton, landmark ảnh thành mm, hoặc vị trí cổ tay thành lệnh robot nếu chưa có hiệu chuẩn và phép biến đổi được kiểm chứng.
- Tách **dữ liệu đo**, **dữ liệu suy luận**, **nhãn người gán**, **dữ liệu mô phỏng**. Mỗi điểm phải truy ngược được về loại và phiên bản nguồn.
- Mẫu `expert` là mẫu tham chiếu và nguồn nội dung do chuyên gia xác nhận; việc lưu mẫu expert không đồng nghĩa tự huấn luyện hay cải thiện trọng số mô hình.
- Mỗi đầu ra có trạng thái sẵn sàng riêng. Một phiên có thể dùng cho học viên nhưng chưa dùng được cho robot.
- Mục tiêu định lượng trong tài liệu này là **tiêu chí nghiệm thu đề xuất theo yêu cầu dự án**, không phải kết quả đã đạt của thiết bị hiện tại.

## 2. Hiện trạng repo và khoảng cách tới yêu cầu

Đối chiếu README, Layer 1–3 runbook/contract/validation và backend README hiện có:

| Hạng mục | Đã có trong dự án | Khoảng cách cần đóng |
|---|---|---|
| Thu phiên | `record_hardware.py` tạo video, dữ liệu camera/wrist và xử lý/publish; session có role và nguồn. | Cần manifest schema/version thống nhất cho mọi nguồn, artifact và chất lượng; không chỉ dựa vào tên file/DB summary. |
| Cảm biến cổ tay | MQTT, timestamp, sequence và 4 ADC; một số lượt đạt xấp xỉ 50 Hz. | Có phiên FSR 4 chưa phản hồi; IMU SmartWrist chưa có dữ liệu; rate phải được đo cho từng phiên và từng kênh. Không tuyên bố đủ cảm biến chỉ vì firmware hoạt động. |
| Đồng bộ | Ghép gần nhất theo timestamp, cấu hình mặc định ±10 ms; dữ liệu thiếu có thể giữ null. | Cần báo cáo phân bố sai lệch, tỷ lệ frame được match, clock offset và uncertainty. Không thể đảm bảo mọi ảnh 30 FPS có mẫu cảm biến trong ±10 ms chỉ bằng nearest-neighbor. |
| Video | Camera OV2640, hiện firmware dùng `FRAMESIZE_QVGA` 320×240; ghi AVI theo tài liệu dự án. Có capture JPEG/preview và keyframes. | QVGA thấp hơn WVGA/720p; một số lượt đo khoảng 17–18 FPS, dưới 30 FPS. Nâng độ phân giải/fps phải xác minh trên phần cứng thực, không upscale rồi coi là đạt. Chưa có clip MP4/H.264 phân đoạn và overlay hoàn chỉnh. |
| Hai tay/AI | MediaPipe phát hiện landmark và handedness, có pipeline nhiều tay; action/phase là heuristic. | Phải lưu confidence, frame lỗi/mất track, camera mirror config và đánh giá nhãn trái/phải bằng bộ test có ground truth. Không ghi nhãn chắc chắn khi confidence thấp. |
| So sánh | Có so sánh worker/expert theo phase/DTW và một số sensor metrics; MUDA là candidate để người xem lại. | Dashboard còn đường mặc định DEMO ở một số luồng; cần chọn expert cụ thể, phiên bản mẫu và quy trình duyệt. Cần báo đơn vị/uncertainty và không gọi heuristic MUDA là lỗi đã xác nhận. |
| SOP | Backend xuất SOP HTML/PDF tổng hợp. | Cần SOP theo từng bước, mốc hình/video, ngôn ngữ tự nhiên, lý do/mẹo/lỗi do chuyên gia ghi, review và phiên bản. |
| Lực | Dữ liệu thô 4 kênh ADC được giữ lại. | FSR chưa được hiệu chuẩn độc lập thành Newton; `peak_force_N` phải null khi chưa đo/calibrate. Chỉ khi hiệu chuẩn hợp lệ mới hiển thị gauge Newton và phần trăm sai lệch. |
| Robot trajectory/action | Có contract/export JSON và ROS2 bag có cấu trúc. | README xác nhận trajectory đo có thể rỗng; ROS export hiện ánh xạ dữ liệu summary và force placeholder. Không được dùng export đó làm action thật cho robot/huấn luyện cho tới khi nguồn pose/action vật lý được xác minh. |
| Lưu trữ/publish | DB, keyframes, video/source ZIP và API publish. | Cần versioned episode bundle, checksum đầy đủ, schema/calibration, quality gate, quyền riêng tư và tách learner-ready/robot-ready. |

**Kết luận hiện trạng:** dữ liệu đang hữu ích cho kiểm thử pipeline, quan sát thao tác và một phần so sánh học viên. Chưa đủ bằng chứng để coi là bộ dữ liệu imitation-learning/robot-ready theo các ngưỡng đã nêu. Những yêu cầu như <2 mm, 0.1–20 N, clock drift <2 ms, packet loss <0.1% phải được đo và lưu bằng chứng trên từng phiên/thiết bị trước khi công bố đạt.

## 3. Kiến trúc đầu-cuối đề xuất

```text
SmartCap / SmartWrist
        │  nguồn thật + timestamp + sequence + trạng thái thiết bị
        ▼
L0 Capture (immutable raw)
        │  camera bytes/video, wrist MQTT JSONL, device/config metadata
        ▼
L1 Normalize + align
        │  timestamp chuẩn, đơn vị, schema, validity mask, alignment report
        ▼
L2 Perception + annotation
        │  hai tay, landmarks, phase/keyframes, confidence, expert notes/review
        ├──────────────────────────────┐
        ▼                              ▼
Learner Package                  Machine Episode
SOP + clips + comparison         observation/action + timestamps + calibration
        │                              │
        └──────────────┬───────────────┘
                       ▼
L3 Quality gate, publish, manifest, checksums, DB index, dashboard
```

### L0 — bản ghi nguồn bất biến

- Lưu nguyên bản ghi camera và SmartWrist; không ghi đè sau xử lý. Mỗi file có SHA-256, byte size, MIME/codec, thời gian bắt đầu/kết thúc, thiết bị và phiên bản firmware.
- Lưu song song event `capture_started`, `capture_stopped`, dropped-frame/error, sequence reset, reconnect, người thực hiện, role, task/procedure ID và cấu hình capture.
- Ghi rõ camera mirror/rotation, độ phân giải thực, fps đo được, cách đồng hồ được tạo; firmware version/commit, serial đã ẩn/ID pseudonymous, calibration IDs.
- `expert` cần metadata: người duyệt, chuyên môn/ủy quyền, ngày duyệt, task/version, trạng thái bản ghi (draft/approved/retired), cùng ghi chú của chuyên gia. Tách `role` của người thao tác với `review_status` của mẫu.

### L1 — chuẩn hóa, đồng bộ và provenance

- Mỗi mẫu có ít nhất `session_id`, `episode_id`, `stream`, `seq`, `t_device_ns` nếu có, `t_host_ns`, `clock_domain`, `receive_time_ns`, `valid`, `quality_flags`, `source_kind` (`measured`, `inferred`, `human_label`, `simulated`) và `schema_version`.
- Chọn một monotonic timeline của máy ghi làm thời gian episode; giữ timestamp thiết bị và wall-clock gốc riêng để audit. Không dùng giờ máy tường thay cho monotonic duration vì đồng hồ có thể chỉnh/NTP step.
- Lưu alignment report: số frame/sensor samples, histogram/max/p50/p95 timestamp delta, tỷ lệ match, duplicate, missing, reorder, sequence gap, clock offset/uncertainty, estimator và ngưỡng. Giữ cả raw timestamp; không chỉ lưu bảng đã join.
- Ảnh 30 fps cách nhau khoảng 33,3 ms trong khi FSR 50 Hz cách khoảng 20 ms. Với ngưỡng match 10 ms, phải đo tỷ lệ match thực tế. Không ép match bằng cách nội suy mà bỏ mất provenance; nếu resample, lưu dữ liệu gốc và cột `interpolated=true`/phương pháp.
- NTP không tự chứng minh đạt sai số <2 ms. Lưu báo cáo offset/dispersion hoặc phép đo tham chiếu của clock; nếu không có phép đo, trạng thái phải là `unknown`, không phải `pass`.

### L2 — perception, nhãn và chuyên gia

- Lưu kết quả detection cho mỗi frame, kể cả `no_hand`, `ambiguous`, `occluded`, confidence và track ID. Cấu hình mirror phải đi cùng episode để kiểm chứng LEFT/RIGHT. Gắn nhãn anatomically left/right; không suy từ vị trí trái/phải trên màn hình.
- Tách action label heuristic/model/human-reviewed. Với mỗi pha có start/end timestamp, tên bước, confidence, nguồn gán nhãn, người duyệt và phiên bản model/rule.
- Thêm form ghi chú expert theo bước: `instruction`, `why`, `tips`, `common_errors`, `safety`, `acceptable_variation`, `force/trajectory_target` (chỉ khi có calibration), liên kết với keyframe và time range.
- Ghi mẫu expert bằng `--role expert`; người học tham chiếu bằng `--role worker --expert-session <thư_mục_phiên_chuyên_gia>`. Backend/dashboard cần cho chọn expert theo task/procedure/version; lưu `reference_session_id` trong kết quả. Không tự chọn DEMO mà không hiển thị nguồn mẫu.
- Mọi MUDA/action candidate là gợi ý cho tới khi người có chuyên môn xác nhận. Lưu `candidate`, `accepted/rejected`, reviewer, rationale và version; không âm thầm biến heuristic thành nhãn ground-truth.

## 4. Gói dữ liệu cho NGƯỜI HỌC

Một learner package được tạo cho một phiên worker đã chọn một expert đã duyệt. Gói này nên có đường dẫn/manifest ổn định, xem được trên dashboard và tải được độc lập.

### 4.1 Digital SOP

Định dạng chính: HTML/Web Dashboard tương tác; tùy chọn PDF in được và Markdown/JSON để sửa đổi/tích hợp. Mỗi bước SOP có:

```json
{
  "step_id": "tighten_02",
  "order": 2,
  "title": "Siết vít đến điểm dừng",
  "instruction": "Giữ chi tiết sát mặt gá, siết đều đến điểm dừng.",
  "why": "Giảm lệch ren và tránh làm xước bề mặt.",
  "tips": ["Giữ trục dụng cụ vuông góc"],
  "common_errors": ["Tăng lực đột ngột ở cuối hành trình"],
  "time_range_s": [4.2, 7.8],
  "keyframes": ["keyframes/tighten_start.jpg", "keyframes/tighten_end.jpg"],
  "clip": "clips/tighten_02.mp4",
  "expert_session_id": "MEASURED_expert_...",
  "review_status": "approved"
}
```

- Tự động đề xuất bước từ action segment/keyframe; expert chỉnh nội dung, thứ tự, time range và approve. Tự động tóm tắt ngôn ngữ chỉ là draft, không tự tạo “lý do/mẹo” như sự thật.
- Cho xem expert và worker đồng bộ theo step; hiển thị thời gian worker/expert, difference (giây), frame/keyframe và note. Có khả năng mở video nguồn quanh điểm sai lệch.
- Nêu rõ nguồn video, độ phân giải/fps và khi dữ liệu bị thiếu/mờ. Tối thiểu 720p hoặc WVGA@30 là yêu cầu acquisition, không thể đạt bằng kéo giãn hình nhỏ.

### 4.2 Annotated micro-clips

- Xuất clip MP4/H.264, mỗi clip theo một công đoạn, cắt theo timestamp expert/worker hoặc cửa sổ so sánh; kèm JSON sidecar ghi time range, nguồn, fps, resolution, overlay version và checksum.
- Overlay quỹ đạo cổ tay chỉ vẽ trên tọa độ ảnh nếu chưa hiệu chuẩn; đặt nhãn “quỹ đạo 2D trong ảnh”, không gọi là mm/robot trajectory. Có thể tô heatmap dừng/đi lại khi đủ track liên tục.
- Widget FSR dùng màu traffic-light chỉ khi các kênh có calibration và ngưỡng lực an toàn của task được chuyên gia duyệt. Khi chỉ có ADC, ghi `ADC raw (chưa hiệu chuẩn)`, dùng thang tương đối riêng từng kênh nếu phù hợp; không gắn đơn vị N hoặc kết luận đạt lực.
- Hiển thị `data missing`, `low confidence`, `sensor not calibrated`, `reference is DEMO` rõ ràng. Màu có nhãn/biểu tượng/text để không phụ thuộc riêng vào khả năng phân biệt màu.
- Mục tiêu video: tối thiểu 1280×720 hoặc WVGA 800×480, 30 FPS. Với vi thao tác, nghiệm thu thực tế dựa trên ảnh rõ ở vùng làm việc, không chỉ metadata codec.

### 4.3 Motion Gap Report / dashboard

- So sánh worker với một expert reference cụ thể. Chuẩn hóa pha/đường thời gian và dùng DTW cho hình dạng chuỗi; lưu thuật toán, feature set, normalization, cost/path và phiên bản. Không để một điểm similarity che mất tín hiệu không tương đương.
- Tối thiểu hiển thị: thời lượng từng pha và chênh lệch giây; thêm/thiếu bước; thời gian dừng; đường 2D hoặc 3D đã hiệu chuẩn; sai khác tốc độ góc rad/s chỉ khi nguồn quaternion/rotation và đơn vị hợp lệ; force difference và phần trăm chỉ khi Newton calibrated.
- Công thức gợi ý:
  - `duration_delta_s = worker_duration_s - expert_duration_s`.
  - `relative_force_error_pct = 100 * (worker_force_N - expert_force_N) / expert_force_N`, chỉ tính khi reference force khác 0 và hai phép đo có calibration tương thích.
  - `angular_velocity_delta_rad_s = worker_omega_rad_s - expert_omega_rad_s`, chỉ so sánh cùng hệ tọa độ và cùng cách lọc.
  - DTW cost/score phải kèm định nghĩa và dải giá trị; không diễn giải score thành độ chính xác % nếu chưa kiểm chứng.
- Dùng xanh/vàng/đỏ theo ngưỡng từng task được xác nhận, không dùng ngưỡng chung tùy ý. Mỗi cảnh báo có evidence/time range, uncertainty và hành động đề xuất.
- Latency mục tiêu: dưới 15 phút từ khi kết thúc phiên đến khi SOP/clip/report sẵn sàng. Ghi `processing_started_at`, `processing_completed_at`, `artifact_ready_at` và kết quả; benchmark với phiên đại diện (video dài, nhiều keyframe, tải thấp/cao).

## 5. Gói dữ liệu cho MÁY HỌC / ROBOT

### 5.1 Tách Observation và Action thật rõ

Robot policy học ánh xạ observation `S_t` → action `A_t`. Hệ thống hiện có camera/landmark và cảm biến tay, nhưng chưa có đủ dữ liệu hành động robot đã hiệu chuẩn. Bước đầu có thể xuất observation dataset, nhưng **không gọi nó là imitation-learning action dataset** nếu `A_t` thiếu hoặc chỉ là số dựng từ landmark ảnh.

Observation tiềm năng:

- `observation.images.fpv`: ảnh RGB/JPEG/video theo frame và timestamp.
- `observation.hand.left/right.landmarks_2d`: tọa độ pixel chuẩn hóa, handedness, track ID, confidence; không mang đơn vị mét.
- `observation.hand.left/right.pose_3d`: chỉ khi có hiệu chuẩn metric; kèm hệ tọa độ và calibration ID.
- `observation.wrist.fsr_adc[4]`: ADC thô, map channel→GPIO/sensor, range/bit-depth và validity.
- `observation.wrist.force_N[4]`: chỉ sau calibration cho từng cảm biến; kèm uncertainty, calibration curve và version.
- `observation.wrist.imu`: `[ax, ay, az, gx, gy, gz]`, đơn vị `m/s^2` và `rad/s`, trục/hệ quy chiếu, sample timestamp và validity; null khi thiết bị không trả về.
- `observation.task`, `phase`, language instruction, expert annotations, segmentation boundaries.

Action cần xác định cùng nhóm robot/control trước khi thu dữ liệu:

- Với robot arm: `action.delta_pose=[dx,dy,dz,droll,dpitch,dyaw]` trong frame cụ thể, SI/rad; hoặc `action.joint_position`/`joint_velocity`/`joint_effort` theo tên joint và thứ tự; ghi `action_horizon`, control rate và interpolation semantics.
- Gripper: `action.gripper_position` (m/mm hoặc normalized có định nghĩa), `action.gripper_command` và/hoặc lực command riêng. Tách lệnh mong muốn khỏi lực được cảm biến đo.
- Với teleoperation người→robot: phải có hệ thống theo dõi/đầu vào control thực và phép biến đổi từ người sang robot. Video wrist 2D/landmark không tự tạo ra ground-truth `delta(x,y,z,roll,pitch,yaw)`.
- Ghi action source (`measured_robot_command`, `teleop_command`, `human_label`, `derived`) và không trộn các loại trong cùng feature mà không có cờ nguồn.

### 5.2 Cấu trúc episode portable

Mỗi episode cần tối thiểu:

```text
episode_<id>/
  episode_manifest.json       # schema, sources, units, calibration, labels, quality, hashes
  raw/                        # immutable source references or copied raw files
  video/fpv.mp4               # lossless/quality source as policy allows; preserve original
  arrays/episode.h5           # or episode.zarr/ or NPZ for compact small episodes
  labels/phases.json
  calibration/*.json
  reports/alignment.json
  checksums.sha256
```

Một record từng bước phải giữ `t_episode_ns`, `frame_index`/camera timestamp, `sensor_seq`, camera↔sensor `delta_t_ns`, từng feature `valid`, `source_kind`, `calibration_id` và action timestamp. Lưu raw clocks riêng; đồng bộ không đồng nghĩa giả định mẫu mọi sensor đúng bằng frame rate.

Manifest minh họa:

```json
{
  "schema": "smartwear.episode/1.0",
  "session_id": "MEASURED_hardware_...",
  "role": "worker",
  "task_id": "assembly.task.v1",
  "reference_session_id": "MEASURED_expert_...",
  "pipeline_version": "<git-commit-or-release>",
  "source_kind": "measured",
  "timebase": {"clock": "recorder_monotonic", "unit": "ns"},
  "video": {"codec": "h264", "width": 1280, "height": 720, "fps_measured": 30.0},
  "sensors": {"wrist_rate_hz_measured": 50.0, "fsr_unit": "adc_count", "imu_available": false},
  "calibration_ids": {"camera": null, "fsr": null, "hand_to_robot": null},
  "quality_state": {"learner_ready": false, "robot_ready": false, "reasons": []},
  "artifacts": [{"path": "video/fpv.mp4", "sha256": "<hex>"}]
}
```

Giá trị `null`/placeholder trong ví dụ phải được thay bằng giá trị thật lúc xuất; không được publish nguyên mẫu minh họa như một episode đạt chuẩn.

### 5.3 Chọn format

- **MCAP/ROS bag**: lưu message có timestamp/topic/schema để replay và tích hợp ROS; topic đề xuất `/smartwear/camera/frame` (hoặc image/video index), `/smartwear/wrist/fsr_raw`, `/smartwear/wrist/imu`, `/smartwear/hand/observations`, `/smartwear/robot/state`, `/smartwear/robot/action`, `/smartwear/annotations/phase`, `/smartwear/clock/status`. Dùng log time và publish/device time đúng ngữ nghĩa; đính kèm calibration/config, sequence và message definition. Chỉ phát topic robot state/action khi có dữ liệu thật. MCAP attachment/metadata phù hợp cho file hiệu chuẩn hoặc manifest.
- **HDF5**: thuận tiện cho một episode hoặc tập nội bộ gồm array đa chiều/chunk/compression. Nhóm `/observations/...`, `/actions/...`, `/timestamps/...`, `/validity/...`, `/metadata/...`; ảnh có thể ở video ngoài để seek/stream hiệu quả, manifest giữ đường dẫn và timestamp.
- **Zarr**: phù hợp array chunked và truy cập song song/cloud/object store khi dữ liệu tăng. Chốt version, codec, chunk layout và metadata convention để nhiều phiên bản reader đọc giống nhau.
- **NPZ**: phù hợp export nhỏ/offline, dễ mở bằng NumPy; không phù hợp làm kho chính cho video lớn hoặc streaming/chunked tập rất lớn. Kèm JSON sidecar vì NPZ đơn lẻ không đủ schema/provenance.
- **LeRobot/Parquet + MP4**: cân nhắc làm adapter xuất cho huấn luyện tương thích LeRobot; chuyển low-dimensional state/action thành bảng và image thành video, metadata episode/task/schema. Giữ SmartWear episode/manifest là canonical để không khóa source vào một framework.
- Có thể xuất nhiều adapter từ canonical episode. Tránh để mỗi format tự tạo clock/feature semantics khác nhau.

### 5.4 Tiêu chuẩn chất lượng robot

- **Đồng bộ**: target `|t_camera - t_sensor| ≤ 10 ms` cho cặp được match, đồng thời báo tỷ lệ match và p50/p95/max; wrist sensor target ≥50 Hz đo trên sample interval và báo gap/jitter. Với frame 30 FPS, không yêu cầu mọi frame có sensor sample gần hơn 10 ms nếu tỷ lệ/phase không cho phép; tiêu chí thực tế phải quy định `match_coverage` tối thiểu theo task.
- **Clock**: target offset/drift giữa các node <2 ms phải có log phép đo, nguồn thời gian và uncertainty. Ghi NTP status không đủ để chứng minh ngưỡng này.
- **Packet loss**: sequence gap / expected packets <0.1% trong cửa sổ phiên; phân biệt packet missing với duplicate/reorder/reconnect và mất cảm biến. Nếu nguồn không có sequence thì trạng thái loss là `not_measured`.
- **Sensor health**: cờ saturation (ADC min/max), flatline, out-of-range, rate irregular, invalid IMU, reset. Flatline cần ngưỡng theo sensor và khoảng thời gian; zero có thể là giá trị hợp lệ nên không kết luận lỗi từ zero đơn lẻ.
- **Lực 0.1–20 N**: hiệu chuẩn từng FSR theo lắp đặt thật (load cell/reference gauge, nhiều điểm nạp/xả, lặp lại, hysteresis/creep, nhiệt độ nếu ảnh hưởng). Lưu đường cong và residual/error trên toàn dải; kiểm chứng độ phân giải/độ chính xác đủ cho task. ADC thô vẫn giữ bên cạnh Newton.
- **Định vị <2 mm**: camera intrinsic/extrinsic và hệ coordinate được calibrate; dùng fiducial/depth/stereo hoặc phương pháp metric độc lập phù hợp. So với gauge/CMM/fixture ground-truth trên workspace và tư thế thao tác; báo MAE, RMSE, p95, bias, điều kiện đo. MediaPipe image landmarks không chứng minh ngưỡng mm.
- **Action validity**: robot command/state được ghi trực tiếp, có joint/frame/unit/control rate; action sequence phải căn đúng với observation. Nếu chỉ có thao tác người quay video, episode chỉ observation/label cho tới khi có action mapping được validate.
- **Split dataset**: chia train/validation/test theo worker, ngày/ca, task hoặc fixture phù hợp; không chia ngẫu nhiên từng frame của cùng episode sang nhiều split. Pin data/pipeline/calibration version để tái lập.

## 6. Quality gates và trạng thái publish

Dùng trạng thái độc lập thay vì một cờ `processed=true`:

| Trạng thái | Điều kiện tối thiểu | Sản phẩm cho phép |
|---|---|---|
| `RAW_CAPTURED` | Raw files đóng hợp lệ, manifest/sequence/checksum có; errors được ghi. | Xem kỹ thuật nội bộ, chưa phát hướng dẫn chuẩn. |
| `ALIGNED` | Schema hợp lệ; clock domain biết; alignment report + missing/duplicate/gap; nguồn thật/demo phân biệt. | Phân tích đồng bộ/preview, hiển thị cảnh báo chất lượng. |
| `ANNOTATED` | Hai tay/phase/keyframe/note có confidence/provenance; người duyệt khi cần. | Draft learner report, note draft phải đánh dấu. |
| `LEARNER_READY` | Expert reference được chọn/approve; SOP và clip có step/note/keyframe; tín hiệu chỉ được diễn giải đúng đơn vị; report hoàn tất và link artifact còn dùng được. | Dashboard/SOP cho học viên với trạng thái, giới hạn và phản hồi. |
| `CALIBRATED` | Các modality dùng để định lượng có calibration ID, validity window và sai số đạt tiêu chí task. | Hiển thị metric vật lý đã hiệu chuẩn. |
| `ROBOT_READY` | Observation/action schema hoàn chỉnh, action thật hoặc mapping đã validate, temporal/clock/loss/sensor/spatial gates đạt, manifest/checksum/split license/review đủ. | Xuất MCAP/HDF5/Zarr/adapter cho huấn luyện/đánh giá robot. |
| `REJECTED` / `REVIEW_REQUIRED` | Lỗi hoặc nghi vấn cần con người xử lý. | Không đưa vào tập chuẩn; vẫn giữ raw để audit. |

`LEARNER_READY` không yêu cầu mọi sensor có mặt nếu bài học là thị giác/quy trình, nhưng dashboard phải nói rõ sensor nào không dùng được. `ROBOT_READY` không thể đạt nếu action thiếu, lực/vị trí dùng làm target chưa hiệu chuẩn, hoặc thời gian không có bằng chứng.

## 7. Backend, database và dashboard cần bổ sung

### Backend/database

- Tạo canonical `episode_manifest.json` cho mỗi phiên và lưu DB metadata: `schema_version`, `pipeline_version`, `role`, `task_id`, `reference_session_id`, `expert_approval`, `calibration_ids`, `quality_state`, `artifact_hashes`, `processing_latency_ms`, `source_kind`.
- Thêm các thực thể/quan hệ cho `ExpertProcedure`, `ExpertStep`, `ExpertNote`, `CalibrationRecord`, `QualityReport`, `Artifact`; giữ `session_role.json` tương thích hoặc migration có kiểm soát. Mỗi reference cần task/version và status approved/retired.
- Tạo API chọn/liệt kê expert reference theo task, xem SOP/note, xác nhận note, xem readiness/reasons; API learner package và machine episode manifest/export riêng. Lưu audit ai chọn reference và thời điểm.
- Giữ payload DB summary nhẹ; file video/arrays/MCAP ở artifact storage có checksum, media type, size, retention/access policy. DB index trỏ artifact, không là nơi nhồi payload lớn.
- Không dùng các ROS export placeholder hiện tại để đánh dấu `ROBOT_READY`. Đánh dấu rõ source/provenance trong JSON/ROS message và chặn robot dataset export khi chỉ có trajectory tổng hợp/demo.

### Dashboard

- Khi bắt đầu quay: chọn `Expert reference` đã approved hoặc `Ghi mẫu expert`; nếu capture expert thì có task/version và form note sau từng bước/sau khi dừng.
- Trên trang so sánh: luôn hiển thị tên/session ID, role, approved status, ngày, nguồn measured/DEMO và phiên bản mẫu. Không fallback âm thầm sang DEMO.
- Hiển thị trạng thái quality gate và lý do (camera thấp fps, FSR chưa calibration, IMU không có, tay mơ hồ, match coverage thấp...).
- Tab “Học thao tác”: SOP, clips, keyframes, overlay, review note, delta theo pha.
- Tab “Dữ liệu máy”: schema/units/timestamp/validity, download adapter, cảnh báo observation-only hay robot-ready. Hạn chế nút “train model” tới khi có pipeline train và evaluation riêng.
- Bảng force dùng 3 mức traffic-light đã cấu hình theo task; cho biết đơn vị và loại nguồn. Khi ADC-only, biểu diễn ADC riêng và không gọi lực chuẩn.

## 8. Thứ tự triển khai đề xuất

### P0 — tính trung thực và chọn mẫu tham chiếu

1. Khóa schema/manifest và enum `source_kind`, timestamps, validity, sensor health; kiểm tra dữ liệu thật/demo và ADC/null xuyên suốt AI→backend.
2. Thêm expert reference selection + metadata task/version/approval + expert notes; bỏ fallback DEMO không thông báo.
3. Thêm quality report alignment/camera fps/wrist Hz/gap/hand confidence và readiness reason. Chặn các diễn giải Newton/mm nếu chưa có calibration.
4. Chạy lại test capture→process→publish→DB→API→dashboard trên phiên đo; bảo toàn raw và checksum.

### P1 — learner product

1. SOP theo step từ keyframe/phase, form expert notes, approve/edit.
2. Reference/worker side-by-side theo phase; metric thời lượng/DTW có định nghĩa.
3. Clip segmentation MP4/H.264 và sidecar; overlay 2D landmarks/tracks, force chỉ theo nguồn/đơn vị hợp lệ.
4. Benchmark end-to-end generation dưới 15 phút và đo clarity bằng review với người học/chuyên gia.

### P2 — machine episode

1. Chốt action space với hệ robot cụ thể; tích hợp ghi robot state/command hoặc teleoperation.
2. Lập calibration workflow FSR, camera-to-workspace/hand-to-robot; lưu uncertainty và lịch hết hạn.
3. Export canonical HDF5 hoặc Zarr episode + MCAP ROS replay; tạo validator đọc lại để so sample count/time/hash.
4. Nếu dùng LeRobot hoặc framework khác, làm converter và round-trip validation.

### P3 — nghiệm thu và tập dữ liệu

1. Bổ sung instrument đồng hồ/packet loss và benchmark dài hạn với số lượng episode đại diện.
2. Đạt từng ngưỡng spatial/force/temporal theo quy trình đo độc lập; công bố metric và điều kiện đo.
3. Review nhãn/consent/license; split không leakage; kiểm tra phân bố người/ca/fixture và quality bias.
4. Chỉ sau đó gắn nhãn `ROBOT_READY`, phát hành dataset version và chạy baseline training/evaluation có version cố định.

## 9. Bảng nghiệm thu cần điền bằng chứng

| Metric | Mục tiêu | Phép đo/evidence cần lưu | Trạng thái ban đầu theo hồ sơ dự án |
|---|---:|---|---|
| SOP generation | <15 phút | `processing_completed - processing_started`, artifact ready và kích cỡ input; báo p50/p95 | Chưa có benchmark end-to-end được ghi trong tài liệu. |
| Video | ≥720p hoặc WVGA, 30 FPS | Stream metadata + số frame/timestamp trong capture dài; kiểm tra hình chi tiết thực | Firmware hiện QVGA 320×240; các lượt được ghi khoảng 17–18 FPS. |
| Wrist sampling | ≥50 Hz | Rate từ timestamp thiết bị, p50/p95 interval, jitter, seq gap trên từng session | Có lượt xấp xỉ 50 Hz; không bảo đảm mọi phiên; cảm biến IMU/Fsr chưa đủ. |
| Camera–sensor alignment | ≤10 ms | Histogram delta, coverage %, missing/interpolated flags; không chỉ cấu hình tolerance | Cấu hình join ±10 ms tồn tại; chưa chứng minh toàn bộ pair/coverage. |
| Clock drift/offset | <2 ms | Log offset/dispersion/uncertainty so clock reference trong suốt episode | NTP status có được ghi; chưa thấy bằng chứng đạt <2 ms. |
| Packet loss | <0.1% | Sequence expected/received, duplicate/reorder, reconnect; mẫu số rõ | Có kiểm tra sequence ở một số lượt; chưa công bố tiêu chí/tổng hợp chuẩn. |
| Sensor flatline/saturation | Không treo/bão hòa ngoài ngưỡng hợp lệ | Per-channel range/std/stuck duration + calibration status | Gần nhất ADC min/max GPIO32/33/34/35: 0–4095, 0–942, 0–917, 0–0; kênh 4 chưa phản hồi ở phép thử đó. |
| Lực | Đo 0.1–20 N đủ độ chính xác theo task | Per-sensor calibration curve, holdout points, hysteresis, uncertainty, load-cell ID | Chỉ ADC thô; không đủ căn cứ xuất Newton. |
| Vị trí vi thao tác | <2 mm | Independent ground truth; MAE/RMSE/p95/bias; workspace/calibration version | Landmark ảnh/chưa có pose metric hand-to-robot. |
| Left/right | Nhãn đúng theo ground truth | Confusion matrix theo tay/occlusion/mirror, test sessions và confidence thresholds | Handedness MediaPipe có; bộ nghiệm thu định lượng chưa thấy. |
| Learner package | Mọi step có instruction/keyframe/reference/notes đã duyệt | Artifact validator + expert review + learner usability check | HTML/PDF SOP có; step/note/clip workflow chưa hoàn chỉnh. |
| Robot package | S/A, timestamps, units, calibration, quality & replay đều đạt | Schema validator, replay equivalence, checksum, train/test split audit | Chưa robot-ready; trajectory đo có thể rỗng và export summary không đủ action ground-truth. |

Không điền PASS từ giá trị mục tiêu. Mỗi dòng nghiệm thu phải liên kết file báo cáo, command/config, firmware, thiết bị và session IDs dùng đo.

## 10. Tổ chức artifacts gợi ý

Giữ cấu trúc session nguồn hiện tại, thêm export có version:

```text
ai/generated_data/sessions/<session_id>/
  session_role.json
  capture_manifest.json
  camera.jsonl / video source
  wrist_raw.jsonl
  camera.normalized.jsonl
  real_sensors.jsonl
  multimodal.jsonl
  action_segments.json
  keyframes.json
  analysis_result.json
  quality/alignment.json
  quality/sensor_health.json
  expert/notes.json
  exports/learner/v1/manifest.json
  exports/learner/v1/sop.html
  exports/learner/v1/sop.pdf
  exports/learner/v1/clips/*.mp4
  exports/robot/v1/episode_manifest.json
  exports/robot/v1/episode.h5  # or episode.zarr/
  exports/robot/v1/episode.mcap
  checksums.sha256
```

Tên `camera.jsonl`/video có thể khác tùy kiểu capture; manifest phải mô tả chính xác artifact thật thay vì giả định mọi session giống nhau. Không cần nhân đôi video giữa gói learner và machine nếu có thể tham chiếu cùng artifact immutable.

## 11. Bảo mật, riêng tư và tái lập

- Video tay/người có thể là dữ liệu cá nhân. Ghi consent/purpose, retention, người được truy cập và điều kiện xóa; pseudonymize worker ID. Không xuất public/đám mây trước khi policy dự án cho phép.
- Bảo vệ API tải raw/source, MCAP và video theo quyền; checksum xác minh toàn vẹn không thay cho access control.
- Version mọi thứ ảnh hưởng kết quả: firmware, camera config, AI model/rules, preprocessing, alignment, calibration, expert procedure, exporter/schema. Không thay artifact đã publish; phát version mới và giữ lineage.
- Tách license/quyền sở hữu video, annotations, model output và expert notes. `ROBOT_READY` cần quyền dùng cho huấn luyện/redistribution phù hợp.
- Lưu raw immutable theo retention đã định; cho phép regenerate derived outputs từ raw+versioned config. Ghi lỗi pipeline/retry thay vì lặng lẽ bỏ các frame lỗi.

## 12. Quy trình vận hành mẫu

1. Chọn procedure/task version và kiểm tra thiết bị, calibration còn hạn, clock, stream resolution/rate, MQTT sequence.
2. Quay expert với role `expert`; chuyên gia ghi/chỉnh nội dung và approve từng bước/mẫu. Kiểm tra trái/phải, phase, note và sensor health.
3. Quay worker, chọn đúng expert reference đã approve. Thu immutable raw; xử lý alignment, AI, keyframes, candidate annotations và quality report.
4. Cho chuyên gia duyệt note/action labels và xử lý cảnh báo. Tạo learner package nếu `LEARNER_READY`; tạo robot episode chỉ nếu observation/action và calibration vượt gate.
5. Publish artifacts/manifest/checksum và DB metadata; dashboard hiển thị nguồn/reference/readiness. Tải lại artifact và validate hash/schema/replay trước khi dùng dạy hoặc train.
6. Khi sửa rule/model/calibration, tạo derived version mới; không thay nội dung đã dùng cho một lớp học hoặc experiment trước.

## 13. Nguồn tham khảo format

- [MCAP Format Specification](https://mcap.dev/spec) — message có `log_time`, `publish_time`, sequence và schema/channel; hữu ích để thiết kế timestamp và replay.
- [ROS 2: Recording and playing back data](https://docs.ros.org/en/rolling/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.html) và [rosbag2 repository](https://github.com/ros2/rosbag2) — công cụ record/playback và các lựa chọn storage của ROS 2. Xác nhận plugin/storage phù hợp với môi trường triển khai trước khi chốt.
- [LeRobot Dataset v3](https://huggingface.co/docs/lerobot/lerobot-dataset-v3) — ví dụ format robot-learning kết hợp Parquet cho chuỗi số, MP4 cho video và metadata episode/task.
- [Zarr documentation](https://zarr.readthedocs.io/en/stable/) — hướng dẫn lưu array đa chiều theo chunk và metadata.
- [HDF5 documentation](https://docs.h5py.org/en/stable/) — giao diện Python phổ biến cho HDF5 và dataset/group.

Các liên kết trên là tài liệu format/tham khảo triển khai. Chúng không xác nhận thiết bị hoặc bộ dữ liệu SmartWear hiện đạt các chỉ tiêu nghiệm thu.
