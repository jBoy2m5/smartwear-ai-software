import json
import sys
import tempfile
import unittest
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
from hand_observation import HandActionDetector  # noqa: E402
from normalize_camera import normalize_camera_data  # noqa: E402


def fake_hand(closed=False):
    points = [{"id": i, "x": 0.5, "y": 0.7, "z": 0} for i in range(21)]
    points[0].update(y=0.9)
    for x, (mcp, pip, tip) in zip((0.35, 0.45, 0.5, 0.65),
                                  ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))):
        points[mcp].update(x=x, y=0.5)
        points[pip].update(x=x, y=0.4)
        points[tip].update(x=x + (0.07 if closed else 0),
                           y=0.48 if closed else 0.2)
    return points


class CameraObservationTests(unittest.TestCase):
    def test_closing_and_opening_hand(self):
        detector = HandActionDetector()
        for ms in (0, 50, 100):
            label = detector.update(ms, fake_hand())
        self.assertEqual(label, "OPEN")
        for ms in (150, 200, 250):
            label = detector.update(ms, fake_hand(closed=True))
        self.assertEqual(label, "GRAB")
        for ms in (300, 350, 400):
            label = detector.update(ms, fake_hand())
        self.assertEqual(label, "RELEASE")
        self.assertEqual(detector.update(450, None), "NO_HAND")

    def test_legacy_raw_camera_gets_action_estimate_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw.jsonl"
            output = Path(directory) / "normalized.jsonl"
            frames = [
                {"timestamp": i * 50, "camera": {"frame_width": 640, "frame_height": 480},
                 "hands": [{"landmarks": fake_hand(closed=i >= 3)}]}
                for i in range(6)
            ]
            raw.write_text("".join(json.dumps(f) + "\n" for f in frames), encoding="utf-8")
            before = raw.read_bytes()
            self.assertEqual(normalize_camera_data(raw, output), 6)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[2]["action_estimate"]["hand_state"], "OPEN")
            self.assertEqual(rows[5]["action_estimate"]["label"], "GRAB")
            self.assertEqual(raw.read_bytes(), before)
            with self.assertRaises(FileExistsError):
                normalize_camera_data(raw, output)


if __name__ == "__main__":
    unittest.main()
