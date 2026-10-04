"""Camera control state can be checked without activating a physical camera."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.core.config import Settings
from backend.api.routes.capture import preview_frame, preview_observation
from backend.services.capture import CaptureManager


class CaptureManagerTests(unittest.TestCase):
    def test_preview_serves_latest_complete_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "preview_00000001.jpg").write_bytes(b"first")
            (directory / "preview_00000003.tmp").write_bytes(b"unfinished")
            (directory / "preview_00000002.jpg").write_bytes(b"second")
            request = Mock()
            request.app.state.capture_manager.directory.return_value = directory
            response = preview_frame("0" * 32, request)
            self.assertEqual(response.body, b"second")
            self.assertEqual(response.media_type, "image/jpeg")
            self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
            self.assertEqual(preview_frame("0" * 32, request, 1).body, b"first")

    def test_preview_metadata_matches_a_published_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "preview_00000001.jpg").write_bytes(b"first")
            (directory / "preview_00000001.json").write_text(
                json.dumps({"frame_index": 1, "right_action": {"label": "OPEN"}}),
                encoding="utf-8")
            (directory / "preview_00000002.json").write_text(
                json.dumps({"frame_index": 2}), encoding="utf-8")
            request = Mock()
            request.app.state.capture_manager.directory.return_value = directory
            response = preview_observation("0" * 32, request)
            self.assertEqual(json.loads(response.body)["frame_index"], 1)
            self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")

    def test_start_stop_and_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(environment="test", static_dir=root / "static")
            manager = CaptureManager(settings)
            process = Mock()
            process.poll.return_value = None
            with patch.object(manager, "_ai_python", return_value="python"), \
                    patch("backend.services.capture.subprocess.Popen", return_value=process) as launch:
                started = manager.start()
            self.assertEqual(launch.call_args.kwargs["env"]["PYTHONIOENCODING"], "utf-8")
            job_id = started["job_id"]
            directory = manager.directory(job_id)
            self.assertEqual(manager.status(job_id)["stage"], "starting")
            (directory / "status.json").write_text(json.dumps({
                "stage": "recording", "message": "Camera đang ghi", "session_id": None,
            }), encoding="utf-8")
            self.assertEqual(manager.stop(job_id)["stage"], "stopping")
            self.assertTrue((directory / "stop.flag").exists())
            with self.assertRaises(RuntimeError):
                manager.start()

    def test_rejects_unknown_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Settings(environment="test", static_dir=Path(temporary) / "static")
            manager = CaptureManager(settings)
            with self.assertRaises(FileNotFoundError):
                manager.status("0" * 32)

    def test_subprocess_finishes_after_dashboard_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root / "fake_capture.py"
            fake.write_text(
                "import json, pathlib, sys, time\n"
                "p = pathlib.Path(sys.argv[sys.argv.index('--job-dir') + 1])\n"
                "(p/'status.json').write_text(json.dumps({'stage':'recording','message':'on','session_id':None}))\n"
                "while not (p/'stop.flag').exists(): time.sleep(.02)\n"
                "(p/'status.json').write_text(json.dumps({'stage':'completed','message':'done','session_id':'DEMO_test'}))\n",
                encoding="utf-8",
            )
            manager = CaptureManager(Settings(environment="test", static_dir=root / "static"))
            with patch.object(manager, "_ai_python", return_value=sys.executable), \
                    patch("backend.services.capture.CAPTURE_SCRIPT", fake):
                job_id = manager.start()["job_id"]
            try:
                deadline = time.monotonic() + 5
                while manager.status(job_id)["stage"] == "starting" and time.monotonic() < deadline:
                    time.sleep(.03)
                self.assertEqual(manager.status(job_id)["stage"], "recording")
                manager.stop(job_id)
                while manager.status(job_id)["stage"] != "completed" and time.monotonic() < deadline:
                    time.sleep(.03)
                self.assertEqual(manager.status(job_id)["session_id"], "DEMO_test")
            finally:
                if manager._process and manager._process.poll() is None:
                    manager._process.terminate()
                if manager._process:
                    manager._process.wait(timeout=5)
