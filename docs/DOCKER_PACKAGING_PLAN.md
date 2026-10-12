# Kế hoạch đóng gói Docker để bàn giao ban tổ chức

Ngày lập: 11/10/2026. Cập nhật: 12/10/2026. Mã Docker đã được áp lại trên nền `main` nhận diện hai tay; cần build và kiểm thử image mới trước khi bàn giao. Gói đã build trước đó thuộc phiên bản cũ và được giữ ở thư mục sao lưu ngoài repo.

Kiểm thử image cũ đã đạt: giao diện và `/ready` trên volume mới, upload video không có tay, AI xử lý và tạo ZIP nguồn, dữ liệu còn sau khi restart container. Mã hai tay hiện tại đã xử lý video mẫu cục bộ với 3 đoạn tay trái và 5 đoạn tay phải; chưa xác nhận image Docker mới cho đến khi chạy lại `BUILD_JUDGE.cmd` và `VERIFY_REAL_VIDEO.cmd`.

Chưa xác nhận: video MP4 H.264 và các codec khác trong container, các tình huống lỗi của bảng kiểm thử bên dưới, chạy trên máy chấm riêng không có Internet, số đo tài nguyên và quyền phân phối model. Không xem các mục này là đã đạt cho đến khi kiểm tra riêng.

## 1. Phương án đề xuất

Đóng gói **một container Linux chạy bằng CPU**, bao gồm dashboard đã build, backend, pipeline AI và model nhận diện tay. Ban tổ chức mở dashboard, tải video của họ lên, phân tích và tải kết quả. Lần chạy đầu có danh sách phiên trống; không cần chuẩn bị dữ liệu mẫu.

Gói bàn giao chính là **image Docker đã build, xuất thành file TAR**, kèm Compose và hướng dẫn. Máy chấm cần cài Docker trước; sau khi nạp image, ứng dụng phải chạy được offline. Việc build image tại máy phát triển vẫn cần Internet để lấy base image và dependencies.

Phạm vi mặc định:

- Không yêu cầu ESP32, SmartCap, SmartWrist, hotspot, MQTT, NTP, webcam hoặc GPU.
- Tải video là màn hình mặc định; chế độ chấm cần ẩn hoặc vô hiệu hóa các nút yêu cầu thiết bị.
- Dùng video do ban tổ chức cung cấp; model AI là thành phần chương trình, không phải dữ liệu phiên mẫu.
- Phân tích video, nhận diện tay, phân đoạn, keyframe, báo cáo nháp và ZIP nguồn theo luồng hiện có.
- Hiển thị rõ lực/FSR, IMU và torque không có dữ liệu; không dùng số mô phỏng để thay thế.
- Không trình bày DTW/MUDA, so sánh expert hoặc robot trajectory như kết quả đã đánh giá khi chỉ có một video.

Chi tiết chức năng hiện có: [VIDEO_UPLOAD.md](VIDEO_UPLOAD.md).

## 2. Hiện trạng và việc cần bổ sung

| Thành phần | Hiện trạng | Việc cần làm trước khi nộp |
| --- | --- | --- |
| Upload video | Đã có API, giao diện và worker AI | Chạy kiểm thử toàn luồng trong container thật |
| Dockerfile | Có `backend/Dockerfile`, chỉ đóng gói backend | Tạo Dockerfile ở cấp dự án, đưa frontend, AI và model vào cùng image |
| Dependencies | Có bộ requirements chạy tại môi trường hiện tại | Xác minh wheel Linux và bộ phiên bản tương thích; khóa phiên bản đã kiểm thử |
| Frontend | Backend phục vụ `frontend/dist` | Build trong stage Node, chép dist sang runtime Python |
| Model | Pipeline dùng `ai/hand_landmarker.task` | Chép model vào image, kiểm checksum và quyền phân phối |
| Xác thực | `production` bắt buộc API key | Chốt cấu hình chế độ chấm cục bộ; kiểm tra frontend gọi API thành công |
| Lưu kết quả | DB, capture jobs và artifacts lưu trên đĩa | Mount volume, chuẩn bị quyền ghi và kiểm tra dữ liệu sau restart |
| Readiness | `/ready` hiện kiểm tra dịch vụ đã khởi tạo | Bổ sung kiểm tra model, interpreter và thư mục ghi; không phụ thuộc thiết bị |
| Dữ liệu khởi tạo | Startup có `KnowledgeService.seed()` | Rà soát seed chỉ chứa định nghĩa quy trình, không tạo phiên hay kết quả mẫu |
| Bàn giao | Chưa có bộ release dành cho máy chấm | Tạo TAR, Compose, hướng dẫn, manifest và checksum |

## 3. Kiến trúc và cấu hình dự kiến

