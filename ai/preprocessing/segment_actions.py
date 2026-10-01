"""Group consecutive camera action estimates into time segments."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hand_observation import SIDES, validate_hand_actions

LABELS = {"OPEN", "REACH", "GRAB", "ASSEMBLY", "RELEASE", "OTHER", "NO_HAND"}
STATES = {"OPEN", "CLOSED", "OTHER", "NONE"}


def _segment_single_track(frames, max_gap_ms=500):
    """Keep every frame; split at label changes or gaps above max_gap_ms.

    A normal boundary ends at the first sample of the next label. At a gap or
    end of recording, stop at the last observed timestamp; never extrapolate.
    """
    if type(max_gap_ms) is not int or max_gap_ms <= 0:
        raise ValueError("max_gap_ms must be a positive integer")
    if not frames:
        raise ValueError("Multimodal input is empty")
    previous_time = -1
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict) or frame.get("schema_version") != "smartwear.multimodal.v1":
            raise ValueError(f"Expected smartwear.multimodal.v1 at row {index}")
        timestamp = frame.get("timestamp_ms")
        if type(timestamp) is not int or timestamp <= previous_time:
            raise ValueError("Timestamps must be nonnegative, strictly increasing integers")
        if type(frame.get("frame_id")) is not int or frame["frame_id"] != index:
            raise ValueError("Expected consecutive frame_id values starting at 0")
        estimate = frame.get("action_estimate")
        if (not isinstance(estimate, dict)
                or estimate.get("source") != "camera_landmarks"
                or estimate.get("label") not in LABELS
                or estimate.get("hand_state") not in STATES):
            raise ValueError(f"Invalid camera action estimate at row {index}")
        previous_time = timestamp

    segments = []
    start = 0

    def finish(last, end_ms, reason):
        first_frame, last_frame = frames[start], frames[last]
        segments.append({
            "segment_id": len(segments),
            "label": first_frame["action_estimate"]["label"],
            "start_frame_id": first_frame["frame_id"],
            "end_frame_id": last_frame["frame_id"],
            "frame_count": last - start + 1,
            "start_ms": first_frame["timestamp_ms"],
            "last_observed_ms": last_frame["timestamp_ms"],
            "end_ms": end_ms,
            "duration_ms": end_ms - first_frame["timestamp_ms"],
            "end_reason": reason,
            "end_is_observation_limit": reason != "label_change",
        })

    for index in range(1, len(frames)):
        previous, current = frames[index - 1], frames[index]
        gap = current["timestamp_ms"] - previous["timestamp_ms"] > max_gap_ms
        changed = (current["action_estimate"]["label"] != previous["action_estimate"]["label"]
                   or current["action_estimate"].get("tracking_status") !=
                   previous["action_estimate"].get("tracking_status"))
        if gap or changed:
            finish(index - 1, previous["timestamp_ms"] if gap else current["timestamp_ms"],
                   "data_gap" if gap else "label_change")
            start = index
    finish(len(frames) - 1, frames[-1]["timestamp_ms"], "recording_end")
    return segments


def segment_frames(frames, max_gap_ms=500):
    if not frames:
        raise ValueError("Multimodal input is empty")
    versions = {frame.get("schema_version") for frame in frames if isinstance(frame, dict)}
    if len(versions) != 1 or not all(isinstance(frame, dict) for frame in frames):
        raise ValueError("Mixed or invalid multimodal schemas")
    if versions == {"smartwear.multimodal.v1"}:
        return _segment_single_track(frames, max_gap_ms)
    if versions != {"smartwear.multimodal.v2"}:
        raise ValueError("Unsupported multimodal schema")
    for frame in frames:
        validate_hand_actions(frame.get("hand_actions"), frame.get("hands"))
    segments = []
    for side in SIDES:
        track = [{"schema_version": "smartwear.multimodal.v1", "frame_id": f["frame_id"],
                  "timestamp_ms": f["timestamp_ms"], "action_estimate": f["hand_actions"][side]}
                 for f in frames]
        for segment in _segment_single_track(track, max_gap_ms):
            segment["hand"] = side
            segment["tracking_status"] = track[segment["start_frame_id"]]["action_estimate"]["tracking_status"]
            segments.append(segment)
    segments.sort(key=lambda s: (s["start_ms"], s["hand"]))
    for index, segment in enumerate(segments):
        segment["segment_id"] = index
    return segments


def segment_file(input_path, output_path, max_gap_ms=500):
    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output must differ")
    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")
    raw = input_path.read_bytes()
    frames = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    segments = segment_frames(frames, max_gap_ms)
    gaps = [{"after_frame_id": a["frame_id"], "before_frame_id": b["frame_id"],
             "start_ms": a["timestamp_ms"], "end_ms": b["timestamp_ms"],
             "duration_ms": b["timestamp_ms"] - a["timestamp_ms"]}
            for a, b in zip(frames, frames[1:])
            if b["timestamp_ms"] - a["timestamp_ms"] > max_gap_ms]
    document = {
        "schema_version": "smartwear.action_segments.v1",
        "source_file": str(input_path.resolve()),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "method": "consecutive_camera_labels",
        "action_source": "camera_landmarks_heuristic",
        "uses_simulated_sensors": False,
        "max_gap_ms": max_gap_ms,
        "frame_count": len(frames),
        "segment_count": len(segments),
        "first_timestamp_ms": frames[0]["timestamp_ms"],
        "last_timestamp_ms": frames[-1]["timestamp_ms"],
        "duration_note": "Label-change boundaries use the next frame time. Gap/end "
                         "boundaries stop at the last observation; true action end is unknown.",
        "data_gaps": gaps,
        "segments": segments,
    }
    if frames[0]["schema_version"] == "smartwear.multimodal.v2":
        document.update(schema_version="smartwear.action_segments.v2",
                        method="consecutive_camera_labels_per_hand",
                        hand_identity="camera_recorded_handedness",
                        segment_counts_by_hand={side: sum(s["hand"] == side for s in segments)
                                                for side in SIDES},
                        duration_scope="Per hand; simultaneous left/right durations must not be added")
    encoded = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as target:
        target.write(encoded + "\n")
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-gap-ms", type=int, default=500)
    args = parser.parse_args()
    try:
        result = segment_file(args.input, args.output, args.max_gap_ms)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created {args.output.resolve()}: {result['segment_count']} action segments "
          f"from {result['frame_count']} frames")


if __name__ == "__main__":
    main()
