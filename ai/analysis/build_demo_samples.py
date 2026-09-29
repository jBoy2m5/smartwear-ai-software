"""Cut three clearly labeled demo references from the existing camera recording.

The clips are practice examples from one previous recording, not validated
factory expert demonstrations. Run from the repository root with Python/OpenCV.
"""

import json
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
from analysis.compare_sessions import sha256_file
from process_recording import process_recording
from video_recording import RecordingVideo

SOURCE = (AI_DIR / "generated_data" / "sessions"
          / "camera_data_20260929_162510_226861_uev_uvqt")
OUTPUT_ROOT = AI_DIR / "generated_data" / "reference_samples"
# Times refer to the original camera clock. Labels are visual estimates only.
SAMPLES = (
    ("01_two_hands_reach_grab", 4312, 6323,
     "Hai tay đưa tới và nắm",
     "Đưa hai bàn tay vào khung hình; mở tay, đưa tới trước, rồi nắm cả hai tay. Sau đó mở tay trái."),
    ("02_right_hand_grab_hold", 6556, 8416,
     "Tay phải giữ lâu, tay trái rời khung",
     "Bắt đầu với hai tay nắm. Đưa tay trái khỏi khung hình, còn tay phải tiếp tục nắm và giữ một lúc."),
    ("03_left_hand_grab_release", 8586, 10873,
     "Tay trái nắm rồi mở",
     "Đưa tay trái vào khung hình, nắm lại, sau đó mở bàn tay và giữ mở một lúc."),
)


def build_samples(source=SOURCE, output_root=OUTPUT_ROOT):
    import cv2

    source, output_root = Path(source).resolve(), Path(output_root).resolve()
    manifests = list(source.glob("*.video.json"))
    if len(manifests) != 1:
        raise ValueError("Expected exactly one source video manifest")
    manifest = manifests[0]
    camera = manifest.with_name(manifest.name.removesuffix(".video.json") + ".jsonl")
    video = camera.with_suffix(".avi")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if (not camera.is_file() or not video.is_file()
            or metadata.get("camera_sha256") != sha256_file(camera)
            or metadata.get("video_sha256") != sha256_file(video)):
        raise ValueError("Source camera/video hashes do not match")
    rows = [json.loads(line) for line in camera.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if len(rows) != metadata.get("frame_count"):
        raise ValueError("Source frame count does not match metadata")
    if any((row.get("video_frame_index") != index) for index, row in enumerate(rows)):
        raise ValueError("Source camera/video mapping is incomplete")
    output_root.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, start_ms, end_ms, title, instruction in SAMPLES:
        indices = [index for index, row in enumerate(rows)
                   if start_ms <= row["timestamp"] < end_ms]
        if len(indices) < 10:
            raise ValueError(f"Too few source frames for {name}")
        session = output_root / name
        session.mkdir(exist_ok=False)
        raw = session / "camera.jsonl"
        capture = cv2.VideoCapture(str(video))
        recorder = RecordingVideo(raw, cv2)
        try:
            if not capture.isOpened():
                raise RuntimeError(f"Cannot open source video: {video}")
            with raw.open("x", encoding="utf-8", newline="\n") as target:
                for index, row in enumerate(rows):
                    ok, frame = capture.read()
                    if not ok:
                        raise ValueError("Source video ended before camera JSONL")
                    if index not in indices:
                        continue
                    copied = dict(row)
                    copied["timestamp"] = row["timestamp"] - rows[indices[0]]["timestamp"]
                    copied["video_frame_index"] = recorder.write(frame)
                    target.write(json.dumps(copied, ensure_ascii=False, allow_nan=False) + "\n")
                if capture.read()[0]:
                    raise ValueError("Source video has extra frames")
        finally:
            recorder.close()
            capture.release()
        recorder.save_manifest()
        process_recording(raw, output_root=output_root, session_dir=session)
        segments = session / "action_segments.json"
        with (session / "session_role.json").open("x", encoding="utf-8") as stream:
            json.dump({"schema_version": "smartwear.session_role.v1", "role": "demo_reference",
                       "segments_sha256": sha256_file(segments)}, stream, indent=2)
            stream.write("\n")
        segment_doc = json.loads(segments.read_text(encoding="utf-8"))
        visible = {side: [item["label"] for item in segment_doc["segments"]
                          if item["hand"] == side and item["tracking_status"] == "detected"
                          and item["label"] not in ("OTHER", "NO_HAND")]
                   for side in ("left", "right")}
        with (session / "reference_sample.json").open("x", encoding="utf-8") as stream:
            json.dump({"schema_version": "smartwear.demo_reference.v1",
                       "title": title, "practice_instruction": instruction,
                       "demo_only": True, "not_validated_expert": True,
                       "source_session": source.name,
                       "source_camera_sha256": metadata["camera_sha256"],
                       "source_video_sha256": metadata["video_sha256"],
                       "source_start_ms": rows[indices[0]]["timestamp"],
                       "source_end_ms": rows[indices[-1]]["timestamp"],
                       "frame_count": len(indices), "visible_labels_by_hand": visible},
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        outputs.append(session)
    return outputs


if __name__ == "__main__":
    for path in build_samples():
        print(f"Created demo reference: {path}")
