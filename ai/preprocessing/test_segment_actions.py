import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from segment_actions import segment_file, segment_frames


def make_frames(items):
    states = {"GRAB": "CLOSED", "ASSEMBLY": "CLOSED", "OTHER": "OTHER", "NO_HAND": "NONE"}
    return [{"schema_version": "smartwear.multimodal.v1", "frame_id": i,
             "timestamp_ms": time, "action_estimate": {
                 "label": label, "hand_state": states.get(label, "OPEN"),
                 "source": "camera_landmarks"}}
            for i, (time, label) in enumerate(items)]


class SegmentTests(unittest.TestCase):
    def test_boundaries_cover_all_frames_without_overlapping_durations(self):
        frames = make_frames([(303, "REACH"), (343, "REACH"), (403, "GRAB"),
                              (503, "GRAB"), (553, "RELEASE"), (603, "RELEASE")])
        segments = segment_frames(frames)
        self.assertEqual([(s["label"], s["start_ms"], s["end_ms"], s["duration_ms"])
                          for s in segments],
                         [("REACH", 303, 403, 100), ("GRAB", 403, 553, 150),
                          ("RELEASE", 553, 603, 50)])
        self.assertEqual([s["frame_count"] for s in segments], [2, 2, 2])
        self.assertEqual(segments[0]["last_observed_ms"], 343)
        self.assertFalse(segments[0]["end_is_observation_limit"])
        self.assertTrue(segments[-1]["end_is_observation_limit"])

    def test_short_unknown_and_no_hand_runs_are_kept(self):
        frames = make_frames([(0, "GRAB"), (40, "OTHER"), (80, "GRAB"), (120, "NO_HAND")])
        segments = segment_frames(frames)
        self.assertEqual([s["label"] for s in segments], ["GRAB", "OTHER", "GRAB", "NO_HAND"])
        self.assertEqual(segments[-1]["duration_ms"], 0)
        single = segment_frames(make_frames([(702, "OPEN")]))[0]
        self.assertEqual((single["frame_count"], single["start_ms"], single["duration_ms"]), (1, 702, 0))

    def test_large_gap_splits_even_same_label_without_counting_missing_time(self):
        segments = segment_frames(make_frames([(303, "GRAB"), (403, "GRAB"),
                                               (1500, "GRAB"), (1600, "GRAB")]))
        self.assertEqual(len(segments), 2)
        self.assertEqual([s["duration_ms"] for s in segments], [100, 100])
        self.assertEqual(segments[0]["end_reason"], "data_gap")
        self.assertEqual(len(segment_frames(make_frames([(0, "OPEN"), (500, "OPEN")]))), 1)

    def test_invalid_input_rejected(self):
        base = make_frames([(0, "OPEN"), (40, "GRAB")])
        variants = [[]]
        for key, value in (("timestamp_ms", 0), ("timestamp_ms", -1),
                           ("timestamp_ms", True), ("frame_id", 3),
                           ("schema_version", "unknown"), ("action_estimate", {})):
            rows = copy.deepcopy(base)
            rows[1][key] = value
            variants.append(rows)
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                segment_frames(rows)
        with self.assertRaises(ValueError):
            segment_frames(base, 0)

    def test_file_provenance_gaps_and_exclusive_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.jsonl", Path(directory) / "segments.json"
            frames = make_frames([(0, "OPEN"), (1000, "OPEN")])
            source.write_text("".join(json.dumps(r) + "\n" for r in frames))
            before = source.read_bytes()
            document = segment_file(source, output)
            self.assertEqual(document["source_sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(document["data_gaps"][0]["duration_ms"], 1000)
            self.assertFalse(document["uses_simulated_sensors"])
            saved = output.read_bytes()
            with self.assertRaises(FileExistsError):
                segment_file(source, output)
            self.assertEqual(output.read_bytes(), saved)
            self.assertEqual(source.read_bytes(), before)
            invalid = Path(directory) / "invalid.jsonl"
            invalid.write_text('{}\n')
            with self.assertRaises(ValueError):
                segment_file(invalid, Path(directory) / "bad.json")
            self.assertFalse((Path(directory) / "bad.json").exists())


if __name__ == "__main__":
    unittest.main()
