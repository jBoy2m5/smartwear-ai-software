import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camera_test
from analysis.compare_sessions import align_track, compare_sessions, keyframe_paths, sha256_file
from test_two_hands import frame_sequence, hand


class SessionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "sessions"
        self.root.mkdir()

    def make_recording(self, name, count, closed_after, missing_left=False, parent=None):
        session = (parent or self.root) / name
        session.mkdir()
        frames = frame_sequence([
            ([] if missing_left else [hand("left", index >= closed_after)])
            + [hand("right", False)] for index in range(count)])
        raw = session / "camera.jsonl"
        with raw.open("x", encoding="utf-8") as target:
            for frame in frames:
                target.write(json.dumps({
                    "schema_version": "smartwear.camera_raw.v2",
                    "timestamp": frame["timestamp_ms"], "camera": frame["camera"],
                    "hands": frame["hands"], "hand_actions": frame["hand_actions"],
                }) + "\n")
        return raw

    def test_record_expert_and_worker_then_compare_automatically(self):
        expert = self.make_recording("expert", 12, 5)
        worker = self.make_recording("worker", 16, 7)
        with patch.object(camera_test, "SESSION_ROOT", self.root):
            camera_test.finish_recording(expert, "expert")
            camera_test.finish_recording(worker, "worker", expert.parent)
        result_path = worker.parent / "analysis_result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(result["schema_version"], "smartwear.analysis_comparison.v1")
        self.assertFalse(result["uses_simulated_sensors"])
        self.assertEqual(result["hands"]["left"]["status"], "compared")
        self.assertEqual(result["hands"]["right"]["status"], "compared")
        self.assertTrue(result["hands"]["left"]["alignment"])
        self.assertEqual(json.loads((expert.parent / "session_role.json").read_text())["role"],
                         "expert")
        self.assertEqual(json.loads((worker.parent / "session_role.json").read_text())["role"],
                         "worker")
        self.assertEqual(result["expert_segments_sha256"],
                         sha256_file(expert.parent / "action_segments.json"))
        before = result_path.read_bytes()
        with self.assertRaises(FileExistsError):
            compare_sessions(expert.parent, worker.parent)
        self.assertEqual(result_path.read_bytes(), before)

    def test_dtw_exposes_longer_visible_action_and_label_change(self):
        expert = [{"segment_id": 1, "label": "GRAB", "duration_ms": 400},
                  {"segment_id": 2, "label": "RELEASE", "duration_ms": 300}]
        worker = [{"segment_id": 3, "label": "GRAB", "duration_ms": 1400},
                  {"segment_id": 4, "label": "OPEN", "duration_ms": 300}]
        result = align_track(expert, worker)
        reasons = {item["reason"] for item in result["review_candidates"]}
        self.assertEqual(reasons, {"longer_visible_action", "different_visible_label"})
        self.assertGreater(result["normalized_dtw_cost"], 0)
        self.assertEqual(align_track(expert, expert)["normalized_dtw_cost"], 0)

    def test_missing_or_ambiguous_hand_is_not_scored(self):
        expert = self.make_recording("expert", 5, 0, missing_left=True)
        worker = self.make_recording("worker", 5, 0, missing_left=True)
        with patch.object(camera_test, "SESSION_ROOT", self.root):
            camera_test.finish_recording(expert, "expert")
            camera_test.finish_recording(worker, "worker", expert.parent)
        doc = json.loads((worker.parent / "analysis_result.json").read_text())
        self.assertEqual(doc["hands"]["left"]["status"], "insufficient_visible_actions")
        self.assertGreater(doc["hands"]["left"]["expert_omitted"]["no_hand"], 0)
        self.assertGreater(doc["hands"]["left"]["expert_omitted"]["no_hand_duration_ms"], 0)
        self.assertEqual(doc["hands"]["right"]["status"], "compared")
        # The camera observations are the only inputs: no force or torque in the result.
        self.assertNotIn("force_emg_raw", json.dumps(doc))
        self.assertNotIn("torque", json.dumps(doc))
        self.assertEqual(align_track([], [])["status"], "insufficient_visible_actions")

    def test_rejects_wrong_role_and_changed_source(self):
        expert = self.make_recording("expert", 5, 0)
        worker = self.make_recording("worker", 5, 0)
        with patch.object(camera_test, "SESSION_ROOT", self.root):
            camera_test.finish_recording(expert, "expert")
            camera_test.finish_recording(worker, "worker", expert.parent)
        with self.assertRaisesRegex(ValueError, "role"):
            compare_sessions(worker.parent, expert.parent)
        (expert.parent / "multimodal.jsonl").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "segmentation"):
            compare_sessions(expert.parent, worker.parent)

    def test_only_existing_keyframes_from_matching_segments_are_linked(self):
        session = self.root / "images"
        (session / "keyframes").mkdir(parents=True)
        (session / "keyframes" / "grab.png").write_bytes(b"example")
        manifest = session / "keyframes.json"
        manifest.write_text(json.dumps({"segments_sha256": "abc", "entries": [
            {"segment_id": 4, "status": "extracted", "image_path": "keyframes/grab.png"},
            {"segment_id": 5, "status": "skipped", "image_path": None},
        ]}), encoding="utf-8")
        self.assertEqual(keyframe_paths(session, "abc"), {4: "keyframes/grab.png"})
        with self.assertRaisesRegex(ValueError, "different segmentation"):
            keyframe_paths(session, "wrong")

    def test_plain_camera_flow_selects_closest_bundled_reference(self):
        samples = self.root / "reference_samples"
        samples.mkdir()
        worker = self.make_recording("worker", 8, 0)
        for name, closed_after in (("open_sample", 100), ("grab_sample", 0)):
            reference = self.make_recording(name, 8, closed_after, parent=samples)
            with patch.object(camera_test, "SESSION_ROOT", samples):
                camera_test.finish_recording(reference, "expert")
            (reference.parent / "reference_sample.json").write_text(json.dumps({
                "schema_version": "smartwear.demo_reference.v1", "title": name,
                "practice_instruction": "test example", "demo_only": True,
            }), encoding="utf-8")
        with patch.object(camera_test, "SESSION_ROOT", self.root), \
                patch.object(camera_test, "REFERENCE_ROOT", samples):
            camera_test.finish_recording(worker)
        result = json.loads((worker.parent / "analysis_result.json").read_text())
        self.assertEqual(result["selected_reference"]["sample_id"], "grab_sample")
        self.assertTrue(result["selected_reference"]["demo_only"])
        self.assertEqual(json.loads((worker.parent / "session_role.json").read_text())["role"],
                         "worker")


if __name__ == "__main__":
    unittest.main()
