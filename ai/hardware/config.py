"""Shared deployment defaults. Environment overrides are read at call time."""
import os
from dataclasses import dataclass

CAMERA_URL = "http://192.168.137.111:81/stream"
MQTT_HOST = "192.168.137.1"
WRIST_IP = "192.168.137.100"  # Publisher identity, never the broker address.
TOPIC = "wearable/user01/wrist/data"
ALIGNMENT_WINDOW_MS = 10


@dataclass(frozen=True)
class HardwareConfig:
    camera_url: str = CAMERA_URL
    mqtt_host: str = MQTT_HOST
    mqtt_port: int = 1883
    topic: str = TOPIC
    alignment_window_ms: int = ALIGNMENT_WINDOW_MS

    @classmethod
    def from_environment(cls):
        value = cls(
            os.getenv("SMARTWEAR_CAMERA_URL", CAMERA_URL),
            os.getenv("SMARTWEAR_MQTT_HOST", MQTT_HOST),
            int(os.getenv("SMARTWEAR_MQTT_PORT", "1883")),
            os.getenv("SMARTWEAR_MQTT_TOPIC", TOPIC),
            int(os.getenv("SMARTWEAR_ALIGNMENT_WINDOW_MS", "10")),
        )
        if not 1 <= value.mqtt_port <= 65535 or not 1 <= value.alignment_window_ms <= 500:
            raise ValueError("Invalid MQTT port or alignment window")
        return value
