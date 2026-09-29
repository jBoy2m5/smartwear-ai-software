"""Estimate visible hand posture and motion from MediaPipe landmarks.

These are camera observations, not proof that an object was grasped or assembled.
"""

import math


def finger_angle(a, b, c):
    first = (a["x"] - b["x"], a["y"] - b["y"])
    second = (c["x"] - b["x"], c["y"] - b["y"])
    length = math.hypot(*first) * math.hypot(*second)
    if length < 1e-9:
        return None
    cosine = max(-1.0, min(1.0,
                      (first[0] * second[0] + first[1] * second[1]) / length))
    return math.degrees(math.acos(cosine))


class HandActionDetector:
    """Track a single hand; labels describe visual patterns only."""

    def __init__(self):
        self.pose = "OTHER"
        self.candidate = None
        self.candidate_frames = 0
        self.closed_since_ms = None
        self.release_until_ms = None
        self.previous_wrist = None
        self.previous_time_ms = None
        self.speed = 0.0

    def update(self, timestamp_ms, landmarks):
        if landmarks is None:
            self.__init__()
            return "NO_HAND"

        points = {p["id"]: p for p in landmarks}
        if set(points) != set(range(21)):
            return "OTHER"

        straight = 0
        bent = 0
        for mcp, pip, tip in ((5, 6, 8), (9, 10, 12),
                              (13, 14, 16), (17, 18, 20)):
            angle = finger_angle(points[mcp], points[pip], points[tip])
            if angle is not None and angle >= 155:
                straight += 1
            elif angle is not None and angle <= 135:
                bent += 1
        detected_pose = ("OPEN" if straight >= 3 else
                         "CLOSED" if bent >= 3 else "OTHER")

        wrist = (points[0]["x"], points[0]["y"])
        palm = max(0.01, math.dist(wrist, (points[9]["x"], points[9]["y"])))
        if self.previous_wrist is not None and timestamp_ms > self.previous_time_ms:
            seconds = (timestamp_ms - self.previous_time_ms) / 1000
            movement = math.dist(wrist, self.previous_wrist) / palm / seconds
            self.speed = 0.4 * movement + 0.6 * self.speed
        self.previous_wrist = wrist
        self.previous_time_ms = timestamp_ms

        if detected_pose == self.candidate:
            self.candidate_frames += 1
        else:
            self.candidate = detected_pose
            self.candidate_frames = 1
        if self.candidate_frames >= 3:
            self.pose = detected_pose

        if self.pose == "CLOSED":
            if self.closed_since_ms is None:
                self.closed_since_ms = timestamp_ms
            self.release_until_ms = None
            if timestamp_ms - self.closed_since_ms >= 800 and self.speed < 0.8:
                return "ASSEMBLY"
            return "GRAB"

        if self.pose == "OPEN":
            if self.closed_since_ms is not None:
                self.closed_since_ms = None
                self.release_until_ms = timestamp_ms + 650
            if self.release_until_ms is not None and timestamp_ms <= self.release_until_ms:
                return "RELEASE"
            self.release_until_ms = None
            return "REACH" if self.speed >= 0.8 else "OPEN"

        return "OTHER"


def observation(label, hand_state):
    """Add provenance without suggesting a calibrated confidence score."""
    return {"label": label, "hand_state": "NONE" if label == "NO_HAND" else hand_state,
            "source": "camera_landmarks"}
