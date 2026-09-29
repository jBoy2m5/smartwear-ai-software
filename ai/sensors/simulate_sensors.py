"""Simulate unavailable sensors using observations from one real camera session.

The hand state comes from MediaPipe landmarks. IMU, force and torque remain
invented numbers; they are never measurements of that worker.
"""

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
from hand_observation import SIDES, select_hands, validate_hand_actions

AXES = ("ax", "ay", "az", "gx", "gy", "gz")
STATES = {"OPEN", "CLOSED", "OTHER", "NONE"}
LABELS = {"OPEN", "REACH", "GRAB", "ASSEMBLY", "RELEASE", "OTHER", "NO_HAND"}
V2_SIMULATED_FIELDS = ["imu_head"] + [
    f"hand_sensors.{side}.{field}" for side in SIDES
    for field in ("imu_wrist", "force_emg_raw", "torque")]


def validate_config(random_seed, noise_level):
    if type(random_seed) is not int or not math.isfinite(noise_level) or not 0 <= noise_level <= 1:
        raise ValueError("Invalid random_seed or noise_level")


def read_camera_records(path):
    """Require camera-derived actions; never silently invent action labels."""
    previous = -1
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            frame = json.loads(line)
            timestamp = frame["timestamp_ms"]
            if type(timestamp) is not int or timestamp <= previous:
                raise ValueError("Camera timestamps must be increasing integers")
            if frame.get("schema_version") == "smartwear.camera.v2":
                validate_hand_actions(frame.get("hand_actions"), frame.get("hands"))
            elif frame.get("schema_version") is None:
                estimate = frame["action_estimate"]
                if (estimate.get("source") != "camera_landmarks"
                        or estimate.get("hand_state") not in STATES
                        or estimate.get("label") not in LABELS):
                    raise ValueError("Camera action estimate is missing or has unknown provenance")
            else:
                raise ValueError("Unsupported camera schema; normalize the raw recording first")
            previous = timestamp
            yield frame


def _simulate_single_hand(frames, random_seed=42, noise_level=0.02):
    validate_config(random_seed, noise_level)
    rng = random.Random(random_seed)
    previous_time = None
    previous_wrist = None
    force = 100.0
    angle = 0.0

    def noisy(value, scale, lower=None):
        result = value + rng.uniform(-1, 1) * noise_level * scale
        return round(max(lower, result) if lower is not None else result, 6)

    for frame in frames:
        timestamp = frame["timestamp_ms"]
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError("Camera timestamps must strictly increase")
        dt = 0 if previous_time is None else (timestamp - previous_time) / 1000
        hand = frame["hands"][0] if frame["hands"] else None
        wrist = None
        palm = 0.1
        if hand and len(hand.get("landmarks", [])) == 21:
            landmarks = {p["id"]: p for p in hand["landmarks"]}
            wrist = (landmarks[0]["x"], landmarks[0]["y"])
            palm = max(0.01, math.dist(wrist, (landmarks[9]["x"], landmarks[9]["y"])))
        visual_speed = (math.dist(wrist, previous_wrist) / palm / dt
                        if wrist is not None and previous_wrist is not None and dt > 0 else 0)
        visual_speed = min(5.0, visual_speed)
        state = frame["action_estimate"]["hand_state"]
        label = frame["action_estimate"]["label"]
        target_force = 800 if state == "CLOSED" else 250 if state == "OTHER" else 100
        force += (target_force - force) * min(1.0, dt / 0.4)
        if label == "ASSEMBLY":
            angle = min(30.0, angle + 15.0 * dt)
        elif label == "RELEASE":
            angle = max(0.0, angle - 30.0 * dt)
        else:
            angle = max(0.0, angle - 5.0 * dt)
        phase = timestamp / 1000

        def imu(amplitude):
            return {
                "ax": noisy(amplitude * math.sin(2 * math.pi * phase), 1),
                "ay": noisy(amplitude * math.cos(2 * math.pi * phase), 1),
                "az": noisy(9.81 + 0.2 * amplitude * math.sin(4 * math.pi * phase), 1),
                "gx": noisy(0.4 * amplitude * math.sin(2 * math.pi * phase), 0.2),
                "gy": noisy(0.4 * amplitude * math.cos(2 * math.pi * phase), 0.2),
                "gz": noisy(0.2 * amplitude * math.sin(4 * math.pi * phase), 0.2),
            }

        yield {
            "timestamp_ms": timestamp,
            "imu_head": imu(0.08),
            "imu_wrist": imu(0.08 + min(2.0, 0.5 * visual_speed)),
            "force_emg_raw": noisy(force, 1000, 0),
            "torque": {"torque": noisy(3 if label == "ASSEMBLY" else 0, 3, 0),
                       "angle": noisy(angle, 30, 0)},
        }
        previous_time = timestamp
        previous_wrist = wrist


