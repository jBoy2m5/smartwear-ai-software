"""Camera-free regression checks for real-input parsing and no-DEMO alignment."""

import io
import json
import math
import sys
import tempfile
import unittest
import urllib.error
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent))

from hand_observation import TwoHandActionDetector  # noqa: E402
from analysis.compare_sensors import load_sensor_stream  # noqa: E402
from hardware.align import align_session  # noqa: E402
from hardware.camera_receiver import CameraReceiver  # noqa: E402
from hardware.mjpeg import read_parts  # noqa: E402
from hardware.mqtt_wrist import WristReceiver, validate_wrist_payload  # noqa: E402
from integration.backend_bridge import build_payload  # noqa: E402
from process_recording import process_recording  # noqa: E402
from backend.schemas.session import SessionInput  # noqa: E402


BASE = 1_790_000_000_000


class SplitReads(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3) if size >= 0 else 3)


class HardwareTests(unittest.TestCase):
    def test_mjpeg_split_jpeg_case_insensitive_headers_and_multiple_parts(self):
        jpeg = b"\xff\xd8some-jpeg\xff\xd9"
        part = (b"--frame\r\nX-FRAME-SEQ: {seq}\r\nContent-Length: {length}\r\n"
                b"x-timestamp-ms: {epoch}\r\nContent-Type: image/jpeg\r\n\r\n")
        stream = b"".join(part.replace(b"{seq}", str(i).encode())
                          .replace(b"{length}", str(len(jpeg)).encode())
                          .replace(b"{epoch}", str(BASE + i * 33).encode()) + jpeg + b"\r\n"
                          for i in range(2)) + b"--frame--\r\n"
        frames = list(read_parts(SplitReads(stream),
                                 'multipart/x-mixed-replace; boundary="frame"'))
        self.assertEqual([frame.sequence for frame in frames], [0, 1])
        self.assertEqual([frame.jpeg for frame in frames], [jpeg, jpeg])
        bad = stream.replace(b"Content-Length: 13", b"Content-Length: 99999999", 1)
        with self.assertRaises(ValueError):
            list(read_parts(SplitReads(bad), "multipart/x-mixed-replace; boundary=frame"))

    def test_camera_waits_for_http_503_then_saves_original_jpeg(self):
        jpeg = b"\xff\xd8jpeg\xff\xd9"
        body = (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 8\r\n"
                + f"X-Timestamp-Ms: {BASE}\r\nX-Frame-Seq: 0\r\n\r\n".encode()
                + jpeg + b"\r\n--frame--\r\n")
        attempts = 0

        def open_stream(_url):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise urllib.error.HTTPError("http://camera", 503, "waiting for NTP", {}, None)
            if attempts == 2:
                response = io.BytesIO(body)
                response.headers = {"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
                return response
            raise urllib.error.URLError("stream ended")

        with tempfile.TemporaryDirectory() as temporary, patch(
                "hardware.camera_receiver.open_camera_stream", side_effect=open_stream):
            receiver = CameraReceiver(Path(temporary), "http://camera")
            receiver.start()
            packet, _ = receiver.get(timeout=3)
            receiver.stop()
            self.assertEqual(packet.jpeg, jpeg)
            self.assertEqual((Path(temporary) / "camera_raw.mjpeg").read_bytes(), jpeg)
            self.assertEqual(receiver.snapshot()["http_503"], 1)

    def test_wrist_validation_rejects_malformed_and_nonfinite(self):
        valid = {"t_ms": BASE, "seq": 1, "acc": [0, 0, 1],
                 "gyro": [0, 0, 0], "force": [1, 2, 3, 4]}
        self.assertEqual(validate_wrist_payload(json.dumps(valid).encode())["force"],
                         [1, 2, 3, 4])
        for wrong in ({**valid, "force": [1, 2, 3]},
                      {**valid, "acc": [math.nan, 0, 1]},
                      {**valid, "t_ms": 0},
                      {**valid, "force": [1, 2, 3, 4096]}):
            with self.assertRaises(ValueError):
                validate_wrist_payload(json.dumps(wrong))

    def test_wrist_sequence_gap_and_reset_are_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wrist_raw.jsonl"
            receiver = WristReceiver(path, "127.0.0.1")
            for seq, epoch in ((1, BASE), (3, BASE + 20), (0, BASE + 40)):
                receiver.pending.put({"t_ms": epoch, "seq": seq,
                                      "acc": [0, 0, 1], "gyro": [0, 0, 0],
                                      "force": [1, 2, 3, 4],
                                      "received_epoch_ms": epoch + 5})
            receiver.finished.set()
            receiver._write_loop()
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["generation"] for row in rows], [0, 0, 1])
            self.assertEqual(receiver.snapshot()["seq_gaps"], 1)
            self.assertEqual(receiver.snapshot()["resets"], 1)

    def test_mqtt_raw_payload_topic_and_receipt_time_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wrist_raw.jsonl"
            receiver = WristReceiver(path, "127.0.0.1")
            payload = b'{"t_ms":1790000000000,"seq":7,"acc":[0,0,1],"gyro":[0,0,0],"force":[1,2,3,4]}'
            receiver._on_message(None, None, SimpleNamespace(
                topic=receiver.topic, payload=payload))
            receiver.finished.set()
            receiver._write_loop()
            row = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(row["raw_payload"], payload.decode())
            self.assertEqual(row["topic"], receiver.topic)
            self.assertIsInstance(row["received_epoch_ms"], int)
            self.assertEqual(row["generation"], 0)

    def write_inputs(self, session, missing=False, reset=False, force_channel=0):
        detector = TwoHandActionDetector()
        points = [{"id": i, "x": 0.5, "y": 0.5, "z": 0.0} for i in range(21)]
        with (session / "camera.jsonl").open("w", encoding="utf-8") as stream:
            for index in range(20):
                hands = [{"hand_index": 0, "handedness": "Right",
                          "landmarks": points, "world_landmarks": points}]
                row = {"schema_version": "smartwear.camera_raw.v2",
                       "timestamp": index * 40,
                       "camera": {"frame_width": 320, "frame_height": 240},
                       "hands": hands, "hand_actions": detector.update(index * 40, hands),
                       "source_epoch_ms": BASE + index * 40,
                       "source_frame_seq": index,
                       "received_epoch_ms": BASE + index * 40 + 10}
                stream.write(json.dumps(row) + "\n")
        with (session / "wrist_raw.jsonl").open("w", encoding="utf-8") as stream:
            for index in range(40):
                item = {"t_ms": BASE + index * 20 + (5000 if missing else 5),
                        "seq": index, "generation": 1 if reset and index >= 20 else 0,
                        "received_epoch_ms": BASE + index * 20 + 12,
                        "acc": [0.1, 0.2, 1], "gyro": [0, 0, 0],
                        "force": [100 + index, 200, 300, 400]}
                stream.write(json.dumps(item) + "\n")
        (session / "hardware_capture.json").write_text(json.dumps({
            "schema_version": "smartwear.hardware_capture.v1", "status": "complete",
            "alignment_window_ms": 40, "force_channel": force_channel,
            "device_id": "testwrist"}), encoding="utf-8")

    def test_complete_measured_pipeline_has_no_fake_force_or_robot_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / "session"
            session.mkdir()
            self.write_inputs(session)
            process_recording(session / "camera.jsonl", root, session)
            rows = [json.loads(line) for line in (session / "multimodal.jsonl").read_text(
                encoding="utf-8").splitlines()]
            self.assertTrue(all(row["provenance"]["sensors"] == "measured_hardware"
                                and row["imu_head"] is None
                                and row["hand_sensors"]["right"]["torque"] is None
                                for row in rows))
            self.assertFalse((session / "sensors.jsonl").exists())
            segments = session / "action_segments.json"
            (session / "session_role.json").write_text(json.dumps({
                "schema_version": "smartwear.session_role.v1", "role": "expert",
                "segments_sha256": sha256(segments.read_bytes()).hexdigest()}),
                encoding="utf-8")
            payload, meta, _ = build_payload(session)
            SessionInput.model_validate(payload)
            self.assertTrue(payload["session_id"].startswith("MEASURED_"))
            self.assertEqual(payload["robot_trajectory_points"], [])
            self.assertTrue(all(item["peak_force_N"] is None
                                for item in payload["action_phases"]))
            self.assertEqual(meta["sensor_source"], "measured_hardware")

    def test_missing_or_reset_wrist_never_falls_back_to_simulator(self):
        for missing, reset in ((True, False), (False, True)):
            with self.subTest(missing=missing, reset=reset), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                session = root / "session"
                session.mkdir()
                self.write_inputs(session, missing=missing, reset=reset)
                with self.assertRaises(RuntimeError):
                    process_recording(session / "camera.jsonl", root, session)
                self.assertFalse((session / "sensors.jsonl").exists())

    def test_unmapped_four_adc_channels_remain_visible_without_inventing_scalar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / "session"
            session.mkdir()
            self.write_inputs(session, force_channel=None)
            process_recording(session / "camera.jsonl", root, session)
            rows = [json.loads(line) for line in (session / "real_sensors.jsonl").read_text(
                encoding="utf-8").splitlines()]
            self.assertTrue(all(row["hand_sensors"]["right"]["force_emg_raw"] is None
                                and len(row["hand_sensors"]["right"]["force_adc"]) == 4
                                for row in rows))
            self.assertTrue(all(row["hand_sensors"]["left"]["force_adc"] is None
                                for row in rows))

    def test_measured_sensor_hash_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / "session"
            session.mkdir()
            self.write_inputs(session)
            process_recording(session / "camera.jsonl", root, session)
            path = session / "real_sensors.jsonl"
            with path.open("a", encoding="utf-8") as stream:
                stream.write(" \n")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_sensor_stream(session)


if __name__ == "__main__":
    unittest.main()
