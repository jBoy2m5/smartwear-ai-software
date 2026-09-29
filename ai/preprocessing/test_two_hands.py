import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_test import make_frame_data, draw_frame
from hand_observation import TwoHandActionDetector, SIDES
from normalize_camera import normalize_camera_data
from process_recording import process_recording
from sensors.simulate_sensors import simulate_from_camera, validate_record
from build_multimodal import build_multimodal
from segment_actions import segment_frames
from test_camera_observation import fake_hand
import camera_test


def hand(side, closed=False, offset=0):
    points = fake_hand(closed)
    for p in points:
        p["x"] += offset
    return {"hand_index": 0, "handedness": side.title(), "landmarks": points,
            "world_landmarks": []}


def frame_sequence(hand_lists):
    detector = TwoHandActionDetector()
    frames = []
    for index, source_hands in enumerate(hand_lists):
        hands = copy.deepcopy(source_hands)
        for i, h in enumerate(hands):
            h["hand_index"] = i
        timestamp = 303 + index * 100
        frames.append({"schema_version": "smartwear.camera.v2", "frame_id": index,
                       "timestamp_ms": timestamp, "relative_time_s": timestamp / 1000,
                       "camera": {"frame_width": 640, "frame_height": 480}, "hands": hands,
                       "hand_actions": detector.update(timestamp, hands),
                       "action_origin": "recorded_per_hand"})
    return frames


