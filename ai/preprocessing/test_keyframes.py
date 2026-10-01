import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_recording import process_recording
from video_recording import RecordingVideo, sha256_file
from extract_keyframes import extract_keyframes
from test_camera_observation import fake_hand

HAS_VIDEO_LIBS = (importlib.util.find_spec("cv2") is not None
                  and importlib.util.find_spec("numpy") is not None)


@unittest.skipUnless(HAS_VIDEO_LIBS, "Real video round trip requires OpenCV and NumPy")
class KeyframeVideoTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np

        self.cv2, self.np = cv2, np
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "camera.jsonl"
        self.times = [0, 10, 20, 30, 40, 50, 500, 520, 540, 560]
        video = RecordingVideo(self.raw, cv2)
        with self.raw.open("x", encoding="utf-8") as stream:
            for index, timestamp in enumerate(self.times):
                image = np.full((48, 64, 3), 15 + index * 15, dtype=np.uint8)
                video_index = video.write(image)
                row = {
                    "schema_version": "smartwear.camera_raw.v2", "timestamp": timestamp,
                    "video_frame_index": video_index,
                    "camera": {"frame_width": 64, "frame_height": 48},
                    "hands": [{"hand_index": 0, "handedness": "Left",
                               "landmarks": fake_hand(closed=index >= 7),
                               "world_landmarks": []}],
                    "hand_actions": {
                        "left": {"label": "OPEN" if index < 7 else "GRAB",
                                 "hand_state": "OPEN" if index < 7 else "CLOSED",
                                 "source": "camera_landmarks", "tracking_status": "detected",
                                 "hand_index": 0},
                        "right": {"label": "NO_HAND", "hand_state": "NONE",
                                  "source": "camera_landmarks", "tracking_status": "missing",
                                  "hand_index": None}},
                }
                stream.write(json.dumps(row) + "\n")
        video.close()
        video.save_manifest()

    def test_real_video_to_png_uses_recorded_time_and_hand_segments(self):
        raw_bytes = self.raw.read_bytes()
        video_hash = sha256_file(self.raw.with_suffix(".avi"))
        combined = process_recording(self.raw, self.root / "sessions")
        session = combined.parent
        result = json.loads((session / "keyframes.json").read_text())
        self.assertEqual(result["status"], "completed")
        self.assertEqual((result["extracted_count"], result["skipped_count"]), (2, 1))
        left = [entry for entry in result["entries"] if entry["hand"] == "left"]
        self.assertEqual([e["frame_id"] for e in left], [5, 8])
        self.assertEqual([e["timestamp_ms"] for e in left], [50, 540])
        for entry in left:
            path = session / entry["image_path"]
            self.assertTrue(path.is_file())
            image = self.cv2.imread(str(path))
            self.assertEqual(image.shape[:2], (48, 64))
            expected = 15 + entry["frame_id"] * 15
            self.assertLess(abs(float(image[24, 32, 0]) - expected), 8)
        self.assertEqual([e["reason"] for e in result["entries"] if e["hand"] == "right"],
                         ["no_hand"])
        with self.assertRaises(FileExistsError):
            extract_keyframes(self.raw, combined, session / "action_segments.json",
                              session / "keyframes.json")
        self.assertEqual(self.raw.read_bytes(), raw_bytes)
        self.assertEqual(sha256_file(self.raw.with_suffix(".avi")), video_hash)
        # Tampering with the video metadata must fail before any PNG is published.
        manifest = self.raw.with_suffix(".video.json")
        meta = json.loads(manifest.read_text())
        meta["video_sha256"] = "bad"
        manifest.write_text(json.dumps(meta))
        destination = self.root / "bad.json"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            extract_keyframes(self.raw, session / "multimodal.jsonl",
                              session / "action_segments.json", destination)
        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_suffix("").exists())

    def test_missing_video_metadata_for_mapped_frames_is_error(self):
        combined = process_recording(self.raw, self.root / "sessions")
        self.raw.with_suffix(".video.json").unlink()
        output = self.root / "retry.json"
        with self.assertRaises(FileNotFoundError):
            extract_keyframes(self.raw, combined, combined.with_name("action_segments.json"), output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
