"""Normalize a recorded camera session and retain camera-derived hand actions."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
from hand_observation import TwoHandActionDetector, validate_hand_actions  # noqa: E402


def normalize_camera_data(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output must be different files")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detector = TwoHandActionDetector()
    frame_id = 0
    previous_ms = -1
    # Exclusive creation protects both older normalized data and new recordings.
    with input_path.open("r", encoding="utf-8") as source, \
         output_path.open("x", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            data = json.loads(line)
            timestamp_ms = data["timestamp"]
            if type(timestamp_ms) is not int or timestamp_ms <= previous_ms:
                raise ValueError("Camera timestamps must be increasing integers")
            hands = data["hands"]
            version = data.get("schema_version")
            if version not in (None, "smartwear.camera_raw.v2"):
                raise ValueError(f"Unsupported raw camera schema: {version}")
            recomputed = detector.update(timestamp_ms, hands)
            # Old aggregate labels cannot be attributed to either hand. Recompute
            # from the original landmarks and handedness instead of duplicating.
            actions = data["hand_actions"] if version == "smartwear.camera_raw.v2" else recomputed
            validate_hand_actions(actions, hands)
            normalized = {
                "schema_version": "smartwear.camera.v2",
                "frame_id": frame_id,
                "timestamp_ms": timestamp_ms,
                "relative_time_s": round(timestamp_ms / 1000, 3),
                "camera": data["camera"],
                "hands": hands,
                "hand_actions": actions,
                "action_origin": "recorded_per_hand" if version else "recomputed_from_legacy_landmarks",
            }
            target.write(json.dumps(normalized, ensure_ascii=False, allow_nan=False) + "\n")
            previous_ms = timestamp_ms
            frame_id += 1
    if frame_id == 0:
        raise ValueError("Camera file is empty")
    return frame_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "ai" / "camera_data.jsonl")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "data" / "processed" / f"{args.input.stem}.normalized.jsonl"
    try:
        count = normalize_camera_data(args.input, output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created {output.resolve()}: {count} camera frames with action estimates")


if __name__ == "__main__":
    main()