class TwoHandTests(unittest.TestCase):
    def test_camera_q_closes_device_and_saves_two_hands_without_real_webcam(self):
        hands = [hand("left", True), hand("right", False)]
        result = SimpleNamespace(
            hand_landmarks=[[SimpleNamespace(**{k: p[k] for k in ("x", "y", "z")})
                             for p in h["landmarks"]] for h in hands],
            handedness=[[SimpleNamespace(category_name=h["handedness"], score=0.99)] for h in hands],
            hand_world_landmarks=[[], []])
        events = []
        frame = SimpleNamespace(shape=(480, 640, 3))
        device = SimpleNamespace(isOpened=lambda: True, read=lambda: (True, frame),
                                 release=lambda: events.append("released"))
        keys = iter((0, 0, ord("q")))
        cv = SimpleNamespace(VideoCapture=lambda index: device, flip=lambda f, axis: f,
                             cvtColor=lambda f, mode: f, COLOR_BGR2RGB=1,
                             FONT_HERSHEY_SIMPLEX=0, circle=lambda *args: None,
                             putText=lambda *args: None, imshow=lambda *args: None,
                             waitKey=lambda ms: next(keys), destroyAllWindows=lambda: events.append("closed"))

        class Landmarker:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                events.append("landmarker_closed")

            def detect_for_video(self, image, timestamp):
                return result

        mp = SimpleNamespace(
            Image=lambda **kwargs: kwargs, ImageFormat=SimpleNamespace(SRGB=1),
            tasks=SimpleNamespace(BaseOptions=lambda **kwargs: kwargs,
                vision=SimpleNamespace(HandLandmarkerOptions=lambda **kwargs: kwargs,
                    RunningMode=SimpleNamespace(VIDEO=1),
                    HandLandmarker=SimpleNamespace(create_from_options=lambda options: Landmarker()))))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model.task"
            model.write_text("test double")
            with patch.dict(sys.modules, {"cv2": cv, "mediapipe": mp}), \
                    patch.object(camera_test, "SCRIPT_DIR", root), \
                    patch.object(camera_test, "MODEL_PATH", model):
                output = camera_test.record_camera()
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[-1]["hand_actions"]["left"]["label"], "GRAB")
            self.assertEqual(rows[-1]["hand_actions"]["right"]["label"], "OPEN")
            self.assertEqual(events, ["landmarker_closed", "released", "closed"])

    def test_opposite_actions_and_order_changes_keep_identity(self):
        left, right = hand("left", True, -0.2), hand("right", False, 0.2)
        stable = frame_sequence([[left, right] for _ in range(12)])
        swapped = frame_sequence([[left, right] if i % 2 else [right, left] for i in range(12)])
        self.assertEqual(stable[2]["hand_actions"]["left"]["label"], "GRAB")
        self.assertEqual(stable[2]["hand_actions"]["right"]["label"], "OPEN")
        for a, b in zip(stable, swapped):
            for side in SIDES:
                self.assertEqual(a["hand_actions"][side]["label"], b["hand_actions"][side]["label"])
        self.assertEqual(list(simulate_from_camera(stable)), list(simulate_from_camera(swapped)))

    def test_crossing_screen_positions_does_not_define_handedness(self):
        frames = frame_sequence([[hand("left", True, -0.2 + i * 0.04),
                                  hand("right", False, 0.2 - i * 0.04)] for i in range(12)])
        for frame in frames[2:]:
            self.assertEqual(frame["hand_actions"]["left"]["hand_state"], "CLOSED")
            self.assertEqual(frame["hand_actions"]["right"]["hand_state"], "OPEN")

    def test_missing_hand_resets_only_its_own_history_and_sensor_values(self):
        left, right = hand("left", True), hand("right", False)
        frames = frame_sequence([[left, right]] * 12 + [[right]] * 2 + [[left, right]] * 3)
        sensors = list(simulate_from_camera(frames, noise_level=0))
        self.assertEqual(frames[11]["hand_actions"]["left"]["label"], "ASSEMBLY")
        self.assertEqual(frames[12]["hand_actions"]["left"]["label"], "NO_HAND")
        self.assertIsNone(sensors[12]["hand_sensors"]["left"]["force_emg_raw"])
        self.assertEqual(frames[14]["hand_actions"]["left"]["label"], "OTHER")
        self.assertEqual(frames[16]["hand_actions"]["left"]["label"], "GRAB")
        self.assertEqual(sensors[14]["hand_sensors"]["left"]["force_emg_raw"], 100)
        for frame in frames[2:]:
            self.assertEqual(frame["hand_actions"]["right"]["label"], "OPEN")

    def test_one_hand_cannot_change_other_hand_simulation_or_head(self):
        right = hand("right", False, 0.2)
        first = frame_sequence([[hand("left", True, -0.2), right] for _ in range(12)])
        second = frame_sequence([[right] for _ in range(12)])
        a, b = list(simulate_from_camera(first)), list(simulate_from_camera(second))
        self.assertGreater(a[8]["hand_sensors"]["left"]["force_emg_raw"],
                           a[8]["hand_sensors"]["right"]["force_emg_raw"])
        for x, y in zip(a, b):
            self.assertEqual(x["hand_sensors"]["right"], y["hand_sensors"]["right"])
            self.assertEqual(x["imu_head"], y["imu_head"])
        self.assertEqual(a, list(simulate_from_camera(first)))

    def test_ambiguous_handedness_is_not_arbitrarily_assigned(self):
        for hands in ([hand("left"), hand("left", True)], [hand("unknown")]):
            frames = frame_sequence([hands] * 3)
            sensors = list(simulate_from_camera(frames))
            for side in SIDES:
                self.assertEqual(frames[-1]["hand_actions"][side]["tracking_status"], "ambiguous")
                self.assertEqual(frames[-1]["hand_actions"][side]["label"], "OTHER")
                self.assertIsNone(sensors[-1]["hand_sensors"][side]["imu_wrist"])

    def test_invalid_landmarks_and_timestamp_gap_do_not_keep_old_action(self):
        left, right = hand("left", True), hand("right", False)
        detector = TwoHandActionDetector()
        right["hand_index"] = 1
        for t in (0, 100, 200):
            actions = detector.update(t, [left, right])
        self.assertEqual(actions["left"]["label"], "GRAB")
        actions = detector.update(1200, [left, right])
        self.assertEqual(actions["left"]["label"], "OTHER")
        left["landmarks"][0]["x"] = float("nan")
        actions = detector.update(1300, [left, right])
        self.assertEqual(actions["left"]["tracking_status"], "ambiguous")
        self.assertEqual(actions["right"]["tracking_status"], "detected")
        with self.assertRaises(ValueError):
            detector.update(1300, [right])

    def test_sensor_validation_rejects_fabricated_values_for_missing_hand(self):
        sample = list(simulate_from_camera(frame_sequence([[]])))[0]
        sample["hand_sensors"]["left"]["force_emg_raw"] = 100
        with self.assertRaises(ValueError):
            validate_record(sample)

    def test_two_hand_segmentation_preserves_gaps_and_unknown_intervals(self):
        frames = frame_sequence([[hand("left"), hand("right")]] * 4 + [[]] +
                                [[hand("unknown")]] + [[hand("left"), hand("right")]] * 3)
        for i, frame in enumerate(frames):
            frame["schema_version"] = "smartwear.multimodal.v2"
            if i >= 3:
                frame["timestamp_ms"] += 1000
        segments = segment_frames(frames)
        for side in SIDES:
            track = [s for s in segments if s["hand"] == side]
            self.assertIn("data_gap", [s["end_reason"] for s in track])
            self.assertIn("missing", [s["tracking_status"] for s in track])
            self.assertIn("ambiguous", [s["tracking_status"] for s in track])
            self.assertEqual(sum(s["duration_ms"] for s in track) + 1100,
                             frames[-1]["timestamp_ms"] - frames[0]["timestamp_ms"])
            ids = [i for s in track for i in range(s["start_frame_id"], s["end_frame_id"] + 1)]
            self.assertEqual(ids, list(range(len(frames))))

    def test_live_conversion_overlay_and_full_pipeline_both_hands(self):
        detector = TwoHandActionDetector()
        raw_frames = []
        for index in range(24):
            hands = [hand("left", index < 16, -0.2), hand("right", index >= 12, 0.2)]
            if index in (10, 11):
                hands = hands[1:]
            if index % 2:
                hands.reverse()
            result = SimpleNamespace(
                hand_landmarks=[[SimpleNamespace(**{k: p[k] for k in ("x", "y", "z")})
                                 for p in h["landmarks"]] for h in hands],
                handedness=[[SimpleNamespace(category_name=h["handedness"], score=0.99)] for h in hands],
                hand_world_landmarks=[[] for _ in hands])
            raw_frames.append(make_frame_data(result, 303 + index * 100, 640, 480, detector))
        # Exercise the actual overlay routine without accessing a webcam.
        texts = []
        cv = SimpleNamespace(FONT_HERSHEY_SIMPLEX=0, circle=lambda *a: None,
                             putText=lambda image, text, *a: texts.append(text))
        draw_frame(cv, SimpleNamespace(shape=(480, 640, 3)), raw_frames[3])
        self.assertIn("LEFT: GRAB", texts)
        self.assertIn("RIGHT: OPEN", texts)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "two hands.jsonl"
            raw.write_text("".join(json.dumps(f) + "\n" for f in raw_frames), encoding="utf-8")
            original = raw.read_bytes()
            combined = process_recording(raw, root / "sessions")
            rows = [json.loads(line) for line in combined.read_text().splitlines()]
            self.assertEqual(len(rows), 24)
            for row, camera in zip(rows, raw_frames):
                self.assertEqual(row["schema_version"], "smartwear.multimodal.v2")
                self.assertEqual(row["hand_actions"], camera["hand_actions"])
                self.assertEqual(row["hands"], camera["hands"])
                self.assertEqual(row["timestamp_ms"], camera["timestamp"])
            doc = json.loads(combined.with_name("action_segments.json").read_text())
            self.assertEqual(doc["schema_version"], "smartwear.action_segments.v2")
            for side in SIDES:
                segments = [s for s in doc["segments"] if s["hand"] == side]
                covered = [i for s in segments for i in range(s["start_frame_id"], s["end_frame_id"] + 1)]
                self.assertEqual(covered, list(range(24)))
                self.assertEqual(sum(s["duration_ms"] for s in segments), 2300)
                for s in segments:
                    self.assertTrue(all(rows[i]["hand_actions"][side]["label"] == s["label"]
                                        for i in range(s["start_frame_id"], s["end_frame_id"] + 1)))
            self.assertEqual(raw.read_bytes(), original)
            # A wrong v2 side/status must be rejected even with matching timestamps.
            sensor_path = combined.with_name("sensors.jsonl")
            sensors = [json.loads(line) for line in sensor_path.read_text().splitlines()]
            sensors[0]["hand_sensors"]["left"] = {
                "tracking_status": "missing", "imu_wrist": None, "force_emg_raw": None, "torque": None}
            sensor_path.write_text("".join(json.dumps(s) + "\n" for s in sensors))
            meta_path = sensor_path.with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text())
            meta.pop("sensors_sha256")  # Allow association validation to be exercised.
            meta_path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, "hand status mismatch"):
                build_multimodal(combined.with_name("camera.normalized.jsonl"), sensor_path, root / "bad.jsonl")

    def test_legacy_global_label_not_copied_to_both_hands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = frame_sequence([[hand("left", True), hand("right", False)]] * 4)
            raw = root / "old.jsonl"
            old = [{"timestamp": f["timestamp_ms"], "camera": f["camera"], "hands": f["hands"],
                    "action_estimate": {"label": "ASSEMBLY", "hand_state": "CLOSED", "source": "camera_landmarks"}}
                   for f in frames]
            raw.write_text("".join(json.dumps(f) + "\n" for f in old))
            output = root / "new.jsonl"
            normalize_camera_data(raw, output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(rows[-1]["hand_actions"]["left"]["label"], "GRAB")
            self.assertEqual(rows[-1]["hand_actions"]["right"]["label"], "OPEN")
            self.assertNotIn("action_estimate", rows[-1])


if __name__ == "__main__":
    unittest.main()
