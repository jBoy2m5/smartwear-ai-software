import io
import json
import unittest
from unittest.mock import patch
from ai.hardware.config import HardwareConfig
from backend.services.device_health import diagnose


class DeviceHealthTests(unittest.TestCase):
    def test_legacy_tcp_does_not_claim_camera_images_verified(self):
        with patch('backend.services.device_health.urlopen', side_effect=OSError), \
             patch('backend.services.device_health.tcp', return_value=True), \
             patch('backend.services.device_health.ntp', return_value=True):
            value = diagnose(HardwareConfig())
        self.assertEqual(value['camera']['state'], 'tcp_only')
        self.assertTrue(value['can_start'])

    def test_does_not_probe_stream_port_during_capture(self):
        with patch('backend.services.device_health.urlopen', side_effect=OSError), \
             patch('backend.services.device_health.tcp', return_value=True) as tcp, \
             patch('backend.services.device_health.ntp', return_value=True):
            value = diagnose(HardwareConfig(), active=True)
        self.assertEqual(tcp.call_count, 1)
        self.assertEqual(value['camera']['state'], 'in_use')
        self.assertFalse(value['can_start'])

    def test_boot_diagnostics_and_missing_ntp_gate_start(self):
        board = {'schema':'smartwear.cap.status/1', 'boot_id':'0123456789abcdef',
                 'reset_reason':'brownout', 'camera_ready':True, 'ntp_ready':False}
        with patch('backend.services.device_health.urlopen', return_value=io.BytesIO(json.dumps(board).encode())), \
             patch('backend.services.device_health.tcp', return_value=True), \
             patch('backend.services.device_health.ntp', return_value=False):
            value = diagnose(HardwareConfig())
        self.assertEqual(value['camera']['board']['reset_reason'], 'brownout')
        self.assertEqual(value['camera']['state'], 'starting')
        self.assertFalse(value['can_start'])
