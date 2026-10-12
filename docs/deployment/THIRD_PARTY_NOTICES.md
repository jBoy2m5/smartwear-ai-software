# SmartWear Judge — thành phần bên thứ ba

Image sử dụng Python, Node (chỉ lúc build), FastAPI, MediaPipe, OpenCV, NumPy,
React và các gói Python/npm được khóa trong `backend/requirements.txt`,
`deployment/requirements-judge.txt`, `frontend/package-lock.json`.

Model nhận diện: `ai/hand_landmarker.task`. Mã tải model hiện có trong
`ai/camera_test.py` trỏ tới kho model MediaPipe của Google. Khi build,
`manifest.json` ghi SHA-256 của file model thực sự đóng gói.

**Cần kiểm tra trước khi bàn giao cho bên ngoài:** giấy phép của toàn bộ
dependencies và quyền phân phối lại chính file model trong repo. Tài liệu này
liệt kê nguồn thành phần, chưa xác nhận quyền phân phối. Repo hiện cũng chưa
khai báo giấy phép cho mã nguồn dự án.