def simulate_from_camera(frames, random_seed=42, noise_level=0.02):
    """Version 2 keeps separate state/RNG per anatomical hand; v1 stays readable."""
    validate_config(random_seed, noise_level)
    frames = list(frames)
    if not frames:
        return
    versions = {frame.get("schema_version") for frame in frames}
    if versions == {None}:
        yield from _simulate_single_hand(frames, random_seed, noise_level)
        return
    if versions != {"smartwear.camera.v2"}:
        raise ValueError("Mixed or unsupported camera schemas")
    previous = -1
    for frame in frames:
        timestamp = frame["timestamp_ms"]
        if type(timestamp) is not int or timestamp <= previous:
            raise ValueError("Camera timestamps must strictly increase")
        validate_hand_actions(frame.get("hand_actions"), frame.get("hands"))
        previous = timestamp
    # The single head channel has its own deterministic sequence.
    head_frames = [{"timestamp_ms": f["timestamp_ms"], "hands": [],
                    "action_estimate": {"label": "NO_HAND", "hand_state": "NONE"}}
                   for f in frames]
    rows = [{"schema_version": "smartwear.sensors.v2", "timestamp_ms": h["timestamp_ms"],
             "imu_head": h["imu_head"], "hand_sensors": {}}
            for h in _simulate_single_hand(head_frames, random_seed, noise_level)]
    for side_number, side in enumerate(SIDES):
        run = []

        def flush_run():
            if not run:
                return
            # A reappearing hand starts afresh, rather than inheriting force,
            # motion, or torque from before it disappeared or from the other hand.
            seed = random_seed + 1009 * (side_number + 1) + run[0][1]["timestamp_ms"]
            samples = _simulate_single_hand((f for _, f in run), seed, noise_level)
            for (index, _), sample in zip(run, samples):
                rows[index]["hand_sensors"][side].update(
                    {field: sample[field] for field in ("imu_wrist", "force_emg_raw", "torque")})
            run.clear()

        for index, frame in enumerate(frames):
            action = frame["hand_actions"][side]
            rows[index]["hand_sensors"][side] = {
                "tracking_status": action["tracking_status"],
                "imu_wrist": None, "force_emg_raw": None, "torque": None}
            if run and frame["timestamp_ms"] - run[-1][1]["timestamp_ms"] > 500:
                flush_run()
            if action["tracking_status"] != "detected":
                flush_run()
                continue
            _, hand = select_hands(frame["hands"])[side]
            run.append((index, {"timestamp_ms": frame["timestamp_ms"],
                                "hands": [hand], "action_estimate": action}))
        flush_run()
    yield from rows


