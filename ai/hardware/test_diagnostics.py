import io
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware.mjpeg import CameraFrame, read_parts
from hardware.camera_receiver import CameraReceiver
from hardware.performance import Performance


class DiagnosticsTests(unittest.TestCase):
    def test_boot_change_detected_even_when_sequence_increases(self):
        with tempfile.TemporaryDirectory() as root:
            receiver = CameraReceiver(root, 'http://camera/stream')
            receiver._accept_frame(CameraFrame(b'jpeg', 1790000000000, 10, '0123456789abcdef', 'power_on'))
            with self.assertRaisesRegex(RuntimeError, 'brownout'):
                receiver._accept_frame(CameraFrame(b'jpeg', 1790000000020, 11, '1123456789abcdef', 'brownout'))
            self.assertEqual(receiver.snapshot()['clock_or_sequence_resets'], 1)

    def test_optional_boot_headers_preserved_and_invalid_id_rejected(self):
        jpeg = b'\xff\xd8image\xff\xd9'
        body = (f'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n'
                'X-Timestamp-Ms: 1790000000000\r\nX-Frame-Seq: 1\r\n'
                'X-Boot-Id: 0123456789abcdef\r\nX-Reset-Reason: brownout\r\n\r\n').encode()+jpeg+b'\r\n--frame--\r\n'
        value = list(read_parts(io.BytesIO(body), 'multipart/x-mixed-replace; boundary=frame'))[0]
        self.assertEqual(value.reset_reason, 'brownout')
        with self.assertRaises(ValueError):
            list(read_parts(io.BytesIO(body.replace(b'0123456789abcdef', b'invalid')), 'multipart/x-mixed-replace; boundary=frame'))

    def test_metrics_keep_full_counts_and_bound_percentile_memory(self):
        metrics = Performance()
        for i in range(3000): metrics.add('inference', i)
        value = metrics.snapshot()['stages']['inference']
        self.assertEqual(value['count'], 3000)
        self.assertEqual(value['percentile_samples'], 2048)
        self.assertEqual(value['max_ms'], 2999)
