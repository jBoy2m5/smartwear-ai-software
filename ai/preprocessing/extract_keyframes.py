"""Export a real video frame near each observed action segment's time midpoint."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video_recording import sha256_file
from preprocessing.segment_actions import segment_frames


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def select_keyframes(frames, segments):
    entries = []
    for segment in segments:
        entry = {"segment_id": segment["segment_id"], "hand": segment.get("hand", "unspecified"),
                 "label": segment["label"], "start_ms": segment["start_ms"],
                 "end_ms": segment["end_ms"], "status": "skipped", "image_path": None}
        if segment["label"] == "NO_HAND":
            entry["reason"] = "no_hand"
        elif segment.get("tracking_status", "detected") != "detected":
            entry["reason"] = "ambiguous_hand"
        elif segment["label"] == "OTHER":
            entry["reason"] = "unknown_action"
        else:
            first, last = segment["start_frame_id"], segment["end_frame_id"]
            midpoint = (frames[first]["timestamp_ms"] + frames[last]["timestamp_ms"]) / 2
            chosen = min(frames[first:last + 1],
                         key=lambda f: (abs(f["timestamp_ms"] - midpoint), f["frame_id"]))
            entry.update(status="selected", frame_id=chosen["frame_id"],
                         timestamp_ms=chosen["timestamp_ms"])
        entries.append(entry)
    return entries


def extract_keyframes(camera_file, multimodal_file, segments_file, output_file):
    camera_file, multimodal_file, segments_file, output_file = map(
        Path, (camera_file, multimodal_file, segments_file, output_file))
    images_dir = output_file.with_suffix("")
    if output_file.suffix != ".json":
        raise ValueError("Keyframe output must be a .json file")
    if output_file.exists() or images_dir.exists():
        raise FileExistsError("Keyframe output or image directory already exists")
    frames = read_rows(multimodal_file)
    raw = read_rows(camera_file)
    segmentation = json.loads(segments_file.read_text(encoding="utf-8"))
    if segmentation.get("source_sha256") != sha256_file(multimodal_file):
        raise ValueError("Segments belong to a different multimodal file")
    if segmentation.get("segments") != segment_frames(frames, segmentation["max_gap_ms"]):
        raise ValueError("Segment boundaries do not match the camera labels")
    if len(raw) != len(frames) or any(r["timestamp"] != f["timestamp_ms"] for r, f in zip(raw, frames)):
        raise ValueError("Raw camera and multimodal frames do not match")
    entries = select_keyframes(frames, segmentation["segments"])
    document = {
        "schema_version": "smartwear.keyframes.v1",
        "camera_file": str(camera_file.resolve()), "camera_sha256": sha256_file(camera_file),
        "multimodal_sha256": sha256_file(multimodal_file),
        "segments_sha256": sha256_file(segments_file),
        "selection_method": "nearest_observed_time_midpoint; earlier frame wins ties",
        "image_content": "full mirrored camera frame without overlay; not a hand crop",
        "entries": entries,
    }
    manifest_file = camera_file.with_suffix(".video.json")
    has_mapping = any("video_frame_index" in row for row in raw + frames)
    if not manifest_file.exists():
        if has_mapping:
            raise FileNotFoundError(f"Recording has video indices but metadata is missing: {manifest_file}")
        # Legacy landmark-only sessions remain usable; no fabricated images.
        for entry in entries:
            entry.update(status="skipped", reason="no_recorded_video", image_path=None)
        document.update(status="skipped_no_video", extracted_count=0, skipped_count=len(entries))
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2)
        return document

    metadata = json.loads(manifest_file.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != "smartwear.recording_video.v1":
        raise ValueError("Unsupported recording video metadata")
    video_name = metadata.get("video_file")
    if not isinstance(video_name, str) or Path(video_name).name != video_name or "\\" in video_name or "/" in video_name:
        raise ValueError("Video must be a filename next to its camera recording")
    video_file = camera_file.parent / video_name
    if metadata.get("camera_sha256") != document["camera_sha256"]:
        raise ValueError("Video metadata belongs to a different camera recording")
    if metadata.get("video_sha256") != sha256_file(video_file):
        raise ValueError("Recorded video SHA-256 mismatch")
    if metadata.get("frame_count") != len(frames):
        raise ValueError("Video metadata frame count mismatch")
    size = (metadata["frame_width"], metadata["frame_height"])
    for index, (r, f) in enumerate(zip(raw, frames)):
        if (type(r.get("video_frame_index")) is not int or r["video_frame_index"] != index
                or type(f.get("video_frame_index")) is not int or f["video_frame_index"] != index
                or r["hands"] != f["hands"] or r.get("hand_actions") != f.get("hand_actions")
                or r["camera"] != f["camera"]
                or (r["camera"]["frame_width"], r["camera"]["frame_height"]) != size):
            raise ValueError(f"Camera/video association mismatch at frame {index}")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Trich anh can OpenCV; dung cung Python da chay camera.") from exc
    capture = cv2.VideoCapture(str(video_file))
    try:
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open recorded video: {video_file}")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        requested = {}
        for entry in entries:
            if entry["status"] == "selected":
                requested.setdefault(entry["frame_id"], []).append(entry)
        with tempfile.TemporaryDirectory(prefix=".keyframes_", dir=output_file.parent) as scratch:
            staging = Path(scratch) / "images"
            staging.mkdir()
            count = 0
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                if count >= len(frames) or (image.shape[1], image.shape[0]) != size:
                    raise ValueError("Decoded video frames do not match the recording")
                for entry in requested.get(count, []):
                    name = f"segment_{entry['segment_id']:04d}_{entry['hand']}_{entry['label']}_frame_{count:06d}.png"
                    ok, png = cv2.imencode(".png", image)
                    if not ok:
                        raise RuntimeError("Could not encode keyframe PNG")
                    with (staging / name).open("xb") as stream:
                        stream.write(png.tobytes())
                    entry.update(status="extracted", video_frame_index=count,
                                 image_path=f"{images_dir.name}/{name}")
                count += 1
            if count != len(frames):
                raise ValueError(f"Video is incomplete: decoded {count}, expected {len(frames)} frames")
            # Publish images only after all frames have been decoded and checked.
            staging.rename(images_dir)
    finally:
        capture.release()
    document.update(status="completed", video_file=str(video_file.resolve()),
                    video_sha256=metadata["video_sha256"],
                    extracted_count=sum(e["status"] == "extracted" for e in entries),
                    skipped_count=sum(e["status"] == "skipped" for e in entries))
    with output_file.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-file", type=Path, required=True)
    parser.add_argument("--multimodal-file", type=Path, required=True)
    parser.add_argument("--segments-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = extract_keyframes(args.camera_file, args.multimodal_file, args.segments_file, args.output)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    if result["status"] == "skipped_no_video":
        print("Ban ghi cu khong co video: bo qua trich anh.")
    else:
        print(f"Extracted {result['extracted_count']} keyframes; skipped {result['skipped_count']} segments")


if __name__ == "__main__":
    main()
