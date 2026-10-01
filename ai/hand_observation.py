"""Estimate visible hand posture and motion from MediaPipe landmarks.

These are camera observations, not proof that an object was grasped or assembled.
"""

import math

SIDES = ("left", "right")
LABELS = {"OPEN", "REACH", "GRAB", "ASSEMBLY", "RELEASE", "OTHER", "NO_HAND"}
STATES = {"OPEN", "CLOSED", "OTHER", "NONE"}


def anatomical_handedness(model_label):
    """Correct the reported MediaPipe side for this mirrored camera input."""
    return {"Left": "Right", "Right": "Left"}.get(model_label, "unknown")


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


def valid_landmarks(points):
    return (isinstance(points, list) and len(points) == 21
            and all(isinstance(p, dict) and type(p.get("id")) is int for p in points)
            and {p["id"] for p in points} == set(range(21))
            and all(type(p.get(axis)) in (int, float) and math.isfinite(p[axis])
                    for p in points for axis in ("x", "y", "z")))


def select_hands(hands):
    """Resolve anatomical sides by corrected camera handedness, never list order.

    This is for one operator. Duplicate/unknown handedness cannot be safely
    resolved to left/right: report ambiguity rather than guessing identities.
    """
    if not isinstance(hands, list):
        raise ValueError("hands must be a list")
    grouped = {side: [] for side in SIDES}
    indices = set()
    ambiguous = len(hands) > 2
    for hand in hands:
        if not isinstance(hand, dict):
            raise ValueError("Invalid hand record")
        side = str(hand.get("handedness", "unknown")).lower()
        index = hand.get("hand_index")
        if side not in SIDES or type(index) is not int or index < 0 or index in indices:
            ambiguous = True
        else:
            grouped[side].append(hand)
            indices.add(index)
    if ambiguous or any(len(group) > 1 for group in grouped.values()):
        return {side: ("ambiguous", None) for side in SIDES}
    result = {}
    for side, group in grouped.items():
        if not group:
            result[side] = ("missing", None)
        elif not valid_landmarks(group[0].get("landmarks")):
            result[side] = ("ambiguous", None)
        else:
            result[side] = ("detected", group[0])
    return result


def validate_hand_actions(actions, hands):
    if not isinstance(actions, dict) or set(actions) != set(SIDES):
        raise ValueError("hand_actions must contain left and right")
    selected = select_hands(hands)
    for side in SIDES:
        action = actions[side]
        status, hand = selected[side]
        if (not isinstance(action, dict) or action.get("source") != "camera_landmarks"
                or action.get("label") not in LABELS or action.get("hand_state") not in STATES
                or action.get("tracking_status") != status
                or action.get("hand_index") != (hand["hand_index"] if hand else None)):
            raise ValueError(f"Invalid action/hand association for {side}")
        if status == "missing" and (action["label"], action["hand_state"]) != ("NO_HAND", "NONE"):
            raise ValueError("Missing hand must be NO_HAND/NONE")
        if status == "ambiguous" and (action["label"], action["hand_state"]) != ("OTHER", "OTHER"):
            raise ValueError("Ambiguous hand must be OTHER/OTHER")
        if status == "detected" and (action["label"] == "NO_HAND" or action["hand_state"] == "NONE"):
            raise ValueError("Detected hand cannot be NO_HAND/NONE")


class TwoHandActionDetector:
    """Independent histories keyed by handedness; not a multi-person tracker."""

    def __init__(self):
        self.detectors = {side: HandActionDetector() for side in SIDES}
        self.previous_ms = None

    def update(self, timestamp_ms, hands):
        if (type(timestamp_ms) is not int or timestamp_ms < 0
                or (self.previous_ms is not None and timestamp_ms <= self.previous_ms)):
            raise ValueError("Camera timestamps must strictly increase")
        if self.previous_ms is not None and timestamp_ms - self.previous_ms > 500:
            self.detectors = {side: HandActionDetector() for side in SIDES}
        self.previous_ms = timestamp_ms
        actions = {}
        for side, (status, hand) in select_hands(hands).items():
            detector = self.detectors[side]
            if status == "detected":
                label = detector.update(timestamp_ms, hand["landmarks"])
                action = observation(label, detector.pose)
            else:
                self.detectors[side] = HandActionDetector()
                action = observation("NO_HAND", "NONE") if status == "missing" else observation("OTHER", "OTHER")
            actions[side] = {**action, "tracking_status": status,
                             "hand_index": hand["hand_index"] if hand else None}
        return actions
