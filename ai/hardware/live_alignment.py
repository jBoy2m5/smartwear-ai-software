"""Bounded source-time nearest-neighbour handoff from Layer 2 to Layer 3."""
import threading
import time
from collections import deque


class WristBuffer:
    def __init__(self, maxlen=100):
        self.samples = deque(maxlen=maxlen)
        self.condition = threading.Condition()

    def append(self, sample):
        with self.condition:
            if self.samples and (sample["seq"] <= self.samples[-1]["seq"]
                                 or sample["t_ms"] <= self.samples[-1]["t_ms"]):
                self.samples.clear()  # Never match across a reboot/clock discontinuity.
            self.samples.append(sample)
            self.condition.notify_all()

    def nearest(self, epoch_ms, window_ms=10, wait_s=0.04):
        deadline = time.monotonic() + wait_s
        with self.condition:
            # Allow the first following 50-Hz sample to arrive before choosing.
            while not self.samples or self.samples[-1]["t_ms"] < epoch_ms:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(remaining)
            sample = min(self.samples, key=lambda s: abs(s["t_ms"] - epoch_ms), default=None)
            return sample if sample and abs(sample["t_ms"] - epoch_ms) <= window_ms else None


def multimodal_frame(packet, frame_bgr, sample):
    """In-process contract: ndarray is deliberately not serialized into JSON."""
    return {"frame_id": packet.sequence, "t_ms": packet.epoch_ms,
            "delta_ms": abs(sample["t_ms"] - packet.epoch_ms) if sample else None,
            "frame": frame_bgr,
            "wrist": ({key: sample[key] for key in ("seq", "acc", "gyro", "force", "imu_status", "imu_address", "imu_age_ms")
                       if key in sample}
                      if sample else None), "head": None}
