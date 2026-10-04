"""Regression checks for the optional full AI comparison attachment."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from backend.core.config import BACKEND_ROOT
from backend.services.analysis_detail import (
    get_expert_image,
    image_urls,
    load_analysis,
    parse_analysis,
    save_analysis,
    save_expert_image,
)


class AnalysisDetailTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=BACKEND_ROOT, prefix=".analysis_test_")
        self.addCleanup(self.workspace.cleanup)
        self.keyframes = Path(self.workspace.name) / "static" / "images"
        self.session_id = "DEMO_camera_data_test"
        self.document = {
            "schema_version": "smartwear.analysis_comparison.v2",
            "worker_session": "camera_data_test",
            "expert_session": "sample_01",
            "hands": {"left": {"alignment": [{
                "expert_segment_id": 5, "worker_segment_id": 19,
                "expert_label": "GRAB", "worker_label": "OPEN",
                "expert_duration_ms": 700, "worker_duration_ms": 359,
                "worker_extra_ms": -341,
                "expert_image_path": "keyframes/expert.png",
                "worker_image_path": "keyframes/worker.png",
            }]}, "right": {"alignment": []}},
            "muda_review": {"hands": {"left": {"candidates": []}}},
            "sensor_comparison": {"status": "simulated_demo_comparison"},
            "selected_reference": {"sample_id": "sample_01"},
        }

    def test_preserves_all_comparison_fields_and_expert_image(self):
        content = json.dumps(self.document).encode()
        save_analysis(self.keyframes, self.session_id, content)
        save_analysis(self.keyframes, self.session_id, content)  # safe retry
        self.assertEqual(load_analysis(self.keyframes, self.session_id), self.document)
        urls = image_urls(self.document, self.session_id, "/api/v1")
        self.assertIn("keyframes/expert.png", urls["expert"])
        self.assertIn("keyframes/worker.png", urls["worker"])
        picture = io.BytesIO()
        Image.new("RGB", (2, 2), "white").save(picture, format="PNG")
        save_expert_image(self.keyframes, self.session_id, "expert.png",
                          picture.getvalue(), 10_000)
        self.assertEqual(get_expert_image(self.keyframes, self.session_id,
                                          "expert.png").read_bytes(), picture.getvalue())

    def test_rejects_mismatched_session_and_unsafe_images(self):
        data = json.dumps(self.document).encode()
        with self.assertRaises(ValueError):
            parse_analysis(data, "DEMO_some_other_session")
        self.document["hands"]["left"]["alignment"][0]["expert_image_path"] = "../escape.png"
        with self.assertRaises(ValueError):
            parse_analysis(json.dumps(self.document).encode(), self.session_id)

    def test_measured_worker_analysis_uses_measured_session_id(self):
        self.document["sensor_comparison"] = {
            "status": "incompatible_sources_no_numeric_delta",
            "worker_source": {"source": "measured_hardware"}}
        from backend.services.analysis_detail import parse_analysis
        content = json.dumps(self.document).encode()
        parsed = parse_analysis(content, "MEASURED_camera_data_test")
        self.assertEqual(parsed["worker_session"], "camera_data_test")
        with self.assertRaises(ValueError):
            parse_analysis(content, "DEMO_camera_data_test")


if __name__ == "__main__":
    unittest.main()
