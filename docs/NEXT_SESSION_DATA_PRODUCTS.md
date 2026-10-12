# Bàn giao: hoàn thiện hai demo và hai sản phẩm dữ liệu

Ngày lưu: 07/10/2026. **Người dùng yêu cầu dừng công việc để lưu tiến trình và tiếp tục ở phiên sau.** Đọc file này trước; không tự bắt đầu quay hoặc duyệt mẫu chuyên gia.

**Cập nhật sau khi người dùng yêu cầu tiếp tục:** đã hoàn thành lượt review exporter/timing/cache/cleanup, khởi động backend bản mới và real-archive read-back. Đọc [DATA_PRODUCTS_REVIEW_20261007.md](DATA_PRODUCTS_REVIEW_20261007.md) trước các mục lịch sử bên dưới. Episode mới `3fcfd3e0cc9f8742`, 1.555 frames, 12 artifacts/13 checksum hợp lệ, 48,703 giây; hash exporter runtime khớp file. Suite toàn bộ 61 tests + 8 subtests đạt; lượt targeted cuối 20 tests đạt. Chưa có browser điều khiển được và chưa nhận thông tin thực nghiệm A/B. Tiếp theo: visual-QA và chuẩn bị/quay/review thật khi có người/vật dụng; không cần lặp export cũ nếu code/nguồn chưa đổi.

## 1. Yêu cầu đang thực hiện

Đọc chi tiết và hoàn thiện từng bước hai tài liệu do người dùng đưa vào `docs/`:

- `docs/DATA_PRODUCTS_ROADMAP.md`: P0 provenance/reference/quality, P1 learner package, P2 machine episode, P3 nghiệm thu.
- `docs/DEMO_TWO_WORKFLOWS.md`: bài A LOG soạn/kiểm bộ và bài B lắp bulông–long đen–đai ốc bằng tay; reference, lượt trước/sau học, SOP/notes, evidence và sân khấu 6–8 phút.

Đã đọc cả hai. Hướng dẫn triển khai chi tiết nằm ở `docs/IMPLEMENTATION_PROGRESS.md`; phiếu thực nghiệm trống ở `docs/demo-kit/EVIDENCE.md`.

**Chưa hoàn tất toàn bộ roadmap.** Phần mềm đang có bản triển khai đầu tiên; quay/duyệt hai bài, đánh giá người học, calibration và điều khiển robot chưa có bằng chứng.

## 2. Trạng thái Git

- Nhánh hiện tại: `main`.
- Commit gần nhất đã push trước công việc này: `af1f90943ed1b7fa5b758f8c4722ca34f2d09d86`.
- Danh tính Git đã sửa đúng người dùng: `tinhBa180906 <226667564+tinhBa180906@users.noreply.github.com>`.
- **Các thay đổi của workflow chuyên gia/data products hiện chưa commit hoặc push.** Có cả file modified và file untracked. Không reset, clean hoặc ghi đè chúng.
- Hai tài liệu yêu cầu ban đầu cũng đang là untracked; đã thêm link cập nhật và sửa đoạn mô tả dashboard, giữ nội dung chính và checklist thực nghiệm chưa đạt.
- Dữ liệu/video/ảnh đo thật giữ cục bộ; không tự đưa vào Git. Khi commit sau này, chọn file mã nguồn/tài liệu cụ thể, không `git add .`.

## 3. Đã triển khai vào mã

### Workflow chuyên gia và người học

- Dashboard chọn role `expert` / `worker` / `demo`, task/version A/B, bí danh, consent và lượt reference/trước học/sau học/luyện tập.
- Worker bắt buộc chọn reference expert đã approved cùng task/version. Review revision được pin; không tự fallback DEMO trong luồng này.
- Backend lưu procedure/session knowledge append-only trong bảng mới `knowledge_revisions` của database hiện tại. Task procedure versions bất biến theo key; notes/review là revisions riêng.
- Form notes theo bước: instruction, why, tips, common_errors, safety, acceptable_variation, start/end giây, keyframe; reviewer/rationale/clarity, outcome, prompt count, errors và quyền sử dụng.
- Approval chặn thiếu rationale/mốc/reviewer/clarity và outcome chưa đánh giá; reference expert phải có outcome passed. Không tự bịa reviewer, consent hoặc kinh nghiệm chuyên gia.
- Worker khởi tạo nội dung SOP từ reference đã chọn, nhưng xóa mốc/keyframe của reference để người đánh giá gán evidence của worker riêng.

