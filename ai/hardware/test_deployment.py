"""Layer 1/2/3 contract regressions. All generated inputs here are synthetic."""
import json
import os
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware.config import HardwareConfig
from hardware.live_alignment import WristBuffer, multimodal_frame
from hardware.mjpeg import CameraFrame
from hardware.mqtt_wrist import validate_wrist_payload
from hardware.ntp_server import reply, timestamp
from hardware import test_hardware as fixtures
BASE = fixtures.BASE
from process_recording import process_recording


def sample(seq, epoch):
    return {"seq": seq, "t_ms": epoch, "acc": [0, 0, 1],
            "gyro": [0, 0, 0], "force": [10, 20, 30, 40]}


class DeploymentTests(unittest.TestCase):
    def test_default_topology_and_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            config = HardwareConfig.from_environment()
        self.assertEqual(config.camera_url, "http://192.168.137.111:81/stream")
        self.assertEqual(config.mqtt_host, "192.168.137.1")
        self.assertEqual(config.alignment_window_ms, 10)
        with patch.dict(os.environ, {"SMARTWEAR_MQTT_PORT": "1884",
                                     "SMARTWEAR_ALIGNMENT_WINDOW_MS": "8"}):
            self.assertEqual(HardwareConfig.from_environment().mqtt_port, 1884)
            self.assertEqual(HardwareConfig.from_environment().alignment_window_ms, 8)

    def test_bounded_ring_ten_ms_inclusive_and_stale_missing(self):
        buffer = WristBuffer()
        for seq in range(110):
            buffer.append(sample(seq, BASE + seq * 20))
        self.assertEqual(len(buffer.samples), 100)
        last = BASE + 109 * 20
        self.assertEqual(buffer.nearest(last + 10, wait_s=0)["seq"], 109)
        self.assertIsNone(buffer.nearest(last + 11, wait_s=0))
        self.assertIsNone(buffer.nearest(BASE, wait_s=0))

    def test_future_sample_and_reset(self):
        buffer = WristBuffer()
        buffer.append(sample(5, BASE))
        producer = threading.Timer(0.01, lambda: buffer.append(sample(6, BASE + 20)))
        producer.start()
        try:
            self.assertEqual(buffer.nearest(BASE + 18, wait_s=0.5)["seq"], 6)
        finally:
            producer.join()
        buffer.append(sample(0, BASE + 40))
        self.assertEqual(len(buffer.samples), 1)
        self.assertIsNone(buffer.nearest(BASE, wait_s=0))

    def test_handoff_preserves_original_frame_and_missing_is_null(self):
        frame = object()
        packet = CameraFrame(b"jpeg", BASE, 99)
        row = multimodal_frame(packet, frame, sample(4, BASE + 7))
        self.assertIs(row["frame"], frame)
        self.assertEqual(row["delta_ms"], 7)
        self.assertEqual(row["wrist"]["force"], [10, 20, 30, 40])
        self.assertIsNone(row["head"])
        self.assertIsNone(multimodal_frame(packet, frame, None)["wrist"])

    def test_adc_must_be_json_integer(self):
        row = sample(1, BASE)
        for force in ([1.0, 2, 3, 4], [True, 2, 3, 4]):
            with self.assertRaises(ValueError):
                validate_wrist_payload({**row, "force": force})

    def test_ntp_origin_and_server_mode(self):
        request = bytearray(48)
        request[0] = 0x23
        request[40:48] = timestamp(BASE / 1000)
        response = reply(request, BASE / 1000 + 0.01, BASE / 1000 + 0.02)
        self.assertEqual(response[0], 0x24)
        self.assertEqual(response[1], 10)
        self.assertEqual(response[24:32], request[40:48])
        self.assertEqual(response[40:48], timestamp(BASE / 1000 + 0.02))
        for bad in (b"", b"\x24" + bytes(47), b"\x03" + bytes(47)):
            with self.assertRaises(ValueError):
                reply(bad, BASE / 1000, BASE / 1000)

    def test_manual_hardware_retry_does_not_generate_simulated_sensors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / "session"
            session.mkdir()
            fixtures.HardwareTests().write_inputs(session)
            marker = session / "hardware_capture.json"
            config = json.loads(marker.read_text(encoding="utf-8"))
            config["alignment_window_ms"] = 10
            marker.write_text(json.dumps(config), encoding="utf-8")
            process_recording(session / "camera.jsonl", root)
            meta = json.loads((session / "real_sensors.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["alignment_window_ms"], 10)
            self.assertEqual(meta["matched_count"], 20)
            self.assertFalse((session / "sensors.jsonl").exists())

    def test_analysis_rejects_missing_measured_stream(self):
        from analysis.compare_sensors import load_sensor_stream
        from preprocessing.normalize_camera import normalize_camera_data
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary)
            fixtures.HardwareTests().write_inputs(session)
            normalize_camera_data(session / "camera.jsonl", session / "camera.normalized.jsonl")
            with self.assertRaisesRegex(ValueError, "no simulated fallback"):
                load_sensor_stream(session)

    def test_capture_failure_saves_failed_manifest(self):
        from hardware.record_hardware import record_hardware
        with tempfile.TemporaryDirectory() as temporary, \
                patch("hardware.record_hardware.SESSION_ROOT", Path(temporary)), \
                patch("hardware.record_hardware.CameraReceiver") as camera, \
                patch("hardware.record_hardware.WristReceiver") as wrist:
            camera.return_value.snapshot.return_value = {}
            wrist.return_value.snapshot.return_value = {}
            camera.return_value.get.side_effect = RuntimeError("test disconnect")
            with self.assertRaisesRegex(RuntimeError, "test disconnect"):
                record_hardware(show_window=False, duration_s=1)
            marker = next(Path(temporary).glob("*/hardware_capture.json"))
            document = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(document["status"], "failed")
            self.assertIn("test disconnect", document["error"])

    def test_actual_ai_receives_aligned_synthetic_frames(self):
        import cv2
        import numpy as np
        import time
        from types import SimpleNamespace
        from hardware.record_hardware import record_hardware
        success, jpeg = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertTrue(success)
        handoffs = []
        finalization_times = []
        closed = []
        import mediapipe as mp
        create_landmarker = mp.tasks.vision.HandLandmarker.create_from_options
        def model(options):
            detector = create_landmarker(options)
            close = detector.close
            def tracked_close():
                closed.append('model')
                close()
            detector.close = tracked_close
            return detector
        def git_version(*args, **kwargs):
            finalization_times.append(time.monotonic_ns())
            return SimpleNamespace(stdout='fixture-commit')
        with tempfile.TemporaryDirectory() as temporary, \
                patch("hardware.record_hardware.SESSION_ROOT", Path(temporary)), \
                patch("hardware.record_hardware.CameraReceiver") as camera, \
                patch("hardware.record_hardware.WristReceiver") as wrist, \
                patch.object(mp.tasks.vision.HandLandmarker, 'create_from_options', side_effect=model), \
                patch("hardware.record_hardware.subprocess.run", side_effect=git_version):
            camera.return_value.stop.side_effect = lambda: closed.append('camera')
            wrist.return_value.stop.side_effect = lambda: closed.append('wrist')
            camera.return_value.snapshot.return_value = {"received_jpeg": 3}
            camera.return_value.get.side_effect = [
                (CameraFrame(jpeg.tobytes(), BASE + index * 40, index), BASE + index * 40 + 2)
                for index in range(3)]
            wrist.return_value.snapshot.return_value = {"received": 3, "newest_sample_age_ms": 2}
            wrist.return_value.buffer.nearest.side_effect = [sample(i, BASE + i*40 + 5) for i in range(3)]
            output = record_hardware(show_window=False, duration_s=10,
                                     on_multimodal=handoffs.append,
                                     stop_requested=lambda: len(handoffs) == 3)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual([row["source_frame_seq"] for row in rows], [0, 1, 2])
            self.assertTrue(all(row["live_alignment"]["delta_ms"] == 5 for row in rows))
            self.assertEqual(handoffs[0]["frame"].shape, (240, 320, 3))
            self.assertTrue(output.with_suffix(".avi").is_file())
            manifest=json.loads((output.parent/'capture_manifest.json').read_text(encoding='utf-8'))
            events={event['name']:event['host_monotonic_ns'] for event in manifest['events']}
            self.assertLess(events['capture_started'],events['capture_stopped'])
            self.assertLessEqual(events['capture_stopped'],finalization_times[0])
            self.assertEqual(closed, ['camera', 'wrist', 'model'])
            timings = json.loads((output.parent/'performance.json').read_text())
            self.assertLess(timings['events_ms']['model_ready'],timings['events_ms']['capture_started'])
            self.assertEqual(timings['stages']['inference']['count'], 3)


if __name__ == "__main__":
    unittest.main()