```text
Trình duyệt tại máy chấm
    -> http://localhost:8000
    -> container SmartWear
         frontend/dist + FastAPI + worker AI + model
         -> volume dữ liệu: SQLite, video upload, job
         -> volume artifacts: keyframe, báo cáo, ZIP
```

Chọn một dịch vụ để ban tổ chức chỉ cần khởi động một ứng dụng. Backend phục vụ frontend cùng origin; Node chỉ dùng khi build, không cần chạy trong image cuối.

| Mục | Cấu hình dự kiến |
| --- | --- |
| Kiến trúc image | `linux/amd64` cho máy Intel/AMD; chỉ thêm ARM64 sau khi build và kiểm thử riêng |
| Python | Ưu tiên 3.12 theo Dockerfile hiện có, xác minh tương thích MediaPipe/OpenCV trên Linux |
| Node build | Chọn phiên bản đáp ứng engine của Vite trong lockfile rồi khóa phiên bản |
| Cổng tại máy chấm | `127.0.0.1:8000:8000`; nếu máy đang dùng cổng 8000, hướng dẫn đổi cổng host |
| Web server | Uvicorn một worker; không dùng reload |
| Worker AI | `SMARTWEAR_AI_PYTHON=/usr/local/bin/python`, kiểm tra executable thực tế trong image |
| Database | `SMARTWEAR_DATABASE_URL=sqlite:////app/backend/data/smartwear.db` |
| Volume dữ liệu | `/app/backend/data`, gồm `capture_jobs` và DB |
| Volume artifacts | `/app/backend/static`, gồm PDF, images và dataset artifacts |
| Model | `/app/ai/hand_landmarker.task`, không đặt trong volume dữ liệu |
| Frontend | `/app/frontend/dist`, không đặt trong volume dữ liệu |
| Tài nguyên thử nghiệm | Bắt đầu đo với 4 CPU và 8 GB RAM cấp cho Docker; đây là cấu hình thử, chưa phải yêu cầu tối thiểu |

Giữ một worker và một instance vì CaptureManager hiện dùng khóa trong tiến trình để ngăn các job chạy đồng thời. Chỉ tăng số worker khi đã có cơ chế điều phối job dùng chung.

Dung lượng đĩa cần được đo từ image thực tế và số phiên lưu. Mỗi phiên có thể giữ video nguồn, video phân tích, dữ liệu và ZIP; giới hạn upload 50 MiB không phải giới hạn dung lượng toàn phiên.

### Cấu hình xác thực cho máy chấm

Phương án ban đầu cho bản chạy trên máy cá nhân: dùng cấu hình `development`, không API key, chỉ publish cổng trên loopback `127.0.0.1`. Cấu hình này phù hợp với cơ chế xác thực hiện có và cần ghi rõ là chế độ chấm cục bộ.

Nếu ban tổ chức yêu cầu truy cập qua mạng hoặc chế độ `production`, phải bổ sung cách nhập và gửi API key từ giao diện trước khi phát hành. Không nhúng khóa bí mật vào bundle frontend và không bỏ kiểm tra API key của production để xử lý lỗi khởi động.

## 4. Các file cần tạo khi triển khai

| File | Mục đích |
| --- | --- |
| `Dockerfile.judge` | Build nhiều stage từ context thư mục gốc dự án |
| `.dockerignore` | Loại dữ liệu người dùng, môi trường phát triển và thông tin riêng khỏi build context |
| `compose.judge.yaml` | Chạy image phát hành, cấu hình cổng, volume, healthcheck và một instance |
| `deployment/requirements-judge.txt` | Bộ Python dependencies đã kiểm thử trên Linux |
| `deployment/judge.env.example` | Các tùy chọn được hỗ trợ, không chứa khóa thật |
| `deployment/build-judge.ps1` | Build, kiểm tra và xuất image trên máy phát triển Windows |
| `deployment/verify-judge.ps1` | Kiểm tra khởi động, readiness và luồng upload trên bản phát hành |
| `docs/JUDGE_QUICKSTART.md` | Hướng dẫn ngắn cho ban tổ chức, xử lý lỗi và lưu kết quả |
| `release/manifest.json` | Phiên bản, kiến trúc, image ID, nguồn build, model checksum và kết quả kiểm thử |
| `release/SHA256SUMS.txt` | Checksum các file bàn giao |

Các file trên là đầu việc dự kiến; tài liệu này không khẳng định chúng đã tồn tại.

## 5. Trình tự triển khai

### Giai đoạn 1 — Chốt phạm vi và nguồn build