### Provenance và dữ liệu thiếu

- `capture_manifest.json`: schema/source, raw artifact hash/size, code/model version, mirror, clock domain, capture events và context.
- Camera packet và MQTT giữ thêm receive monotonic ns. Legacy không có field đó dùng `legacy_camera_device_relative`, không tự nhận là recorder monotonic.
- Confidence handedness <0.5 được coi ambiguous khi score có mặt. Không ép một tay thành tay phải.
- Sự kiện websocket DashboardUpdate cho phép `force=null`; ingest không thay lực thiếu bằng 0. Đã kiểm regression trường hợp đo thật và giữ nguyên kiểu force bắt buộc của RobotTrajectoryPointInput.

### Quality và sản phẩm dữ liệu

- Report có camera acquisition, wrist rate từ device/receive, interval/gap, range/std/flatline/saturation bốn FSR, IMU count, alignment coverage/delta, tracking/confidence, các mục tiêu pass/fail/unknown.
- Gói portable: manifest/checksums, raw ZIP/AVI nguồn, HDF5 observations/timestamps/validity và nhãn bước có review validity, MCAP JSON observations có schema/CRC, HTML SOP, MP4/H.264 VFR, overlay 2D và micro-clips/sidecars nếu đã gán mốc.
- JPEG nguồn được mirror đúng với landmarks. Khi raw JPEG không có trong ZIP nhưng AVI nguồn có, exporter đọc theo `video_frame_index` và tái dựng timing từ JSONL; không coi encoding_fps AVI là acquisition fps.
- Gói worker giữ video reference và worker riêng, seek theo mốc bước và báo chênh thời lượng từ annotation. Không tự gọi DTW/action heuristic là ground truth.
- Không upscale rồi công bố đạt 720p/WVGA 30 FPS; không đổi ADC sang N hoặc landmarks sang mm. IMU thiếu giữ NaN + validity false trong HDF5, null + valid=false trong MCAP.
- Robot actions group rỗng/explicit unavailable; `robot_policy_training_ready=false`. Endpoint robot export mới trả 409.
- Phiên cũ không có task/review chỉ được xuất technical draft, không tự đăng ký thành expert A/B.

## 4. Các file cần giữ và rà soát

File mới quan trọng:

```text
backend/models/knowledge.py
backend/schemas/knowledge.py
backend/services/knowledge.py
backend/services/episode_products.py
backend/api/routes/knowledge.py
backend/tests/test_knowledge_products.py
frontend/src/components/KnowledgePanel.tsx
deployment/validate-data-products.py
deployment/build-dataset-index.py
docs/IMPLEMENTATION_PROGRESS.md
docs/demo-kit/EVIDENCE.md
```

File sửa: `backend/main.py`, API router/capture/sessions, capture manager, requirements, schemas/session và test_backend; frontend backendApi/CapturePanel/SessionDashboard; AI hand_observation, camera_receiver, mqtt_wrist, record_hardware, frontend_capture, backend_bridge; NEXT-SESSION.md.

Dependencies đã cài vào `.venv` và pin ở backend requirements: numpy 2.5.3, h5py 3.16.0, imageio-ffmpeg 0.6.0, mcap 1.5.0, opencv-contrib-python 5.0.0.93. Các dependency AI cũ vẫn giữ.

## 5. Kiểm chứng đã chạy

Kiểm thử cuối cùng **sau sửa websocket force nullable**:

```powershell
.\.venv\Scripts\python.exe -B -m pytest ai backend/tests --ignore=ai/generated_data -q
```

Kết quả: **58 passed, 8 subtests passed** (lượt cuối khoảng 8.77 giây).

