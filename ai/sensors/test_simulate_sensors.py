import json
import tempfile
import unittest
from pathlib import Path

from simulate_sensors import (read_camera_records, read_sensor_records,
                              simulate_from_camera, write_sensor_records)


def camera_frame(timestamp, state, label, wrist_x=0.5):
    points = [{"id": i, "x": 0.5, "y": 0.5} for i in range(21)]
    points[0].update(x=wrist_x, y=0.8)
    points[9].update(x=0.5, y=0.4)
    return {"timestamp_ms": timestamp, "hands": [{"landmarks": points}],
            "action_estimate": {"label": label, "hand_state": state,
                                "source": "camera_landmarks"}}


class SensorTests(unittest.TestCase):
    def test_camera_controls_timing_and_force(self):
        frames = [camera_frame(303, "OPEN", "OPEN"),
                  camera_frame(503, "CLOSED", "GRAB"),
                  camera_frame(703, "CLOSED", "GRAB"),
                  camera_frame(903, "CLOSED", "ASSEMBLY"),
                  camera_frame(1103, "OPEN", "RELEASE")]
        rows = list(simulate_from_camera(frames, noise_level=0))
        self.assertEqual([r["timestamp_ms"] for r in rows], [303, 503, 703, 903, 1103])
        self.assertEqual(len(rows), len(frames))
        self.assertGreater(rows[2]["force_emg_raw"], rows[1]["force_emg_raw"])
        self.assertGreater(rows[3]["torque"]["torque"], 0)
        self.assertEqual(rows[0]["torque"]["torque"], 0)
        self.assertLess(rows[4]["force_emg_raw"], rows[3]["force_emg_raw"])
        self.assertEqual(rows, list(simulate_from_camera(frames, noise_level=0)))

    def test_same_clock_time_can_have_different_hand_state(self):
        open_frame = [camera_frame(3000, "OPEN", "OPEN")]
        closed_frame = [camera_frame(3000, "CLOSED", "GRAB")]
        open_force = list(simulate_from_camera(open_frame, noise_level=0))[0]["force_emg_raw"]
        closed_force = list(simulate_from_camera(closed_frame, noise_level=0))[0]["force_emg_raw"]
        self.assertEqual(open_force, closed_force)  # no elapsed time yet
        # After another frame, the camera state controls the simulated signal.
        open_frame.append(camera_frame(3200, "OPEN", "OPEN"))
        closed_frame.append(camera_frame(3200, "CLOSED", "GRAB"))
        self.assertLess(list(simulate_from_camera(open_frame, noise_level=0))[1]["force_emg_raw"],
                        list(simulate_from_camera(closed_frame, noise_level=0))[1]["force_emg_raw"])

    def test_camera_provenance_and_io(self):
        with tempfile.TemporaryDirectory() as directory:
            camera = Path(directory) / "camera.jsonl"
            frames = [camera_frame(303, "OPEN", "OPEN"), camera_frame(503, "CLOSED", "GRAB")]
            camera.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
            self.assertEqual(list(read_camera_records(camera)), frames)
            sensor = Path(directory) / "sensor.jsonl"
            write_sensor_records(sensor, simulate_from_camera(read_camera_records(camera)))
            before = sensor.read_bytes()
            self.assertEqual(len(list(read_sensor_records(sensor))), 2)
            with self.assertRaises(FileExistsError):
                write_sensor_records(sensor, simulate_from_camera(frames))
            self.assertEqual(sensor.read_bytes(), before)
            frames[1]["action_estimate"]["source"] = "invented"
            camera.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
            with self.assertRaises(ValueError):
                list(read_camera_records(camera))

    def test_invalid_noise_and_nonincreasing_time(self):
        frame = camera_frame(300, "OPEN", "OPEN")
        with self.assertRaises(ValueError):
            list(simulate_from_camera([frame], noise_level=-1))
        with self.assertRaises(ValueError):
            list(simulate_from_camera([frame, frame]))


if __name__ == "__main__":
    unittest.main()