- [ ] Kiểm tra yêu cầu nộp của cuộc thi: định dạng, giới hạn dung lượng, hệ điều hành/CPU máy chấm và khả năng cài Docker.
- [ ] Chốt bản chấm bằng video upload, chạy CPU và không chứa phiên mẫu.
- [ ] Ghi nhận phiên bản mã nguồn thực tế; nếu có thay đổi chưa commit, phải ghi nhận bản snapshot đã build, không chỉ ghi hash commit.
- [ ] Kiểm tra giấy phép dependencies/model, tạo danh sách thành phần và thông báo giấy phép cần bàn giao.
- [ ] Rà soát seed quy trình và bảo đảm database mới không có phiên đã phân tích.

Đầu ra: danh sách chức năng được chấm, mục tiêu kiến trúc và nguồn build xác định.

### Giai đoạn 2 — Build image đầy đủ

- [ ] Stage frontend: cài dependencies bằng lockfile (`npm ci`), build dashboard.
- [ ] Stage runtime: cài Python dependencies, thư viện hệ thống cần cho decoder video và báo cáo.
- [ ] Xác minh MediaPipe/OpenCV thực sự import và giải mã video trong Linux; chỉ dùng biến thể headless sau khi chứng minh tương thích.
- [ ] Chép `backend`, mã AI cần thiết, model và `frontend/dist` vào đúng cấu trúc `/app`.
- [ ] Giữ dependencies cần cho các import backend ngay cả khi chức năng phần cứng không được dùng; giảm dependencies sau khi kiểm tra import và E2E.
- [ ] Chạy ứng dụng bằng người dùng không có quyền root; chuẩn bị quyền ghi cho volume mới.
- [ ] Khóa phiên bản base image/dependencies đã kiểm thử và kiểm tra build lại từ nguồn sạch.

Build context phải loại `.git`, `.venv`, `node_modules`, `.platformio`, logs, DB đang sử dụng, capture jobs, các phiên trong `ai/generated_data`, video cá nhân, khóa và cấu hình Wi-Fi riêng. Dùng COPY có chọn lọc để vẫn đưa model và các tài nguyên chương trình cần thiết vào image.

Đầu ra: image khởi động được, đủ frontend và AI, không cần cài thêm dependencies lúc chạy.

### Giai đoạn 3 — Hoàn thiện chế độ chấm và lưu dữ liệu

- [ ] Mặc định mở upload; không kiểm tra phần cứng khi mở chế độ này.
- [ ] Ẩn/vô hiệu hóa luồng thiết bị trong profile chấm, giải thích nguồn dữ liệu là video tải lên.
- [ ] Cấu hình các thư mục static/PDF/keyframe/dataset đồng nhất với volume đã mount.
- [ ] Healthcheck dùng readiness phù hợp; kiểm tra model, quyền ghi và worker Python, không kiểm MQTT/camera.
- [ ] Khi restart giữa lúc phân tích, job phải có trạng thái rõ ràng, không treo mãi ở `running` hoặc tạo phiên hoàn tất giả.
- [ ] Kiểm tra hủy job, dừng container và xử lý tiến trình con; giữ dữ liệu đã hoàn tất qua restart.
- [ ] Có hướng dẫn dọn các job lỗi/video cũ và sao lưu dữ liệu, không tự xóa kết quả khi khởi động.

Đầu ra: ứng dụng có thể dùng trên máy chấm mới với volumes trống.

### Giai đoạn 4 — Kiểm thử bản phát hành

Kiểm thử phải gọi HTTP vào container thật và chạy worker AI thật. Kết quả unit test trên Windows hoặc test dùng transport giả lập không thay thế bước này.

| Tình huống | Điều kiện đạt |
| --- | --- |
| Máy sạch, volumes mới | UI mở được, danh sách phiên trống, readiness đạt |
| Không phần cứng, không Internet lúc chạy | Mở UI và phân tích được, không tải model/dependencies từ mạng |
| Video MP4 hợp lệ có thao tác tay | Job hoàn tất, có dữ liệu phân tích và tải được artifacts; xem xét chất lượng bằng video có quyền sử dụng |
| Video không thấy tay | Không tạo nhận diện/phase giả, trạng thái và báo cáo diễn đạt đúng |
| Định dạng và codec | Kiểm MP4 H.264 trước, kiểm MOV/AVI/WebM với các codec cụ thể; ghi rõ các codec đã xác nhận |
| File hỏng, quá giới hạn | Báo lỗi rõ, không tạo phiên hoàn tất; kiểm cả body không có Content-Length |
| Giới hạn video | Kiểm 50 MiB, 180 giây, Full HD và 1–120 FPS theo luồng hiện có |
| Hai upload đồng thời | Chỉ một job được xử lý, job còn lại nhận phản hồi rõ |
| Hủy/reload/restart | UI khôi phục trạng thái hợp lệ, worker không bị bỏ lại hoặc publish dữ liệu dở |
| Nguồn dữ liệu | Video gốc trong ZIP có hash đúng; dữ liệu cảm biến thiếu vẫn `null` và có provenance |
| Hiển thị/báo cáo | Không có điểm so sánh hay lực giả; PDF tiếng Việt đọc được, ZIP/keyframe tải được |
| Persistence | DB, video và báo cáo còn sau khi tạo lại container với cùng volumes |
| Máy Windows dùng Docker Linux | Hướng dẫn nạp image và chạy được trên môi trường mới |

