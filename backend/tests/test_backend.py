"""Contract and integration tests for the isolated backend module."""

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.core.config import BACKEND_ROOT, Settings
from backend.main import create_app
from backend.models import ActionPhase, RobotTrajectoryPoint
from backend.schemas import SessionInput
from backend.services.robot_export import RobotDatasetExporter


def sample_payload(session_id: str = "CYCLE_DENSO_001") -> dict[str, object]:
    """Return a fresh backend test fixture matching the immutable contract."""
    return {
        "session_id": session_id,
        "worker_type": "EXPERT",
        "key_frames": ["frame_assemble_01.jpg", "frame_assemble_02.jpg"],
        "action_phases": [
            {"phase": "REACH", "start_time": 0.0, "end_time": 1.8},
            {
                "phase": "ASSEMBLY",
                "start_time": 1.8,
                "end_time": 4.2,
                "peak_force_N": 5.4,
            },
        ],
        "dtw_metrics": {"similarity_score": 91.5, "muda_detected_seconds": 0.8},
        "robot_trajectory_points": [
            {"t": 0.1, "pos": [0.12, 0.45, 0.88], "force": 0.0},
            {"t": 2.0, "pos": [0.15, 0.48, 0.70], "force": 5.4},
        ],
    }


class SchemaTests(unittest.TestCase):
    """Validate the immutable AI-to-backend boundary."""

    def test_contract_round_trip(self) -> None:
        payload = sample_payload()
        validated = SessionInput.model_validate(payload)
        self.assertEqual(validated.model_dump(mode="json", exclude_none=True), payload)

    def test_rejects_unknown_fields(self) -> None:
        payload = sample_payload()
        payload["unexpected"] = True
        with self.assertRaises(ValidationError):
            SessionInput.model_validate(payload)

    def test_rejects_unsafe_identifiers_and_keyframes(self) -> None:
        payload = sample_payload("../escape")
        payload["key_frames"] = ["../frame.jpg"]
        with self.assertRaises(ValidationError):
            SessionInput.model_validate(payload)

    def test_rejects_unordered_trajectory(self) -> None:
        payload = sample_payload()
        payload["robot_trajectory_points"] = list(
            reversed(payload["robot_trajectory_points"])  # type: ignore[arg-type]
        )
        with self.assertRaises(ValidationError):
            SessionInput.model_validate(payload)

    def test_production_requires_api_key(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(environment="production", api_key=None)


class BackendIntegrationTests(unittest.TestCase):
    """Exercise HTTP, persistence, artifact, and WebSocket workflows."""

    def setUp(self) -> None:
        self.test_root = Path(tempfile.mkdtemp(dir=BACKEND_ROOT, prefix=".test_"))
        self.settings = Settings(
            environment="test",
            database_url=f"sqlite:///{(self.test_root / 'smartwear.db').as_posix()}",
            static_dir=self.test_root / "static",
            pdf_dir=self.test_root / "static" / "pdf",
            keyframe_dir=self.test_root / "static" / "images",
            dataset_dir=self.test_root / "static" / "dataset",
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        shutil.rmtree(self.test_root, ignore_errors=True)

    def ingest(self, session_id: str = "CYCLE_DENSO_001"):
        """Ingest one test fixture and assert success."""
        response = self.client.post("/api/v1/sessions/ingest", json=sample_payload(session_id))
        self.assertEqual(response.status_code, 201, response.text)
        return response

    def test_health_and_readiness(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/ready").json(), {"status": "ready"})

    def test_ingest_is_idempotent_and_normalized(self) -> None:
        first = self.ingest()
        second = self.client.post("/api/v1/sessions/ingest", json=sample_payload())
        self.assertTrue(first.json()["created"])
        self.assertEqual(first.json()["export_status"], "COMPLETED")
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])

        database = self.app.state.database
        with database.transaction() as db_session:
            phases = db_session.scalar(select(func.count()).select_from(ActionPhase))
            points = db_session.scalar(select(func.count()).select_from(RobotTrajectoryPoint))
        self.assertEqual(phases, 2)
        self.assertEqual(points, 2)

    def test_list_detail_and_dashboard(self) -> None:
        self.ingest()
        listing = self.client.get("/api/v1/sessions/?limit=10&offset=0")
        detail = self.client.get("/api/v1/sessions/CYCLE_DENSO_001")
        dashboard = self.client.get("/api/v1/sessions/dashboard/summary")
        self.assertEqual(listing.json()["total"], 1)
        self.assertEqual(detail.json()["dtw_metrics"]["similarity_score"], 91.5)
        self.assertEqual(dashboard.json()["expert_sessions"], 1)

    def test_sop_and_robot_outputs_are_downloadable(self) -> None:
        self.ingest()
        sop = self.client.get("/api/v1/sessions/CYCLE_DENSO_001/download-sop")
        robot_json = self.client.get(
            "/api/v1/sessions/CYCLE_DENSO_001/export-rosbag?format=json"
        )
        db3 = self.client.get("/api/v1/sessions/CYCLE_DENSO_001/export-rosbag?format=db3")
        archive = self.client.get(
            "/api/v1/sessions/CYCLE_DENSO_001/export-rosbag?format=rosbag"
        )
        self.assertTrue(sop.content.startswith(b"%PDF"))
        self.assertEqual(len(robot_json.json()["topics"]), 2)
        self.assertTrue(db3.content.startswith(b"SQLite format 3"))
        with zipfile.ZipFile(io.BytesIO(archive.content)) as rosbag:
            self.assertTrue(any(name.endswith("metadata.yaml") for name in rosbag.namelist()))

    def test_keyframe_upload_and_download(self) -> None:
        self.ingest()
        image_buffer = io.BytesIO()
        Image.new("RGB", (4, 4), color="white").save(image_buffer, format="JPEG")
        upload = self.client.put(
            "/api/v1/sessions/CYCLE_DENSO_001/keyframes/frame_assemble_01.jpg",
            content=image_buffer.getvalue(),
            headers={"Content-Type": "image/jpeg"},
        )
        download = self.client.get(
            "/api/v1/sessions/CYCLE_DENSO_001/keyframes/frame_assemble_01.jpg"
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        self.assertEqual(download.content, image_buffer.getvalue())

    def test_not_found_and_cors_errors(self) -> None:
        self.assertEqual(self.client.get("/api/v1/sessions/MISSING").status_code, 404)
        cors = self.client.options(
            "/api/v1/sessions/ingest",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(cors.status_code, 400)

    def test_api_key_is_enforced(self) -> None:
        protected_settings = self.settings.model_copy(update={"api_key": "test-secret"})
        protected_client = TestClient(create_app(protected_settings))
        with protected_client:
            denied = protected_client.get("/api/v1/sessions/")
            allowed = protected_client.get(
                "/api/v1/sessions/",
                headers={"X-API-Key": "test-secret"},
            )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)

    def test_failed_export_is_visible_and_recoverable(self) -> None:
        class FailingExporter:
            def export(self, _: SessionInput) -> object:
                raise RuntimeError("simulated export failure")

        service = self.app.state.session_service
        service.robot_exporter = FailingExporter()
        failed = self.client.post("/api/v1/sessions/ingest", json=sample_payload())
        detail = self.client.get("/api/v1/sessions/CYCLE_DENSO_001")
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(detail.json()["export_status"], "FAILED")

        service.robot_exporter = RobotDatasetExporter(self.settings.dataset_dir)
        recovered = self.client.post("/api/v1/sessions/ingest", json=sample_payload())
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["export_status"], "COMPLETED")

    def test_websocket_simulation_and_validation(self) -> None:
        with self.client.websocket_connect("/ws/live-stream?simulate=true") as websocket:
            self.assertEqual(websocket.receive_json()["event"], "TELEMETRY_UPDATE")

        with self.client.websocket_connect("/ws/live-stream") as websocket:
            websocket.send_json({"invalid": True})
            self.assertEqual(websocket.receive_json()["event"], "VALIDATION_ERROR")
            message = {
                "timestamp": 1.0,
                "current_phase": "REACH",
                "realtime_force_N": 0.0,
                "pinch_distance_mm": 12.4,
                "muda_alert": False,
                "message": "Within expected range",
            }
            websocket.send_json(message)
            self.assertEqual(websocket.receive_json()["current_phase"], "REACH")


if __name__ == "__main__":
    unittest.main()
