# SmartWear AI

SmartCap FPV + SmartWrist IMU/FSR → MQTT/MJPEG gateway → AI observations → backend/dashboard.

## Triển khai hiện tại (06/10/2026)

- SmartCap: `192.168.137.111:81/stream`.
- SmartWrist: `192.168.137.100`, publish `wearable/user01/wrist/data`.
- Máy Layer 2/3: `192.168.137.1`, MQTT 1883, NTP 123, backend 8000.
- Ghép timestamp nguồn mặc định **±10 ms**, dữ liệu thiếu để null, không thay bằng mô phỏng.

Bắt đầu tại **[Hướng dẫn Layer 1 → Layer 3](docs/layer1-layer3/README.md)**, [các lệnh triển khai](docs/layer1-layer3/RUNBOOK.md), [hợp đồng dữ liệu](docs/layer1-layer3/CONTRACT.md), [rà soát](docs/layer1-layer3/AUDIT.md) và [kết quả kiểm thử](docs/layer1-layer3/VALIDATION.md).

## Thành phần

| Thư mục | Chức năng |
|---|---|
| `firmware/` | ESP32-CAM AI-Thinker và ESP32-WROOM, PlatformIO |
| `deployment/` | Config broker, môi trường LAN, khởi chạy backend, AI smoke test |
| `ai/hardware/` | MQTT/MJPEG, raw capture, ghép online/offline, NTP, preflight |
| `ai/preprocessing/` | Chuẩn hóa, multimodal v2, phân đoạn và keyframe |
| `ai/analysis/` | So sánh phiên và cảm biến, gợi ý MUDA để xem lại |
| `ai/integration/` | Capture dashboard và publish backend |
| `backend/` | FastAPI, persistence, API, SOP, robot dataset exporter |
| `frontend/` | React dashboard đọc API và live preview |
| `docs/layer1-layer3/` | Tài liệu và bằng chứng kiểm thử đợt triển khai |

## Chạy nhanh trên máy tạo Mobile Hotspot 192.168.137.1

Sau khi cài dependency, chạy broker/NTP và nạp firmware theo runbook:

```powershell
. .\deployment\hardware.ps1
.\.venv\Scripts\python.exe -B ai\hardware\preflight.py
.\.venv\Scripts\python.exe -B ai\hardware\raw_capture.py --duration-s 60
.\deployment\start-backend.ps1
```

Mở dashboard tại `http://192.168.137.1:8000/`. File phiên nằm trong `ai/generated_data/sessions/`; metadata ghi nguồn đo/mô phỏng và checksum. Dùng `.venv` ở root, không dùng venv cũ đã copy từ máy khác.

## Giới hạn

Firmware build và test phần mềm không chứng minh phần cứng đã hoạt động. Xem VALIDATION để biết trạng thái mạng/USB thực. Action labels hiện là heuristic từ MediaPipe, chưa có model TCN/ensemble được huấn luyện và benchmark F1. ADC chưa phải Newton, head IMU/torque không có nguồn đo; tọa độ bàn tay chưa được hiệu chuẩn sang robot. Dữ liệu DEMO luôn giữ nguồn mô phỏng riêng.

Repo chưa khai báo license dự án; thư viện phụ thuộc có license riêng.
