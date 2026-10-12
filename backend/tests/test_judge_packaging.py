"""Judge profile must not start hardware or leave interrupted uploads running forever."""

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.main import create_app
from backend.services.capture import CaptureManager


class JudgePackagingTests(unittest.TestCase):
    def test_judge_api_disables_device_routes_and_keeps_upload_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(environment="test", judge_mode=True,
                                database_url=f"sqlite:///{(root / 'db.sqlite').as_posix()}",
                                static_dir=root / "static", pdf_dir=root / "static/pdf",
                                keyframe_dir=root / "static/images", dataset_dir=root / "static/dataset")
            with TestClient(create_app(settings, serve_frontend=False)) as client:
                self.assertEqual(client.post("/api/v1/capture/").status_code, 409)
                self.assertEqual(client.get("/api/v1/capture/devices").status_code, 409)
                self.assertEqual(client.post("/api/v1/capture/upload?filename=x.mp4&consent=false").status_code, 422)

    def test_profile_rejects_camera_without_probing_devices(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Settings(environment="test", judge_mode=True,
                                static_dir=Path(temporary) / "static")
            manager = CaptureManager(settings)
            with self.assertRaisesRegex(RuntimeError, "chỉ nhận video tải lên"):
                manager.start("hardware")
            with self.assertRaisesRegex(RuntimeError, "chỉ nhận video tải lên"):
                manager.start("demo")
            self.assertEqual(list(manager.root.iterdir()), [])

    def test_restart_marks_only_unfinished_jobs_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Settings(environment="test", judge_mode=True,
                                static_dir=Path(temporary) / "static")
            root = settings.static_dir.parent / "data" / "capture_jobs"
            active = root / ("a" * 32)
            finished = root / ("b" * 32)
            active.mkdir(parents=True)
            finished.mkdir()
            (active / "status.json").write_text(json.dumps({
                "stage": "processing", "session_id": None, "capture_mode": "upload"}), encoding="utf-8")
            (finished / "status.json").write_text(json.dumps({
                "stage": "completed", "session_id": "VIDEO_saved", "capture_mode": "upload"}), encoding="utf-8")
            manager = CaptureManager(settings)
            self.assertEqual(manager.status(active.name)["stage"], "failed")
            self.assertEqual(manager.status(finished.name)["session_id"], "VIDEO_saved")


if __name__ == "__main__":
    unittest.main()
