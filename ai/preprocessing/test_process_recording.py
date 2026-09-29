import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_recording import process_recording


class RecordingPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "camera session.jsonl"
        self.outputs = self.root / "sessions"
        self.frames = [
            {"timestamp": t, "camera": {"frame_width": 640, "frame_height": 480},
             "hands": [], "action_estimate": {
                 "label": "NO_HAND", "hand_state": "NONE", "source": "camera_landmarks"}}
            for t in (303, 403, 703)]
        self.raw.write_text("".join(json.dumps(r) + "\n" for r in self.frames), encoding="utf-8")

    def test_full_pipeline_and_repeat_preserve_inputs_and_previous_outputs(self):
        original = self.raw.read_bytes()
        first = process_recording(self.raw, self.outputs)
        before = {p: p.read_bytes() for p in first.parent.iterdir()}
        second = process_recording(self.raw, self.outputs)
        self.assertNotEqual(first, second)
        rows = [json.loads(line) for line in second.read_text().splitlines()]
        self.assertEqual([r["timestamp_ms"] for r in rows], [303, 403, 703])
        self.assertEqual(len(rows), 3)
        self.assertTrue(second.with_name("sensors.meta.json").exists())
        for row, frame in zip(rows, self.frames):
            self.assertEqual(row["action_estimate"], frame["action_estimate"])
            self.assertEqual(row["provenance"]["sensors"], "simulated_from_camera_observations")
        self.assertEqual(self.raw.read_bytes(), original)
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_empty_and_missing_recordings_do_not_start_processing(self):
        self.raw.write_text("\n ", encoding="utf-8")
        with self.assertRaises(ValueError):
            process_recording(self.raw, self.outputs)
        self.assertFalse(self.outputs.exists())
        self.raw.unlink()
        with self.assertRaises(FileNotFoundError):
            process_recording(self.raw, self.outputs)

    def test_failed_stage_stops_pipeline_and_preserves_raw(self):
        self.raw.write_text('{"timestamp": 303}\n', encoding="utf-8")
        before = self.raw.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Chuan hoa camera"):
            process_recording(self.raw, self.outputs)
        self.assertFalse(list(self.outputs.rglob("sensors.jsonl")))
        self.assertFalse(list(self.outputs.rglob("multimodal.jsonl")))
        self.assertEqual(self.raw.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
