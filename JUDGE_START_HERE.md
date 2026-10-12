# Chạy SmartWear để chấm thử

**Không cần tải file Docker TAR vào GitHub.** Repo chứa mã nguồn và `Dockerfile.judge`; máy giám khảo tự tạo image rồi chạy. Lần build đầu cần Internet và Docker Desktop đang chạy. Không cần cài Python, Node, camera hay vòng tay.

## Máy Windows: cách nhanh nhất

1. Cài và mở [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/); đợi trạng thái **Engine running**.
2. Tải repo bằng **Code → Download ZIP**, giải nén. Nếu repo riêng tư, cần được cấp quyền truy cập trước.
3. Trong thư mục vừa giải nén, nhấp đúp **`START_JUDGE.cmd`**. Đợi cửa sổ báo `SmartWear is ready`; trình duyệt sẽ mở `http://localhost:8000`.
4. Trên trang, chọn **Tải video lên**, xác nhận quyền sử dụng video rồi bấm **Tải lên và phân tích**. Chờ hoàn tất để xem hành động tay trái và tay phải, ảnh và tải báo cáo. Chế độ này không cần phần cứng; video không có dữ liệu lực/IMU thật.

Lần đầu Docker tải thư viện và build image nên có thể mất vài phút. Những lần sau vẫn dùng `START_JUDGE.cmd`; Docker tái sử dụng các lớp đã build. Kết quả đã lưu nằm trong Docker volumes và vẫn còn sau khi dừng ứng dụng.

## Chạy bằng lệnh nếu không dùng Windows

Mở terminal tại thư mục gốc repo, với Docker Engine đang chạy:

```sh
docker build --platform linux/amd64 -f Dockerfile.judge -t smartwear-judge:1.0.0 .
docker compose -f compose.judge.yaml up -d --pull never --no-build
```

Mở `http://localhost:8000`. Kiểm tra trạng thái tại `http://localhost:8000/ready` (kết quả mong đợi: `{"status":"ready"}`). Để dừng mà giữ dữ liệu:

```sh
docker compose -f compose.judge.yaml down
```

Nếu cổng 8000 đã dùng, đặt `SMARTWEAR_PORT=8001` trước khi chạy. Trên Windows PowerShell: `$env:SMARTWEAR_PORT=8001`; trên CMD: `set SMARTWEAR_PORT=8001`; trên Linux/macOS: `export SMARTWEAR_PORT=8001`. Sau đó mở `http://localhost:8001`.

Để xem lỗi: `docker compose -f compose.judge.yaml logs --tail 100 smartwear`. Hướng dẫn đầy đủ: [docs/JUDGE_QUICKSTART.md](docs/JUDGE_QUICKSTART.md).

**Lưu ý:** GitHub repo không chứa image đã build. Máy chấm cần Internet trong lần build đầu. Nếu muốn chạy hoàn toàn offline mà không build, hãy đăng `smartwear-judge.tar` như một **GitHub Release asset** riêng rồi dùng hướng dẫn nạp image trong `docs/JUDGE_QUICKSTART.md`.
