# SmartWear Judge: cài, chạy và xem kết quả bằng Docker

Gói này chạy **một ứng dụng** gồm giao diện, backend và AI trên CPU. Bạn mở
`http://localhost:8000`, tải video thao tác lên, xác nhận quyền dùng video, rồi
bấm **Tải lên và phân tích**. Không cần ESP32, vòng tay, webcam, MQTT hoặc GPU.
Mỗi lần xử lý, AI lưu video nguồn và kết quả trong Docker volumes. Video tải lên
không có số lực/IMU, mẫu so sánh hoặc kết luận MUDA.

## 1. Cài Docker lần đầu trên Windows

1. Mở **PowerShell với quyền Administrator** và chạy `wsl --install`. Khởi động
   lại máy nếu Windows yêu cầu. Nếu máy đã có WSL, chạy `wsl --update`.
2. Tải và cài **Docker Desktop for Windows** từ
   <https://docs.docker.com/desktop/setup/install/windows-install/>. Chọn
   **WSL 2 / Linux containers** trong lúc cài. Mở Docker Desktop và đợi trạng
   thái Engine running. Windows cần bật virtualization; nếu installer báo thiếu,
   làm theo thông báo của Docker Desktop.
3. Mở PowerShell mới, chạy `docker version` và `docker compose version`. Hai
   lệnh phải trả về phiên bản. Nếu `docker` không được nhận ra, đóng/mở lại
   PowerShell hoặc khởi động lại máy. Nếu CMD nhận `docker` nhưng cửa sổ
   PowerShell cũ không nhận, hãy mở PowerShell mới; có thể nạp lại `PATH`
   ngay trong cửa sổ hiện tại bằng:

   ```powershell
   $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
   docker version
   ```

   `docker version` cần hiện cả **Client** lẫn **Server**. Nếu chỉ có Client và
   báo không nối được `docker_engine`, mở Docker Desktop và đợi Engine running.

Máy chấm chỉ cần bước cài Docker một lần; không cần cài Python hay Node. Nếu
Docker Desktop không chạy được, kiểm tra phiên bản Windows/WSL và cấu hình máy
theo trang cài đặt chính thức ở trên.

## 2A. Bạn có mã nguồn: tự build và kiểm tra image

Khi Docker Desktop báo **Engine running**, có thể nhấp đúp
`deployment/BUILD_JUDGE.cmd` để build, kiểm thử và xuất gói; cửa sổ sẽ giữ lại
kết quả để đọc. Hoặc trong PowerShell:

```powershell
cd C:\Task\smartwear-ai
.\deployment\build-judge.ps1
```

Script build `linux/amd64`, chạy kiểm tra upload AI với volume trống, restart,
rồi xuất `release\SmartWear-Judge-1.0.0\smartwear-judge.tar`, Compose,
`manifest.json` và `SHA256SUMS.txt`. Build lần đầu cần Internet và có thể lâu
vì phải tải các thư viện AI. Nếu PowerShell chặn `.ps1`, mở một phiên bằng
`powershell -ExecutionPolicy Bypass -File .\deployment\build-judge.ps1`;
không cần thay đổi Execution Policy toàn máy.

`verify-judge.ps1` dùng video đen ngắn để kiểm tra luồng kỹ thuật. Bản image
này từng được thử với một video AVI có tay phải. Mã hiện tại nhận diện hai tay;
`deployment/VERIFY_REAL_VIDEO.cmd` dùng video mẫu hai tay để kiểm tra cả hai nhãn
trên image mới. Video thử không có trong gói bàn giao.
Trước khi bàn giao, vẫn nên thử thêm MP4 H.264 có quyền sử dụng và kiểm chất
lượng nhận diện bằng mắt. Xem
`docs/deployment/THIRD_PARTY_NOTICES.md` để kiểm tra quyền phân phối dependencies
và model trước khi gửi image ra ngoài.

## 2B. Máy chấm chỉ nhận gói đã xuất, không cần mã nguồn

Mở PowerShell trong thư mục `SmartWear-Judge-1.0.0` đã nhận:

```powershell
docker image load -i .\smartwear-judge.tar
docker compose -f .\compose.judge.yaml up -d --pull never --no-build
docker compose -f .\compose.judge.yaml ps
```

Mở <http://localhost:8000>. Sau khi chạy, image không cần Internet, model và
dependencies đã nằm trong TAR. **Không** chạy `docker compose build` ở máy chấm.

Nếu cổng 8000 đang được dùng, trước lệnh `up` chạy:

```powershell
$env:SMARTWEAR_PORT=8001
docker compose -f .\compose.judge.yaml up -d --pull never --no-build
```

Khi đó mở <http://localhost:8001>. Compose chỉ cho phép truy cập từ chính máy
đang chạy Docker (`127.0.0.1`); đây là chế độ chấm cục bộ, không dùng làm máy
chủ công khai.

## 3. Dùng ứng dụng

1. Chọn video MP4/MOV/AVI/WebM (tối đa 50 MiB, 3 phút; khuyên dùng MP4 H.264).
2. Tích xác nhận quyền sử dụng video, bấm **Tải lên và phân tích**.
3. Chờ trạng thái **Đã hoàn tất**. Danh sách phiên phía dưới mở kết quả: chuỗi
   hành động tay trái và tay phải, ảnh tiêu biểu và báo cáo. Với video không thấy tay nào,
   không có hành động nào được tạo giả.
4. Tải báo cáo PDF/HTML và ZIP nguồn ở phần kết quả. Lực/FSR và IMU không có
   trong video sẽ hiện là thiếu dữ liệu; không có điểm so với chuyên gia.

Kiểm tra ứng dụng đã sẵn sàng bằng <http://localhost:8000/ready> (hoặc cổng
bạn đã đổi). `{"status":"ready"}` là thành công. Nếu trang chưa mở được:

```powershell
docker compose -f .\compose.judge.yaml ps
docker compose -f .\compose.judge.yaml logs --tail 100 smartwear
```

## 4. Dừng, mở lại và giữ dữ liệu

```powershell
docker compose -f .\compose.judge.yaml down
docker compose -f .\compose.judge.yaml up -d --pull never --no-build
```

Hai Docker volumes giữ database, video và báo cáo qua lần dừng/mở lại.
**Không dùng `down -v`** nếu muốn giữ kết quả. Nếu ứng dụng bị tắt giữa lúc
phân tích, job cũ được đánh dấu thất bại; video nguồn vẫn nằm trong volume để
quản trị viên kiểm tra. Có thể tải video lên lại sau khi ứng dụng chạy.

Để sao lưu dữ liệu ra thư mục trên Windows khi container đang chạy:

```powershell
$id = docker compose -f .\compose.judge.yaml ps -q smartwear
New-Item -ItemType Directory -Force .\backup | Out-Null
docker cp "${id}:/app/backend/data" .\backup\data
docker cp "${id}:/app/backend/static" .\backup\static
```

Nếu cần xem dung lượng cũ, dùng `docker system df` và quản lý Docker volumes
trong Docker Desktop. Không tự xóa `capture_jobs` khi còn phiên cần lưu.
