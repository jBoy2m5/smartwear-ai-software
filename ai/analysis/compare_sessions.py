"""Compare camera action segments and aligned sensor summaries for two sessions.

This is a prototype alignment, not a calibrated quality or Muda assessment.
Sensor summaries prefer verified hardware input and identify simulated fallback.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.compare_sensors import compare_sensor_segments  # noqa: E402

SIDES = ("left", "right")
VISIBLE_LABELS = {"OPEN", "REACH", "GRAB", "ASSEMBLY", "RELEASE"}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_session(session, expected_role):
    session = Path(session).resolve()
    segments_path = session / "action_segments.json"
    multimodal_path = session / "multimodal.jsonl"
    if not session.is_dir() or not segments_path.is_file() or not multimodal_path.is_file():
        raise ValueError(f"Session is missing action_segments.json or multimodal.jsonl: {session}")
    document = json.loads(segments_path.read_text(encoding="utf-8"))
    if (document.get("schema_version") != "smartwear.action_segments.v2"
            or document.get("action_source") != "camera_landmarks_heuristic"
            or document.get("uses_simulated_sensors") is not False
            or document.get("source_sha256") != sha256_file(multimodal_path)):
        raise ValueError(f"Invalid camera-derived two-hand segmentation: {session}")
    marker = session / "session_role.json"
    if marker.exists():
        role = json.loads(marker.read_text(encoding="utf-8"))
        demo_reference = (expected_role == "expert" and role.get("role") == "demo_reference"
                          and (session / "reference_sample.json").is_file()
                          and json.loads((session / "reference_sample.json").read_text(
                              encoding="utf-8")).get("demo_only") is True)
        if (role.get("schema_version") != "smartwear.session_role.v1"
                or (role.get("role") != expected_role and not demo_reference)
                or role.get("segments_sha256") != sha256_file(segments_path)):
            raise ValueError(f"Session role or source hash does not match {expected_role}: {session}")
    segments = document.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(f"Session has no action segments: {session}")
    tracks = {side: [] for side in SIDES}
    omitted = {side: {"no_hand": 0, "no_hand_duration_ms": 0,
                      "unknown_or_ambiguous": 0,
                      "unknown_or_ambiguous_duration_ms": 0} for side in SIDES}
    previous = {side: -1 for side in SIDES}
    for segment in segments:
        if not isinstance(segment, dict) or segment.get("hand") not in SIDES:
            raise ValueError("Every segment must belong to left or right hand")
        side = segment["hand"]
        start, end, duration = (segment.get(field) for field in
                                ("start_ms", "end_ms", "duration_ms"))
        if (any(type(value) is not int for value in (start, end, duration))
                or start < previous[side] or end < start or duration != end - start):
            raise ValueError("Invalid or unordered action segment times")
        previous[side] = start
        if segment.get("tracking_status") != "detected" or segment.get("label") not in VISIBLE_LABELS:
            bucket = ("no_hand" if segment.get("label") == "NO_HAND"
                      else "unknown_or_ambiguous")
            omitted[side][bucket] += 1
            omitted[side][bucket + "_duration_ms"] += duration
            continue
        tracks[side].append({"segment_id": segment["segment_id"],
                             "label": segment["label"], "start_ms": start,
                             "end_ms": end, "duration_ms": duration})
    return session, tracks, omitted, sha256_file(segments_path)


def local_cost(expert, worker):
    if expert["label"] != worker["label"]:
        return 2.0
    a, b = expert["duration_ms"], worker["duration_ms"]
    return min(0.5, abs(math.log((a + 1) / (b + 1))) * 0.25)


def keyframe_paths(session, segments_hash):
    """Return only existing camera images belonging to this segmentation."""
    manifest = session / "keyframes.json"
    if not manifest.exists():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("segments_sha256") != segments_hash:
        raise ValueError(f"Keyframes belong to a different segmentation: {session}")
    images = {}
    for entry in data.get("entries", []):
        relative = entry.get("image_path")
        if entry.get("status") != "extracted" or not relative:
            continue
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not (session / path).is_file():
            raise ValueError(f"Invalid keyframe path: {relative}")
        images[entry["segment_id"]] = path.as_posix()
    return images


def align_track(expert, worker):
    """Segment-level DTW with diagonal, repeated-expert and repeated-worker steps."""
    if not expert or not worker:
        return {"status": "insufficient_visible_actions", "expert_segments": len(expert),
                "worker_segments": len(worker), "alignment": [], "review_candidates": []}
    rows, cols = len(expert), len(worker)
    scores = [[math.inf] * (cols + 1) for _ in range(rows + 1)]
    steps = [[None] * (cols + 1) for _ in range(rows + 1)]
    scores[0][0] = 0.0
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            choices = ((scores[i - 1][j - 1], i - 1, j - 1),
                       (scores[i - 1][j] + 0.75, i - 1, j),
                       (scores[i][j - 1] + 0.75, i, j - 1))
            best, pi, pj = min(choices, key=lambda item: item[0])
            scores[i][j] = best + local_cost(expert[i - 1], worker[j - 1])
            steps[i][j] = (pi, pj)
    pairs = []
    i, j = rows, cols
    while i and j:
        e, w = expert[i - 1], worker[j - 1]
        pairs.append({"expert_segment_id": e["segment_id"],
                      "worker_segment_id": w["segment_id"],
                      "expert_label": e["label"], "worker_label": w["label"],
                      "same_label": e["label"] == w["label"],
                      "expert_duration_ms": e["duration_ms"],
                      "worker_duration_ms": w["duration_ms"],
                      "worker_extra_ms": w["duration_ms"] - e["duration_ms"]})
        i, j = steps[i][j]
    pairs.reverse()
    candidates = []
    seen_worker = set()
    for pair in pairs:
        extra = pair["worker_extra_ms"]
        reason = ("different_visible_label" if not pair["same_label"] else
                  "longer_visible_action" if extra >= 500 and
                  pair["worker_duration_ms"] >= 1.5 * max(1, pair["expert_duration_ms"])
                  else None)
        if reason and pair["worker_segment_id"] not in seen_worker:
            candidates.append({"worker_segment_id": pair["worker_segment_id"],
                               "expert_segment_id": pair["expert_segment_id"],
                               "reason": reason, "worker_extra_ms": extra})
            seen_worker.add(pair["worker_segment_id"])
    return {"status": "compared", "expert_segments": rows, "worker_segments": cols,
            "normalized_dtw_cost": round(scores[rows][cols] / len(pairs), 4),
            "alignment": pairs, "review_candidates": candidates}


def build_comparison(expert_session, worker_session):
    expert_dir, expert, expert_omitted, expert_hash = load_session(expert_session, "expert")
    worker_dir, worker, worker_omitted, worker_hash = load_session(worker_session, "worker")
    if expert_dir == worker_dir:
        raise ValueError("Expert and worker must be different sessions")
    expert_images = keyframe_paths(expert_dir, expert_hash)
    worker_images = keyframe_paths(worker_dir, worker_hash)
    tracks = {}
    for side in SIDES:
        result = align_track(expert[side], worker[side])
        for pair in result["alignment"]:
            pair["expert_image_path"] = expert_images.get(pair["expert_segment_id"])
            pair["worker_image_path"] = worker_images.get(pair["worker_segment_id"])
        for candidate in result["review_candidates"]:
            candidate["worker_image_path"] = worker_images.get(candidate["worker_segment_id"])
        result["expert_omitted"] = expert_omitted[side]
        result["worker_omitted"] = worker_omitted[side]
        tracks[side] = result
    if all(track["status"] != "compared" for track in tracks.values()):
        raise ValueError("No comparable visible actions in either hand")
    document = {"schema_version": "smartwear.analysis_comparison.v2",
                "expert_session": expert_dir.name, "worker_session": worker_dir.name,
                "expert_segments_sha256": expert_hash, "worker_segments_sha256": worker_hash,
                "method": "segment_label_duration_dtw_per_hand_with_sensor_summary",
                "score_note": "DTW cost ranks visible camera actions only; sensor values are reported separately.",
                "review_note": "Candidates need video review; they are not confirmed waste or mistakes.",
                "hands": tracks}
    sensor_result = compare_sensor_segments(expert_dir, worker_dir, document)
    document["sensor_comparison"] = sensor_result
    document["uses_simulated_sensors"] = sensor_result["status"] == "simulated_demo_comparison" or any(
        source["source"] != "measured_hardware" for source in
        (sensor_result["expert_source"], sensor_result["worker_source"]))
    return document


def compare_sessions(expert_session, worker_session, output=None):
    worker_dir = Path(worker_session).resolve()
    output = Path(output).resolve() if output else worker_dir / "analysis_result.json"
    if output.parent != worker_dir:
        raise ValueError("Analysis result must be inside the worker session")
    document = build_comparison(expert_session, worker_session)
    with output.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(document, target, ensure_ascii=False, allow_nan=False, indent=2)
        target.write("\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expert-session", type=Path, required=True)
    parser.add_argument("--worker-session", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        help="Optional filename inside worker session; defaults to analysis_result.json")
    args = parser.parse_args()
    try:
        output = compare_sessions(args.expert_session, args.worker_session, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Cannot compare sessions: {exc}\n")
    print(f"Saved camera-only comparison: {output}")


if __name__ == "__main__":
    main()