Video dùng để kiểm thử có thể tạo tạm hoặc dùng video nội bộ có quyền sử dụng; không cần đưa chúng vào gói nộp. Video synthetic kiểm lỗi luồng xử lý không chứng minh độ chính xác trên thao tác thật.

Đo và ghi lại thời gian xử lý video 30/60/180 giây, RAM cao nhất, dung lượng image/TAR và dung lượng một phiên. Từ số đo mới công bố cấu hình tối thiểu và thời gian chờ dự kiến cho ban tổ chức.

### Giai đoạn 5 — Xuất và bàn giao offline

Cấu trúc dự kiến:

```text
SmartWear-Judge-1.0.0/
  smartwear-judge.tar
  compose.judge.yaml
  JUDGE_QUICKSTART.md
  manifest.json
  SHA256SUMS.txt
  THIRD_PARTY_NOTICES.md
```

Compose bàn giao phải tham chiếu image có tag cố định và không yêu cầu source code/build tại máy chấm. Nếu cuộc thi yêu cầu mã nguồn, bàn giao thêm bản source đã loại dữ liệu riêng.

Ví dụ lệnh xuất sau khi image đã build và đạt kiểm thử:

```powershell
docker image save -o smartwear-judge.tar smartwear-judge:1.0.0
```

Docker hỗ trợ xuất image và các tag thành TAR bằng [docker image save](https://docs.docker.com/reference/cli/docker/image/save/). Kết quả người dùng tạo trong volumes cần sao lưu riêng; gói phát hành này bắt đầu với dữ liệu phiên trống.

Hướng dẫn chạy dự kiến cho ban tổ chức, sau khi đã cài Docker và mở thư mục bàn giao:

```powershell
docker image load -i smartwear-judge.tar
docker compose -f compose.judge.yaml up -d --pull never --no-build
docker compose -f compose.judge.yaml ps
```

Sau đó mở `http://localhost:8000`, chọn video, xác nhận quyền sử dụng, bấm **Tải lên và phân tích**, chờ hoàn tất và tải báo cáo/ZIP. Các lệnh này chỉ áp dụng khi bộ release đã được tạo.

[docker image load](https://docs.docker.com/reference/cli/docker/image/load/) nạp lại image và tag. Các tùy chọn `--pull never` và `--no-build` của [docker compose up](https://docs.docker.com/reference/cli/docker/compose/up/) giúp bản bàn giao dùng image đã nạp mà không pull/build khi khởi động.

Lệnh xem lỗi và dừng ứng dụng dự kiến:

```powershell
docker compose -f compose.judge.yaml logs --tail 100
docker compose -f compose.judge.yaml down
```

Hướng dẫn thông thường không thêm `-v` vào lệnh dừng vì cần giữ volumes chứa kết quả chấm. Quickstart cần có cách đổi cổng, kiểm Docker đang chạy và nhận biết video có codec chưa hỗ trợ.

## 6. Điều kiện hoàn tất trước khi nộp

- [ ] Image đã build và chạy trên đúng kiến trúc máy chấm.
- [ ] Máy mới chỉ cần Docker và bộ bàn giao; không cần Python, Node hoặc phần cứng.
- [ ] Lần đầu mở không có phiên/dữ liệu mẫu, vẫn upload và phân tích được.
- [ ] Chạy offline sau khi nạp image; model và dependencies có sẵn.
- [ ] Upload, hủy, lỗi, restart, tải PDF/ZIP và persistence đều đạt E2E.
- [ ] Không chứa video riêng, database cũ, Wi-Fi credentials hoặc API key thật.
- [ ] Có manifest, checksum, thông báo giấy phép và hướng dẫn đã chạy thử từ đầu.
- [ ] Công bố giới hạn và cấu hình dựa trên số đo thực tế.

Thứ tự ưu tiên: build đầy đủ ứng dụng → kiểm tra Linux/codec/model → cấu hình volumes và chế độ chấm → E2E offline → xuất TAR và hướng dẫn. Việc thu thập dữ liệu mẫu không phải điều kiện để đóng gói hoặc khởi động bản này.
