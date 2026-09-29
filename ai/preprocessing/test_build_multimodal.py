import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from build_multimodal import SENSOR_FIELDS, build_multimodal
from sensors.simulate_sensors import simulate_from_camera, write_sensor_records


class MultimodalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.camera = self.root / "camera.jsonl"
        self.sensor = self.root / "sensors.jsonl"
        self.meta = self.sensor.with_suffix(".meta.json")
        self.output = self.root / "combined.jsonl"
        self.frames = [{"frame_id": i, "timestamp_ms": t,
                        "relative_time_s": t / 1000,
                        "camera": {"frame_width": 640, "frame_height": 480},
                        "hands": [], "action_estimate": {
                            "label": "NO_HAND", "hand_state": "NONE",
                            "source": "camera_landmarks"}}
                       for i, t in enumerate((303, 353, 503))]
        self.write_rows(self.camera, self.frames)
        write_sensor_records(self.sensor, simulate_from_camera(self.frames))
        self.metadata = {
            "source": "simulated_from_camera_observations",
            "camera_sha256": hashlib.sha256(self.camera.read_bytes()).hexdigest(),
            "simulated_fields": list(SENSOR_FIELDS), "sample_count": 3,
            "first_timestamp_ms": 303, "last_timestamp_ms": 503}
        self.write_meta()

    def write_rows(self, path, rows):
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def write_meta(self):
        self.meta.write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_lossless_join_and_no_overwrite(self):
        original = {p: p.read_bytes() for p in (self.camera, self.sensor, self.meta)}
        self.assertEqual(build_multimodal(self.camera, self.sensor, self.output), 3)
        rows = [json.loads(line) for line in self.output.read_text().splitlines()]
        sensors = [json.loads(line) for line in self.sensor.read_text().splitlines()]
        for row, frame, sensor in zip(rows, self.frames, sensors):
            for field in frame:
                self.assertEqual(row[field], frame[field])
            for field in SENSOR_FIELDS:
                self.assertEqual(row[field], sensor[field])
            self.assertEqual(row["provenance"]["sensors"],
                             "simulated_from_camera_observations")
        before = self.output.read_bytes()
        with self.assertRaises(FileExistsError):
            build_multimodal(self.camera, self.sensor, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        for path, contents in original.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_wrong_session_rejected_even_with_same_timestamps(self):
        self.frames[1]["camera"]["frame_width"] = 1280
        self.write_rows(self.camera, self.frames)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            build_multimodal(self.camera, self.sensor, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_duplicate_shifted_and_nonfinite_sensor_data_rejected(self):
        original = [json.loads(line) for line in self.sensor.read_text().splitlines()]
        variants = [original[:-1]]
        for timestamp in (303, 354):
            altered = json.loads(json.dumps(original))
            altered[1]["timestamp_ms"] = timestamp
            variants.append(altered)
        altered = json.loads(json.dumps(original))
        altered[1]["force_emg_raw"] = float("nan")
        variants.append(altered)
        for rows in variants:
            with self.subTest(rows=rows):
                self.write_rows(self.sensor, rows)
                with self.assertRaises(ValueError):
                    build_multimodal(self.camera, self.sensor, self.output)
                self.assertFalse(self.output.exists())

    def test_missing_or_invalid_metadata_rejected(self):
        self.meta.unlink()
        with self.assertRaises(FileNotFoundError):
            build_multimodal(self.camera, self.sensor, self.output)
        for field, value in (("source", "hardware"), ("sample_count", 9),
                             ("simulated_fields", ["torque"])):
            previous = self.metadata[field]
            self.metadata[field] = value
            self.write_meta()
            with self.assertRaises(ValueError):
                build_multimodal(self.camera, self.sensor, self.output)
            self.metadata[field] = previous
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
