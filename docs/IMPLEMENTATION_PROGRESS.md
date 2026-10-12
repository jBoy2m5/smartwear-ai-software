# Hoàn thiện hai luồng dữ liệu và hai bài thực hành

Đối chiếu `DATA_PRODUCTS_ROADMAP.md` và `DEMO_TWO_WORKFLOWS.md`, ngày 07/10/2026. Đây là kết quả phần mềm và hướng dẫn vận hành; không xác nhận bài thực nghiệm hoặc robot đã đạt.

**Lượt tiếp tục mới nhất:** đã sửa cache/lineage, timing clip, SOP offline và xử lý lỗi; backend nạp bản mới, real-archive read-back đạt. Xem [DATA_PRODUCTS_REVIEW_20261007.md](DATA_PRODUCTS_REVIEW_20261007.md) và [báo cáo mới](layer1-layer3/data-products-validation-resumed.json). Các số liệu ở phần kiểm chứng phía dưới là lịch sử trước lượt review này.

## Phần mềm đã triển khai

| Thứ tự | Kết quả | Nơi kiểm tra |
|---|---|---|
| 1 — P0 capture | Capture manifest với hash/size raw, code/model version, clock domain, mirror và event monotonic; MQTT/camera packet giữ receive monotonic riêng. Legacy không có monotonic ghi rõ `legacy_camera_device_relative`. | `ai/hardware/record_hardware.py`, `camera_receiver.py`, `mqtt_wrist.py` |
| 2 — P0 reference | Dashboard chọn task/version, role expert/worker/DEMO, bí danh và đồng ý ghi hình. Worker bắt buộc chọn expert đã duyệt cùng task/version; review revision được pin; không fallback sang DEMO trong luồng này. | `CapturePanel`, capture API và `KnowledgeService` |
| 3 — P0 notes/review | Procedure A/B nháp, ghi chú theo bước, mốc video/keyframe, lý do/mẹo/lỗi/điều kiện dừng, đầu ra và số gợi ý do người ghi. Lưu append-only trong bảng `knowledge_revisions` của DB hiện tại. Review/retire không xóa bản cũ. | `KnowledgePanel`, `/api/v1/knowledge/...` |
| 4 — P0 quality | Rate device/receive, intervals/jitter/gaps, FSR range/std/flatline/saturation, IMU availability, coverage/delta, tracking/confidence, camera acquisition và các trạng thái unknown. | `/knowledge/sessions/{id}/quality` |
| 5 — P1 learner | SOP HTML portable, nguồn expert/worker riêng, seek theo bước; MP4/H.264 VFR từ JPEG và timestamp thật, overlay 2D theo inference, micro-clips/sidecars khi đã gán mốc. Không upscale để tuyên bố đạt acquisition. | Nút tạo gói, ZIP và tab Học thao tác |
| 6 — P2 observation | HDF5 có observations/timestamps/validity, MCAP JSON channels/schema, checksum và read-back validation. Không thêm robot action; IMU thiếu có mask false, ADC không đổi sang N. | `episode_products.py`, tab Dữ liệu máy |
| 7 — validation | Kiểm hash/size, sample count/time/validity, MCAP payload/count/CRC; gói tải lại được. Bộ test có trường hợp draft/approval/reference sai và tranh chấp revision. | `backend/tests/test_knowledge_products.py`, `deployment/validate-data-products.py` |
| 8 — dataset splitting | Script chỉ nhận episode đo thật có review/consent/quyền training và participant/task; chia theo người, không chia frame liền kề. Ít hơn ba người độc lập thì không tạo ba split. | `deployment/build-dataset-index.py` |

Procedure là phiên bản bất biến theo `task_id:version`; notes/approval là revisions độc lập theo session. Metadata, quality và artifact index ở manifest/JSON và DB; chưa tách toàn bộ thành các bảng quan hệ CalibrationRecord/ExpertNote/Artifact riêng. Không có calibration hoặc phép đo clock mới thì trạng thái vẫn missing/unknown.

## Sử dụng từng bước trên dashboard