- Frontend `npm.cmd run build --prefix frontend` đã thành công sau các thay đổi TypeScript cuối. Các thay đổi sau đó chỉ ở Python/backend. Có warning bundle lớn, không lỗi build.
- Tests mới kiểm review/evidence, immutable context, revision conflicts, wrong reference, HDF5 missing-value masks, MCAP read-back, MP4 overlay và bốn micro-clips từ JPEG fixture; test capture API kiểm truyền context tới AI.
- Fixtures là dữ liệu tổng hợp trong thư mục tạm, **không phải nghiệm thu thật**.
- Lệnh pytest rộng không có `--ignore=ai/generated_data` đã bị lỗi collection do thư mục session bị sandbox chặn. Không sửa/xóa dữ liệu để chữa lỗi đó; dùng lệnh có ignore ở trên.
- Export/download/read-back trên phiên đo thật `MEASURED_hardware_20261007_150625_216050_uk5sxhc9` đã đạt: **1555 frames**, MCAP **4610 FSR + 4610 trạng thái IMU + 1555 camera + 1555 hand observations**, 12 artifact hash/size hợp lệ. Gói khoảng 34.6 MB.
- Báo cáo: `docs/layer1-layer3/data-products-validation.json`; episode được kiểm gần nhất `f24dd78dd240b8bb`, generation ~42.484 giây. Một lượt trước ~60.172 giây. Chưa là p50/p95 hoặc benchmark tải cao.
- `learner_ready=false`, `robot_ready=false` cho phiên cũ; không gán nó thành expert hai bài A/B.
- **Sau lượt benchmark có sửa thêm exporter**: media readiness gate, labels trong HDF5, AVI fallback và receive monotonic trong MCAP. Đã test bằng fixtures, nhưng cần reload backend và kiểm download/read-back bằng real archive lần cuối với đúng exporter mới.

## 6. Runtime hiện tại — phải kiểm lại

- Backend từng được reload hai lần khi đã xác nhận không có capture subprocess. Log ở `backend/data/products-backend*.stdout.log` và `.stderr.log`.
- Backend đang chạy có thể vẫn giữ module trước những sửa cuối; **đừng coi file trên đĩa là code runtime đã reload**. Các PID trong hội thoại cũ không còn đáng tin.
- Khi lưu bàn giao, truy vấn cổng 8000 bằng sandbox không xác minh được; chưa kết luận dịch vụ đang chạy hay dừng. Không có yêu cầu tắt dịch vụ từ người dùng.
- Trước restart: kiểm cổng/tiến trình và capture active; không ngắt phiên đang ghi. Nếu chưa chạy, dùng `deployment/start-backend.ps1`.
- Browser automation trước đó không có browser khả dụng; chưa visual-QA dashboard/reload bằng trình duyệt thật. HTTP/API và frontend build đã kiểm.

## 7. Phần cứng và quy tắc bảo toàn

- Cổng xác nhận gần nhất sau đổi cáp/cổng: **SmartCap COM5**, **SmartWrist COM7**. Liệt kê lại trước khi flash/reset.
- SmartCap dùng ESP32-CAM-MB, đã bỏ IMU. `imu_head=null` là chủ đích. Firmware hiện trên cap là camera bình thường, không phải target wifi diagnostic.
- SmartWrist vẫn có IMU nhưng các mẫu đã kiểm báo unavailable. Có bốn FSR **tay phải**, không có FSR tay trái.
- Phép thử FSR 60 giây: 3003 samples; ADC min/max GPIO32/33/34/35: **0–4095, 0–942, 0–917, 0–0**. Chỉ kênh 1 có tăng/giảm rõ; 2/3 cần đối chiếu từng cảm biến; 4 chưa phản hồi. Không công bố đủ bốn FSR hoặc lực Newton.
- Hotspot máy chủ `192.168.137.1`, camera `.111:81/stream`, MQTT `.1:1883`, topic `wearable/user01/wrist/data`, NTP UDP123.
- Preflight mới ở `docs/layer1-layer3/products-preflight.json` đạt camera TCP/MQTT/NTP/dependency; không chứng minh JPEG rõ, fps/IMU/FSR/calibration đạt.
- Có lịch sử brownout/watchdog; đổi cáp/cổng đã có các phiên phục hồi. Không tuyên bố ổn định dài hạn.
- **Không mở serial/monitor, kể cả không --reset, hoặc flash/reset trong khi raw/AI đang quay.** Serial driver/MB có thể reset bo; từng xảy ra ngay lúc agent đọc COM5.
- Không sửa raw/hashes/roles của phiên cũ; không xóa thư mục session bị hạn chế quyền. Khi cần derived output, tạo phiên bản mới.