def validate_record(record):
    timestamp = record["timestamp_ms"]
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError("Invalid timestamp_ms")
    values = [record["imu_head"][axis] for axis in AXES]
    if record.get("schema_version") == "smartwear.sensors.v2":
        hands = record.get("hand_sensors")
        if not isinstance(hands, dict) or set(hands) != set(SIDES):
            raise ValueError("Expected left and right hand_sensors")
        for side in SIDES:
            hand = hands[side]
            if hand.get("tracking_status") not in ("detected", "missing", "ambiguous"):
                raise ValueError("Invalid sensor tracking status")
            if hand["tracking_status"] != "detected":
                if any(hand.get(field) is not None for field in ("imu_wrist", "force_emg_raw", "torque")):
                    raise ValueError("Unavailable hand sensors must be null")
                continue
            if not isinstance(hand.get("imu_wrist"), dict) or not isinstance(hand.get("torque"), dict):
                raise ValueError("Detected hand requires sensor values")
            values.extend(hand["imu_wrist"][axis] for axis in AXES)
            values.extend([hand["force_emg_raw"], hand["torque"]["torque"], hand["torque"]["angle"]])
    elif record.get("schema_version") is None:
        values.extend(record["imu_wrist"][axis] for axis in AXES)
        values.extend([record["force_emg_raw"], record["torque"]["torque"], record["torque"]["angle"]])
    else:
        raise ValueError("Unsupported sensor schema")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("Sensor values must be finite numbers")


def read_sensor_records(path):
    """Future hardware adapters can provide the same record structure."""
    previous = -1
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            validate_record(record)
            if record["timestamp_ms"] <= previous:
                raise ValueError("Sensor timestamps must strictly increase")
            previous = record["timestamp_ms"]
            yield record


def write_sensor_records(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    previous = -1
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for record in records:
            validate_record(record)
            if record["timestamp_ms"] <= previous:
                raise ValueError("Sensor timestamps must strictly increase")
            stream.write(json.dumps(record, allow_nan=False) + "\n")
            previous = record["timestamp_ms"]
            count += 1
    return count, previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-file", type=Path, required=True,
                        help="Normalized JSONL with camera-derived action_estimate")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--noise-level", type=float, default=0.02)
    args = parser.parse_args()
    metadata_path = args.output.with_suffix(".meta.json")
    try:
        validate_config(args.random_seed, args.noise_level)
        if args.output.exists() or metadata_path.exists():
            raise FileExistsError("Output or metadata already exists")
        camera_hash = hashlib.sha256(args.camera_file.read_bytes()).hexdigest()
        frames = list(read_camera_records(args.camera_file))
        if not frames:
            raise ValueError("Camera file is empty")
        count, last = write_sensor_records(
            args.output, simulate_from_camera(frames, args.random_seed, args.noise_level))
        metadata = {
            "source": "simulated_from_camera_observations",
            "camera_file": str(args.camera_file.resolve()),
            "camera_sha256": camera_hash,
            "sample_count": count,
            "first_timestamp_ms": frames[0]["timestamp_ms"],
            "last_timestamp_ms": last,
            "random_seed": args.random_seed,
            "noise_level": args.noise_level,
            "camera_action_counts": (dict(Counter(f["action_estimate"]["label"] for f in frames))
                                     if frames[0].get("schema_version") is None else {}),
            "simulated_fields": ["imu_head", "imu_wrist", "force_emg_raw", "torque"],
            "time_note": "Timestamps copied from camera frames, not independently synchronized clocks",
            "unit_note": "IMU m/s^2 and rad/s, torque N*m and degrees are simulator assumptions; force_emg_raw is unitless",
        }
        metadata["sensors_sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
        if frames[0].get("schema_version") == "smartwear.camera.v2":
            metadata["schema_version"] = "smartwear.sensors_meta.v2"
            metadata["simulated_fields"] = V2_SIMULATED_FIELDS
            metadata["camera_action_counts"] = {
                side: dict(Counter(f["hand_actions"][side]["label"] for f in frames))
                for side in SIDES}
        with metadata_path.open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created {args.output.resolve()}: {count} simulated sensor samples from one camera session")
    print(f"Metadata: {metadata_path.resolve()}")


if __name__ == "__main__":
    main()
