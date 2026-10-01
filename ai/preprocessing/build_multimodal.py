"""Join one normalized camera session with its simulated sensors by exact time."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
from sensors.simulate_sensors import read_camera_records, read_sensor_records, V2_SIMULATED_FIELDS
from hand_observation import SIDES

SENSOR_FIELDS = ("imu_head", "imu_wrist", "force_emg_raw", "torque")


def build_multimodal(camera_path, sensor_path, output_path, metadata_path=None):
    """Validate the complete pair before exclusively creating the output.

    Exact matching is appropriate only for sensors generated from these camera
    frames. No interpolation, zero filling, or independent clock correction.
    """
    camera_path, sensor_path, output_path = map(
        Path, (camera_path, sensor_path, output_path))
    metadata_path = (Path(metadata_path) if metadata_path is not None
                     else sensor_path.with_suffix(".meta.json"))
    if output_path.resolve() in {p.resolve() for p in
                                 (camera_path, sensor_path, metadata_path)}:
        raise ValueError("Output must differ from every input")
    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")

    camera_hash = hashlib.sha256(camera_path.read_bytes()).hexdigest()
    sensor_hash = hashlib.sha256(sensor_path.read_bytes()).hexdigest()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("source") != "simulated_from_camera_observations":
        raise ValueError("Expected camera-conditioned simulated sensor metadata")
    if metadata.get("camera_sha256") != camera_hash:
        raise ValueError("Sensors belong to a different camera file (SHA-256 mismatch)")
    frames = list(read_camera_records(camera_path))
    sensors = list(read_sensor_records(sensor_path))
    if not frames or len(frames) != len(sensors):
        raise ValueError("Camera and sensors must have the same nonzero row count")
    two_hands = frames[0].get("schema_version") == "smartwear.camera.v2"
    camera_version = "smartwear.camera.v2" if two_hands else None
    sensor_version = "smartwear.sensors.v2" if two_hands else None
    simulated_fields = V2_SIMULATED_FIELDS if two_hands else list(SENSOR_FIELDS)
    if (any(f.get("schema_version") != camera_version for f in frames)
            or any(s.get("schema_version") != sensor_version for s in sensors)):
        raise ValueError("Camera and sensors must use matching schemas")
    if set(metadata.get("simulated_fields", [])) != set(simulated_fields):
        raise ValueError("Metadata must identify all simulated sensor fields")
    if two_hands and metadata.get("schema_version") != "smartwear.sensors_meta.v2":
        raise ValueError("Expected two-hand sensor metadata")
    if metadata.get("sensors_sha256", sensor_hash) != sensor_hash:
        raise ValueError("Sensor file SHA-256 mismatch")
    if (metadata.get("sample_count") != len(sensors)
            or metadata.get("first_timestamp_ms") != sensors[0]["timestamp_ms"]
            or metadata.get("last_timestamp_ms") != sensors[-1]["timestamp_ms"]):
        raise ValueError("Sensor count or time range does not match metadata")

    encoded = []
    for index, (frame, sensor) in enumerate(zip(frames, sensors)):
        timestamp = frame["timestamp_ms"]
        if sensor["timestamp_ms"] != timestamp:
            raise ValueError(f"Timestamp mismatch at row {index}: camera={timestamp}, "
                             f"sensors={sensor['timestamp_ms']}")
        if type(frame.get("frame_id")) is not int or frame["frame_id"] != index:
            raise ValueError("Expected normalized camera frame_id starting at 0")
        if (not isinstance(frame.get("camera"), dict)
                or not isinstance(frame.get("hands"), list)
                or frame.get("relative_time_s") != round(timestamp / 1000, 3)):
            raise ValueError(f"Invalid normalized camera frame at row {index}")
        if two_hands:
            if any(frame["hand_actions"][side]["tracking_status"] !=
                   sensor["hand_sensors"][side]["tracking_status"] for side in SIDES):
                raise ValueError(f"Camera and sensor hand status mismatch at row {index}")
            channels = {"hand_actions": frame["hand_actions"],
                        "action_origin": frame["action_origin"],
                        "imu_head": sensor["imu_head"], "hand_sensors": sensor["hand_sensors"]}
        else:
            channels = {"action_estimate": frame["action_estimate"],
                        **{field: sensor[field] for field in SENSOR_FIELDS}}
        row = {
            "schema_version": "smartwear.multimodal.v2" if two_hands else "smartwear.multimodal.v1",
            "frame_id": frame["frame_id"],
            "timestamp_ms": timestamp,
            "relative_time_s": frame["relative_time_s"],
            "camera": frame["camera"],
            "hands": frame["hands"],
            **channels,
            "provenance": {
                "hands": "camera_landmarks",
                "action_estimate": "camera_landmarks_heuristic",
                "sensors": "simulated_from_camera_observations",
                "simulated_fields": simulated_fields,
                "time_alignment": "exact_camera_timestamp_copy",
                "camera_sha256": camera_hash,
                "sensors_sha256": sensor_hash,
            },
        }
        if two_hands:
            row["provenance"].pop("action_estimate")
            row["provenance"].update(hand_actions="camera_landmarks_heuristic",
                                      hand_identity="camera_recorded_handedness")
        if "video_frame_index" in frame:
            if type(frame["video_frame_index"]) is not int or frame["video_frame_index"] != index:
                raise ValueError("Invalid camera/video frame mapping")
            row["video_frame_index"] = frame["video_frame_index"]
        encoded.append(json.dumps(row, ensure_ascii=False, allow_nan=False))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as target:
        for line in encoded:
            target.write(line + "\n")
    return len(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-file", required=True, type=Path)
    parser.add_argument("--sensor-file", required=True, type=Path)
    parser.add_argument("--sensor-metadata", type=Path,
                        help="Defaults to the sensor file's .meta.json sidecar")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        count = build_multimodal(args.camera_file, args.sensor_file,
                                 args.output, args.sensor_metadata)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created {args.output.resolve()}: {count} multimodal frames")
    print("Camera actions are estimates; IMU, force/EMG and torque are simulated.")


if __name__ == "__main__":
    main()