## 8. Tiếp tục theo thứ tự

1. Đọc file này, hai tài liệu gốc, IMPLEMENTATION_PROGRESS và kiểm `git status`; giữ toàn bộ sửa đổi chưa commit.
2. Rà exporter/service/API mới trước khi công bố hoàn tất: API approval/reference/retire/version, các link/video/clip offline, xử lý failure, checksum/hash lineage. Rà cache và ensure code SHA mô tả module đã load; không gắn gói generated từ code cũ với code mới.
3. Rà hai bundle learner/observation hiện cùng chứa portable source bundle; nếu cần tách archive thực sự, tạo manifest/checksum riêng cho từng bộ, không xóa artifact còn được manifest tham chiếu.
4. Rà events capture_started/stopped để lấy monotonic ngay tại event, không sau thao tác hash/file nặng; rà cleanup thư mục temp chỉ trong output root, API handling lỗi FFmpeg/IO và clip timing/video-index. Đây là việc review còn lại, chưa ghi đã đạt.
5. Chạy tests/build/diff check. Nếu có sửa mới, broaden/round-trip theo vấn đề; không lặp kiểm vô ích khi không đổi gì.
6. Kiểm runtime và reload backend an toàn. Tải/read-back gói từ **exporter cuối cùng**:

   ```powershell
   .\.venv\Scripts\python.exe -B deployment/validate-data-products.py --url http://127.0.0.1:8000/api/v1/knowledge/sessions/MEASURED_hardware_20261007_150625_216050_uk5sxhc9/products/observation --output docs/layer1-layer3/data-products-validation.json
   ```

7. Kiểm GUI bằng browser khả dụng hoặc người dùng thao tác: chọn expert, participant/consent/task, ghi/publish, notes/review; worker chọn reference đúng task/version và reload không tạo consumer trùng. Chưa có E2E expert/worker thật qua workflow mới.
8. Người dùng cần chuẩn bị/xác nhận vật dụng, người hướng dẫn/người học. Đã hỏi bằng công cụ nhưng chưa nhận câu trả lời trong phiên. Không tự giả định consent hay quyền chuyên gia để quay/approve thay họ.
9. Khi có xác nhận: quay reference A/B thật, duyệt bốn bước; quay người mới trước/sau học cùng reference, ghi đầu ra/số gợi ý/lỗi/mốc. Không biến các session test cũ thành bài A/B.
10. Xuất learner-ready sau review đủ; thử offline và diễn tập 6–8 phút. Chỉ điền metric cải thiện từ dữ liệu đo thật.
11. P2 robot/P3: cần robot/action space/state/command hoặc teleop, calibration FSR/camera/hand-to-robot, đo clock/spatial/loss độc lập, quyền training và split đủ người. Chưa có điều kiện đó thì luôn observation-only. LeRobot/Zarr và adapter ROS2 điều khiển chưa triển khai đầy đủ; MCAP JSON hiện là replay observations.
12. Chỉ commit/push phần này khi người dùng yêu cầu. Nếu có yêu cầu, giữ author/committer đúng tinhBa180906 và không đưa raw/private artifacts vào Git.

## 9. Câu nhắc cho phiên sau

> Đọc docs/NEXT_SESSION_DATA_PRODUCTS.md và NEXT-SESSION.md. Tiếp tục hoàn thiện workflow chuyên gia/SOP/data products theo hai tài liệu trong docs, bắt đầu từ review code còn lại, reload backend an toàn và real-archive round-trip. Không tự quay hay approve mẫu A/B khi chưa có xác nhận người/vật dụng.