1. Mở `http://127.0.0.1:8000/`. Chọn công đoạn LOG hoặc lắp bộ v1. Hai SOP ban đầu là bài mẫu chưa duyệt, không phải SOP DENSO.
2. Chọn **Ghi mẫu người hướng dẫn / chuyên gia**. Nhập bí danh, xác nhận đồng ý ghi hình; bố trí vật và hai tay rõ. Bấm **Quay ESP32 + vòng tay**, thực hiện đủ bốn bước, bấm **Kết thúc**. Không mở serial, flash hoặc reset trong khi quay.
3. Mở phiên hoàn tất, mục **Kinh nghiệm chuyên gia và gói dữ liệu**. Điền `why`, các ghi chú cần thiết và start/end từng bước dựa vào video, không dựa vào duration capture. Lưu nháp trước khi review.
4. Người hướng dẫn xem video, chọn đầu ra Đạt, tên người duyệt, lý do duyệt và xác nhận độ rõ; bấm **Duyệt SOP và bằng chứng**. Mẫu thiếu note/mốc hoặc chưa đạt đầu ra không được chọn làm reference.
5. Chọn **Người học**, cùng task/version, đúng mẫu đã duyệt, bí danh người mới và lượt **Trước khi học SOP**. Quay, giữ kết quả đạt hoặc thất bại; người đánh giá ghi số gợi ý, lỗi xác nhận và mốc bước. Không đồng nhất heuristic REACH/GRAB với bước nghiệp vụ hay kết luận lấy đúng linh kiện.
6. Cho học viên xem SOP/clip đã duyệt. Quay lượt **Sau khi học SOP** cùng reference và điều kiện tương đương; điền phiếu bằng chứng. Việc người mới học được vẫn phải quan sát thật, không suy từ DTW score.
7. Bấm **Tạo SOP, clip và episode quan sát**. Tải ZIP và mở `learner/sop.html` offline; HDF5/MCAP ở `arrays/`. Bản nháp vẫn có thể xuất kỹ thuật nhưng `learner_ready=false`, `robot_policy_training_ready=false`.
8. Làm tương tự với bài B. Dùng checklist/evidence tại `demo-kit/`, chạy sân khấu 6–8 phút hai lượt và giữ bản thu thật dự phòng có session ID.

Nếu quay không có ảnh/tay hoặc phân tích không tạo được phase, dữ liệu raw vẫn giữ; không đổi marker hoặc tạo nhãn giả để ép publish. Với bài có vật khó thấy, cần đổi khung hình/ánh sáng/vật mẫu trước khi duyệt độ rõ.

## Kiểm chứng đã làm

- Bộ test cuối: **58 passed, 8 subtests passed** khi chạy:

  ```powershell
  .\.venv\Scripts\python.exe -B -m pytest ai backend/tests --ignore=ai/generated_data -q
  npm.cmd run build --prefix frontend
  git diff --check
  ```

- Test review/export dùng fixture tổng hợp trong thư mục tạm, không phải nghiệm thu chuyên gia thật. Kiểm thêm MP4 overlay và bốn micro-clips từ JPEG fixture.
- Kiểm bundle trên phiên đo thật `MEASURED_hardware_20261007_150625_216050_uk5sxhc9`: 1555 frames; 4610 FSR và 4610 trạng thái IMU trong MCAP; 12 artifact hash/size được verify. Lượt export được tải lại và read-back; `learner_ready=false`, `robot_ready=false` vì phiên cũ chưa có task/SOP đã duyệt. Không gán nó thành expert A/B.
- Hai lượt tạo gói trên phiên này mất khoảng 60.2 s và 42.5 s; chưa là p50/p95 benchmark hoặc phép thử tải cao. Báo cáo máy: `layer1-layer3/data-products-validation.json`.
- API task/reference/quality/product đã nạp vào backend; frontend build đạt. Chưa visual-QA qua browser automation, chưa quay expert/worker thực cho hai task mới.

## Điều kiện vẫn phải thực hiện bằng người và phần cứng

- Xác nhận vật dụng, bản lắp, bốn bước và người có chuyên môn; ghi consent, chuyên môn/ủy quyền phù hợp. Không tự nâng “người hướng dẫn bài mẫu” thành “chuyên gia DENSO”.
- Thu ít nhất reference A và B, worker trước/sau, duyệt note/outcome và clarity; chạy bài học không gợi ý và ghi cả thất bại. Các ô nghiệm thu người học và kịch bản sân khấu trong hai tài liệu gốc chưa được đánh dấu đạt.
- Kiểm độc lập từng FSR, khắc phục kênh không phản hồi và IMU. Hiệu chuẩn FSR bằng nguồn lực chuẩn/holdout/hysteresis; không dùng min/max ADC để đổi Newton.
- Camera hiện QVGA, các lượt trước chưa đạt WVGA/720p 30 FPS. Không thay firmware đang ổn định chỉ để đuổi KPI chưa đo gần demo.
- Chưa đo clock <2 ms, spatial <2 mm hoặc packet loss dài hạn đủ đại diện; các gate còn unknown/fail. Match tolerance 10 ms không chứng minh clock accuracy.
- Chưa có robot/platform/action space/state/command/teleop/hand-to-robot calibration. Do đó export robot bị chặn; MCAP hiện là replay dữ liệu quan sát JSON, chưa là adapter ROS 2 cho điều khiển robot. LeRobot/Zarr converter và baseline train/eval còn cần mục tiêu/dữ liệu hợp lệ.
- Chưa có dữ liệu đủ người/ca/fixture, training rights và đánh giá độc lập để công bố hiệu quả học, accuracy hoặc ROBOT_READY.

## Lệnh tải và xác minh gói

```powershell
.\.venv\Scripts\python.exe -B deployment/validate-data-products.py --url http://127.0.0.1:8000/api/v1/knowledge/sessions/MEASURED_hardware_20261007_150625_216050_uk5sxhc9/products/observation --output docs/layer1-layer3/data-products-validation.json
```

Exporter dùng [h5py datasets](https://docs.h5py.org/en/stable/high/dataset.html) và [MCAP Writer](https://mcap.dev/docs/python/mcap-apidoc/mcap.writer). Các format không tự xác nhận dữ liệu robot-ready.
