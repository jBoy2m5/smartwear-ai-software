"""Rebuild legacy demo references with anatomical left/right labels.

The original camera/video data are retained in a backup directory. This is a
one-time migration for references recorded before the mirrored-camera fix.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
from analysis.compare_sessions import load_session, sha256_file  # noqa: E402
from hand_observation import anatomical_handedness, validate_hand_actions  # noqa: E402
from process_recording import process_recording  # noqa: E402

GENERATED = AI_DIR / "generated_data"
REFERENCES = GENERATED / "reference_samples"
BACKUP = GENERATED / "legacy_handedness_references"
SPECS = (
    ("01_two_hands_reach_grab", "01_two_hands_reach_grab",
     "Hai tay đưa tới và nắm",
     "Đưa hai bàn tay vào khung hình; mở tay, đưa tới trước, rồi nắm cả hai tay. Sau đó mở tay phải."),
    ("02_right_hand_grab_hold", "02_left_hand_grab_hold",
     "Tay trái giữ lâu, tay phải rời khung",
     "Bắt đầu với hai tay nắm. Đưa tay phải khỏi khung hình, còn tay trái tiếp tục nắm và giữ một lúc."),
    ("04_left_grab_hold_release_open", "04_right_grab_hold_release_open",
     "Tay phải nắm, giữ, thả và mở",
     "Chỉ đưa tay phải vào hình: nắm, giữ tay nắm gần như đứng yên, "
     "di chuyển tay nắm nhẹ, thả rồi mở và giữ mở. "
     "Nhãn ASSEMBLY chỉ là camera suy đoán tư thế giữ, không phải lắp ráp thật."),
)


def _inside(path, root):
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path outside expected directory: {path}")


def _write_json(path, document):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def correct_legacy_row(row):
    """Swap the two anatomical labels in a legacy mirrored-camera row."""
    if row.get("schema_version") != "smartwear.camera_raw.v2":
        raise ValueError("Only two-hand raw camera data can be corrected")
    if any(hand.get("handedness_convention") for hand in row["hands"]):
        raise ValueError("Camera row already declares a handedness convention")
    for hand in row["hands"]:
        old_side = hand["handedness"]
        hand["handedness"] = anatomical_handedness(old_side)
        hand["model_handedness"] = old_side
        hand["handedness_convention"] = "anatomical_from_mirrored_camera"
    actions = row["hand_actions"]
    row["hand_actions"] = {"left": actions["right"], "right": actions["left"]}
    validate_hand_actions(row["hand_actions"], row["hands"])
    return row


def _prepare(old, staged, title, instruction, staging_root):
    source_raw = old / "camera.jsonl"
    source_video = old / "camera.avi"
    source_manifest = old / "camera.video.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    if (manifest["camera_sha256"] != sha256_file(source_raw)
            or manifest["video_sha256"] != sha256_file(source_video)):
        raise ValueError(f"Original camera/video hashes do not match: {old}")
    staged.mkdir(exist_ok=False)
    raw = staged / "camera.jsonl"
    count = 0
    with source_raw.open(encoding="utf-8") as source, \
            raw.open("x", encoding="utf-8", newline="\n") as target:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            correct_legacy_row(row)
            target.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            count += 1
    if count != manifest["frame_count"]:
        raise ValueError(f"Frame count changed while migrating {old}")
    shutil.copy2(source_video, staged / "camera.avi")
    manifest["camera_sha256"] = sha256_file(raw)
    manifest["handedness_convention"] = "anatomical_from_mirrored_camera"
    _write_json(staged / "camera.video.json", manifest)
    process_recording(raw, output_root=staging_root, session_dir=staged)
    segments = staged / "action_segments.json"
    _write_json(staged / "session_role.json", {
        "schema_version": "smartwear.session_role.v1", "role": "demo_reference",
        "segments_sha256": sha256_file(segments)})
    info = json.loads((old / "reference_sample.json").read_text(encoding="utf-8"))
    segment_doc = json.loads(segments.read_text(encoding="utf-8"))
    info.update(title=title, practice_instruction=instruction,
                handedness_convention="anatomical_from_mirrored_camera",
                visible_labels_by_hand={side: [item["label"] for item in segment_doc["segments"]
                                              if item["hand"] == side
                                              and item["tracking_status"] == "detected"
                                              and item["label"] not in ("OTHER", "NO_HAND")]
                                        for side in ("left", "right")})
    _write_json(staged / "reference_sample.json", info)
    load_session(staged, "expert")


def migrate():
    REFERENCES.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix="handedness_staging_", dir=GENERATED))
    prepared = []
    for old_name, new_name, title, instruction in SPECS:
        old, staged, target = (REFERENCES / old_name, staging_root / new_name,
                               REFERENCES / new_name)
        for path, root in ((old, REFERENCES), (staged, staging_root),
                           (target, REFERENCES), (BACKUP / old_name, BACKUP)):
            _inside(path, root)
        if not old.is_dir() or (BACKUP / old_name).exists() or (target.exists() and target != old):
            raise FileExistsError(f"Missing original or destination already exists: {old_name}")
        _prepare(old, staged, title, instruction, staging_root)
        prepared.append((old, staged, target, BACKUP / old_name))
    for old, staged, target, backup in prepared:
        old.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            backup.rename(old)
            raise
        print(f"Corrected reference: {target}; original saved: {backup}")


def refresh_reference_metadata():
    """Update provenance generated before hand_identity named the corrected label."""
    for reference in sorted(REFERENCES.iterdir()):
        if not reference.is_dir():
            continue
        info = json.loads((reference / "reference_sample.json").read_text(encoding="utf-8"))
        if info.get("handedness_convention") != "anatomical_from_mirrored_camera":
            raise ValueError(f"Reference has uncorrected handedness: {reference}")
        multimodal = reference / "multimodal.jsonl"
        segments = reference / "action_segments.json"
        keyframes = reference / "keyframes.json"
        marker = reference / "session_role.json"
        old_multi_hash, old_segments_hash = sha256_file(multimodal), sha256_file(segments)
        segment_doc = json.loads(segments.read_text(encoding="utf-8"))
        keyframe_doc = json.loads(keyframes.read_text(encoding="utf-8"))
        role_doc = json.loads(marker.read_text(encoding="utf-8"))
        if (segment_doc["source_sha256"] != old_multi_hash
                or keyframe_doc["multimodal_sha256"] != old_multi_hash
                or keyframe_doc["segments_sha256"] != old_segments_hash
                or role_doc["segments_sha256"] != old_segments_hash):
            raise ValueError(f"Reference hashes were already inconsistent: {reference}")
        rows = [json.loads(line) for line in multimodal.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        if any(row["provenance"].get("hand_identity") != "mediapipe_handedness"
               for row in rows):
            continue
        with multimodal.open("w", encoding="utf-8", newline="\n") as target:
            for row in rows:
                row["provenance"]["hand_identity"] = "camera_recorded_handedness"
                target.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        new_multi_hash = sha256_file(multimodal)
        segment_doc["source_sha256"] = new_multi_hash
        segment_doc["hand_identity"] = "camera_recorded_handedness"
        with segments.open("w", encoding="utf-8", newline="\n") as target:
            json.dump(segment_doc, target, ensure_ascii=False, allow_nan=False, indent=2)
            target.write("\n")
        new_segments_hash = sha256_file(segments)
        keyframe_doc["multimodal_sha256"] = new_multi_hash
        keyframe_doc["segments_sha256"] = new_segments_hash
        with keyframes.open("w", encoding="utf-8", newline="\n") as target:
            json.dump(keyframe_doc, target, ensure_ascii=False, allow_nan=False, indent=2)
            target.write("\n")
        role_doc["segments_sha256"] = new_segments_hash
        with marker.open("w", encoding="utf-8", newline="\n") as target:
            json.dump(role_doc, target, ensure_ascii=False, allow_nan=False, indent=2)
            target.write("\n")
        load_session(reference, "expert")
        print(f"Refreshed corrected-side provenance: {reference.name}")


if __name__ == "__main__":
    migrate()
