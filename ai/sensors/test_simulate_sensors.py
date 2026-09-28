import json
import math
import statistics
import tempfile
import unittest
from pathlib import Path

from simulate_sensors import (simulated_records, read_sensor_records,
                              write_sensor_records, camera_end_ms, validate_record)


class SensorTests(unittest.TestCase):
    def test_default_schema_and_reproducibility(self):
        rows = list(simulated_records())
        self.assertEqual(len(rows), 700)
        self.assertEqual([r['timestamp_ms'] for r in rows], list(range(0, 7000, 10)))
        self.assertEqual(rows, list(simulated_records()))
        self.assertNotEqual(rows, list(simulated_records(random_seed=43)))
        for row in rows:
            validate_record(json.loads(json.dumps(row, allow_nan=False)))
            self.assertEqual(set(row), {'timestamp_ms', 'imu_head', 'imu_wrist',
                                        'force_emg_raw', 'torque'})

    def test_invalid_parameters(self):
        for kwargs in ({'duration_s': 0}, {'duration_s': float('nan')},
                       {'duration_s': float('inf')}, {'sampling_rate_hz': 0},
                       {'sampling_rate_hz': 1001}, {'sampling_rate_hz': 99.5},
                       {'noise_level': -1}, {'noise_level': float('nan')},
                       {'noise_level': 2}, {'random_seed': 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                list(simulated_records(**kwargs))

    def test_rates_and_camera_endpoint(self):
        for rate in (1, 60, 100, 333, 1000):
            rows = list(simulated_records(sampling_rate_hz=rate, until_timestamp_ms=48241))
            times = [r['timestamp_ms'] for r in rows]
            self.assertEqual(times, [i * 1000 // rate for i in range(len(rows))])
            self.assertTrue(all(b > a for a, b in zip(times, times[1:])))
            self.assertLess(times[-2], 48241)
            self.assertGreaterEqual(times[-1], 48241)
        rows = list(simulated_records(until_timestamp_ms=48240))
        self.assertEqual((len(rows), rows[-1]['timestamp_ms']), (4825, 48240))

    def test_phase_trends(self):
        rows = list(simulated_records())
        mean_force = lambda start, end: statistics.mean(r['force_emg_raw'] for r in rows[start:end])
        self.assertLess(mean_force(200, 250), mean_force(250, 300))
        self.assertLess(mean_force(250, 300), mean_force(300, 350))
        self.assertLess(mean_force(300, 350), mean_force(350, 400))
        self.assertGreater(mean_force(600, 625), mean_force(625, 650))
        self.assertGreater(mean_force(625, 650), mean_force(650, 675))
        self.assertGreater(mean_force(650, 675), mean_force(675, 700))
        self.assertTrue(all(780 <= r['force_emg_raw'] <= 820 for r in rows[400:600]))
        movement = lambda part, name: statistics.mean(math.hypot(r[name]['ax'], r[name]['ay']) for r in part)
        self.assertGreater(movement(rows[:200], 'imu_wrist'), 5 * movement(rows[400:600], 'imu_wrist'))
        self.assertGreater(movement(rows[:200], 'imu_wrist'), 5 * movement(rows[:200], 'imu_head'))
        self.assertGreater(statistics.mean(r['torque']['torque'] for r in rows[400:600]), 1)
        self.assertLess(statistics.mean(r['torque']['torque'] for r in rows[:400]), 0.04)

    def test_continuity_and_cycle(self):
        rows = list(simulated_records(duration_s=14, noise_level=0))
        for a, b in zip(rows[:700], rows[700:]):
            self.assertEqual({k: v for k, v in a.items() if k != 'timestamp_ms'},
                             {k: v for k, v in b.items() if k != 'timestamp_ms'})
        for index in (200, 400, 600, 700):
            a, b = rows[index - 1:index + 1]
            self.assertLess(abs(a['force_emg_raw'] - b['force_emg_raw']), 1)
            self.assertLess(abs(a['torque']['torque'] - b['torque']['torque']), 0.01)
            self.assertLess(abs(a['torque']['angle'] - b['torque']['angle']), 0.02)

    def test_io_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sensors.jsonl'
            write_sensor_records(path, simulated_records())
            before = path.read_bytes()
            self.assertEqual(list(read_sensor_records(path)), list(simulated_records()))
            with self.assertRaises(FileExistsError):
                write_sensor_records(path, simulated_records())
            self.assertEqual(before, path.read_bytes())
            camera = Path(directory) / 'camera.jsonl'
            camera.write_text('{"timestamp_ms":303}\n{"timestamp_ms":48240}\n')
            original = camera.read_bytes()
            self.assertEqual(camera_end_ms(camera), 48240)
            self.assertEqual(original, camera.read_bytes())
            for content in ('', '{"timestamp_ms":3}\n{"timestamp_ms":3}\n',
                            '{"timestamp_ms":4}\n{"timestamp_ms":3}\n'):
                camera.write_text(content)
                with self.assertRaises(ValueError):
                    camera_end_ms(camera)


if __name__ == '__main__':
    unittest.main()
