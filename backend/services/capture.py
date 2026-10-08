"""Run the existing local camera/AI pipeline behind browser controls."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from backend.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = PROJECT_ROOT / "ai" / "integration" / "frontend_capture.py"


class CaptureManager:
    def __init__(self, settings: Settings):
        self.root = settings.static_dir.parent / "data" / "capture_jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._active_id: str | None = None
        self._python: str | None = None
        self._python_mode: str | None = None

    def has_active_capture(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def _ai_python(self, capture_mode: str) -> str:
        if self._python and self._python_mode == capture_mode:
            return self._python
        candidates = [os.getenv("SMARTWEAR_AI_PYTHON"), shutil.which("python"),
                      getattr(sys, "_base_executable", None), sys.executable]
        for candidate in dict.fromkeys(item for item in candidates if item):
            try:
                result = subprocess.run(
                    [candidate, "-B", "-c", ("import cv2, mediapipe, paho.mqtt.client"
                                            if capture_mode == "hardware" else "import cv2, mediapipe")],
                    cwd=PROJECT_ROOT, capture_output=True, timeout=20,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    self._python = candidate
                    self._python_mode = capture_mode
                    return candidate
            except (OSError, subprocess.TimeoutExpired):
                continue
        raise RuntimeError("Máy chạy backend chưa có Python với OpenCV, MediaPipe"
                           + (" và Paho MQTT" if capture_mode == "hardware" else "") + ". "
                           "Quản trị viên cần cấu hình SMARTWEAR_AI_PYTHON.")

    def _hardware_preflight(self) -> None:
        """Reject a disconnected camera before creating a failed capture job."""
        from ai.hardware.config import HardwareConfig
        config = HardwareConfig.from_environment()
        if config.mqtt_host == '192.168.137.1':
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind((config.mqtt_host, 0))
            except OSError as exc:
                raise RuntimeError(
                    'Máy chưa có địa chỉ hotspot 192.168.137.1. Bật Windows Mobile Hotspot '
                    'ok123 (2.4 GHz), rồi kiểm tra lại kết nối SmartCap/SmartWrist.') from exc
        camera = urlsplit(config.camera_url)
        if not camera.hostname:
            raise RuntimeError('SMARTWEAR_CAMERA_URL không có địa chỉ camera hợp lệ.')
        try:
            with socket.create_connection((camera.hostname, camera.port or 80), timeout=2):
                pass
        except OSError as exc:
            raise RuntimeError(
                f'Không kết nối được SmartCap tại {camera.hostname}:{camera.port or 80}. '
                'Kiểm tra nguồn, kết nối hotspot và trạng thái khởi động camera.') from exc

    def start(self, capture_mode: str = "hardware", context: dict | None = None) -> dict:
        if capture_mode not in ("hardware", "demo"):
            raise RuntimeError("Chế độ quay không hợp lệ")
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("Một phiên camera đang chạy. Hãy kết thúc phiên đó trước.")
            if capture_mode == 'hardware':
                self._hardware_preflight()
            python = self._ai_python(capture_mode)
            if not CAPTURE_SCRIPT.is_file():
                raise RuntimeError("Không tìm thấy chương trình AI camera")
            job_id = uuid.uuid4().hex
            directory = self.root / job_id
            directory.mkdir()
            backend_url = os.getenv("SMARTWEAR_CAPTURE_BACKEND_URL", "http://127.0.0.1:8000")
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "utf-8"
            environment["SMARTWEAR_CAPTURE_MODE"] = capture_mode
            arguments = [python, "-B", str(CAPTURE_SCRIPT), "--job-dir", str(directory),
                         "--backend-url", backend_url]
            if context is not None:
                (directory / "context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
                arguments.extend(["--context", str(directory / "context.json")])
            with (directory / "run.log").open("wb") as log:
                process = subprocess.Popen(
                    arguments,
                    cwd=PROJECT_ROOT, env=environment, stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            self._process = process
            self._active_id = job_id
            return {"job_id": job_id, "stage": "starting",
                    "message": ("Đang kết nối camera ESP32" if capture_mode == "hardware"
                                else "Đang mở webcam DEMO"),
                    "session_id": None, "capture_mode": capture_mode}

    def directory(self, job_id: str) -> Path:
        if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
            raise FileNotFoundError("Không tìm thấy phiên quay")
        directory = self.root / job_id
        if not directory.is_dir():
            raise FileNotFoundError("Không tìm thấy phiên quay")
        return directory

    def status(self, job_id: str) -> dict:
        directory = self.directory(job_id)
        path = directory / "status.json"
        if path.is_file():
            document = json.loads(path.read_text(encoding="utf-8"))
        else:
            document = {"stage": "starting", "message": "Đang mở camera", "session_id": None}
        if (directory / "stop.flag").exists() and document["stage"] == "recording":
            document = {**document, "stage": "stopping", "message": "Đang kết thúc quay"}
        if (job_id == self._active_id and self._process is not None
                and self._process.poll() is not None
                and document["stage"] not in ("completed", "failed")):
            document = {"stage": "failed", "message": "Camera/AI dừng bất ngờ. "
                        "Quản trị viên kiểm tra run.log của phiên quay.", "session_id": None}
        return {"job_id": job_id, **document}

    def stop(self, job_id: str) -> dict:
        with self._lock:
            directory = self.directory(job_id)
            if job_id != self._active_id or self._process is None:
                return self.status(job_id)
            if self._process.poll() is None:
                (directory / "stop.flag").touch(exist_ok=True)
            return self.status(job_id)
