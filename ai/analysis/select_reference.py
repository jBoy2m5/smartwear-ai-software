"""Choose the closest bundled demo reference for a newly recorded worker session."""

import json
import math
from pathlib import Path

from analysis.compare_sessions import SIDES, build_comparison


def selection_cost(document):
    """Rank demos; this number is for sample selection, not worker assessment."""
    total, weight = 0.0, 0
    for side in SIDES:
        track = document["hands"][side]
        if track["status"] != "compared":
            # No hand in either video is a match, not a missing action.
            if track["expert_segments"] or track["worker_segments"]:
                total += 1.5
            continue
        n, m = track["expert_segments"], track["worker_segments"]
        side_weight = min(n, m)
        total += side_weight * (track["normalized_dtw_cost"]
                                + 0.2 * abs(math.log((n + 1) / (m + 1))))
        weight += side_weight
    return round(total / max(1, weight), 4)


def select_reference(worker_session, reference_root, output=None, sample_id=None,
                     right_only=False):
    worker_session = Path(worker_session).resolve()
    reference_root = Path(reference_root).resolve()
    output = Path(output).resolve() if output else worker_session / "analysis_result.json"
    if output.parent != worker_session:
        raise ValueError("Analysis result must be inside the worker session")
    if output.exists():
        raise FileExistsError(f"Analysis result already exists: {output}")
    choices = []
    for candidate in sorted(reference_root.iterdir()) if reference_root.is_dir() else []:
        if sample_id is not None and candidate.name != sample_id:
            continue
        info_path = candidate / "reference_sample.json"
        if not candidate.is_dir() or not info_path.is_file():
            continue
        info = json.loads(info_path.read_text(encoding="utf-8"))
        if info.get("schema_version") != "smartwear.demo_reference.v1":
            raise ValueError(f"Invalid demo reference metadata: {candidate}")
        if right_only and info.get("visible_labels_by_hand", {}).get("left"):
            continue
        try:
            document = build_comparison(candidate, worker_session)
        except ValueError as exc:
            if "No comparable visible actions" in str(exc):
                continue
            raise
        choices.append((selection_cost(document), candidate.name, info, document))
    if not choices:
        raise ValueError("No usable demo reference for visible actions in this recording"
                         + (f": {sample_id}" if sample_id else ""))
    score, name, info, document = min(choices, key=lambda item: (item[0], item[1]))
    document["selected_reference"] = {
        "sample_id": name, "title": info["title"],
        "practice_instruction": info["practice_instruction"],
        "demo_only": True, "selection_cost": score,
    }
    document["reference_selection_note"] = (
        "Closest available demo clip by visible action DTW; not an expert-certified standard.")
    document["available_references"] = [
        {"sample_id": item[1], "selection_cost": item[0]} for item in choices]
    with output.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(document, target, ensure_ascii=False, allow_nan=False, indent=2)
        target.write("\n")
    return output, document["selected_reference"]
