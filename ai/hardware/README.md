# SmartWear hardware pipeline

Cấu hình hiện tại: SmartCap `192.168.137.111`, SmartWrist `192.168.137.100`, máy Layer 2/3 + MQTT/NTP `192.168.137.1`. Ngưỡng ghép mặc định ±10ms.

Xem [bộ hướng dẫn triển khai](../../docs/layer1-layer3/README.md), [runbook](../../docs/layer1-layer3/RUNBOOK.md), [hợp đồng dữ liệu](../../docs/layer1-layer3/CONTRACT.md) và [kết quả kiểm thử](../../docs/layer1-layer3/VALIDATION.md).

`raw_capture.py` thu raw; `record_hardware.py --process` thu và chạy AI; `--publish` gửi backend. `config.py` dùng chung các mặc định CLI/dashboard và hỗ trợ biến môi trường. `live_alignment.py` cung cấp buffer 100 mẫu và callback handoff. `align.py` ghép offline từ giờ thiết bị, giữ missing/null và đo độ lệch.

Chế độ dashboard hardware được bật qua `deployment/hardware.ps1`. Chạy app không có cấu hình này vẫn giữ DEMO mode cũ. Thiếu dữ liệu trong hardware mode không được fallback sang simulator.
