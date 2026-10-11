"""Analyze a user-supplied video without opening devices or simulating sensors."""
import argparse
import json
import math
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from camera_test import MODEL_PATH, TwoHandActionDetector, make_frame_data
from video_recording import RecordingVideo, sha256_file
from preprocessing.normalize_camera import normalize_camera_data
from preprocessing.segment_actions import segment_file
from preprocessing.extract_keyframes import extract_keyframes
from integration.frontend_capture import write_status, encode_and_publish_preview
from integration.backend_bridge import (encoded, phases_for, request_json, publish_recording,
                                       publish_source_data)

MAX_DURATION_S = 180
ANALYSIS_HZ = 10
SENSOR_SOURCE = "missing_from_uploaded_video"


def process_video(source, session, job_dir):
    import cv2
    import mediapipe as mp

    if not MODEL_PATH.is_file():
        raise ValueError("Thiếu model hand_landmarker.task; cần đóng gói model trước khi chạy offline.")
    source, session, job_dir = map(Path, (source, session, job_dir))
    capture = cv2.VideoCapture(str(source))
    video = None
    try:
        if not capture.isOpened():
            raise ValueError("Không đọc được video; hãy dùng MP4 H.264, MOV, AVI hoặc WebM hợp lệ.")
        fps = capture.get(cv2.CAP_PROP_FPS)
        expected = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or not 1 <= fps <= 120:
            raise ValueError("Không xác định được tốc độ video (hỗ trợ 1–120 FPS).")
        if math.isfinite(expected) and expected > 0 and expected / fps > MAX_DURATION_S + .1:
            raise ValueError("Video tối đa 3 phút; hãy cắt video trước khi tải lên.")
        session.mkdir()
        original = session / ("source_video" + source.suffix.lower())
        shutil.copyfile(source, original)
        output = session / "camera.jsonl"
        video = RecordingVideo(output, cv2)
        video.fps = ANALYSIS_HZ
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=.5, min_hand_presence_confidence=.5,
            min_tracking_confidence=.5)
        detector = TwoHandActionDetector()
        decoded = 0
        previous_pts = -1.
        last_sample = -100
        fallback_times = 0
        preview_at = 0.
        started = time.monotonic()
        original_size = None
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker, \
                output.open("x", encoding="utf-8", newline="\n") as stream:
            while True:
                if (job_dir / "stop.flag").exists():
                    raise RuntimeError("Đã hủy phân tích; video và dữ liệu đã xử lý được giữ lại.")
                if time.monotonic() - started > 600:
                    raise RuntimeError("Phân tích vượt 10 phút; hãy thử video ngắn hơn.")
                ok, frame = capture.read()
                if not ok:
                    break
                if frame is None or not frame.size:
                    raise ValueError("Video chứa khung hình không hợp lệ.")
                width, height = frame.shape[1], frame.shape[0]
                if width * height > 1920 * 1080:
                    raise ValueError("Video tối đa Full HD (1920×1080); hãy giảm độ phân giải.")
                if original_size is None:
                    original_size = (width, height)
                elif original_size != (width, height):
                    raise ValueError("Độ phân giải video thay đổi giữa phiên.")
                pts = capture.get(cv2.CAP_PROP_POS_MSEC)
                if not math.isfinite(pts) or pts < 0 or pts <= previous_pts:
                    pts = decoded * 1000 / fps
                    fallback_times += 1
                if pts <= previous_pts:
                    raise ValueError("Mốc thời gian video không tăng; hãy chuyển sang MP4 H.264.")
                previous_pts = pts
                decoded += 1
                if pts > MAX_DURATION_S * 1000 or decoded > MAX_DURATION_S * 120 + 1:
                    raise ValueError("Video tối đa 3 phút.")
                timestamp = round(pts)
                if timestamp - last_sample < 100:
                    continue
                last_sample = timestamp
                # Reuse the mirrored-camera handedness convention. Preserve the
                # unmodified input separately and record this transform explicitly.
                scale = min(1., 960 / width, 540 / height)
                size = (max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2))
                if size != (width, height):
                    frame = cv2.resize(frame, size)
                frame = cv2.flip(frame, 1)
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = landmarker.detect_for_video(image, timestamp)
                data = make_frame_data(result, timestamp, *size, detector)
                data["video_frame_index"] = video.write(frame)
                stream.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n")
                if time.monotonic() - preview_at >= .4:
                    stream.flush()
                    write_status(job_dir, "processing", f"Đang phân tích video · {timestamp/1000:.1f} s")
                    encode_and_publish_preview(cv2, frame, data, job_dir)
                    preview_at = time.monotonic()
        if not decoded:
            raise ValueError("Video không có khung hình đọc được.")
        if math.isfinite(expected) and expected > 0 and decoded + 1 < expected:
            raise ValueError("Video bị cắt hoặc lỗi giải mã; chưa đọc đủ khung hình.")
        video.close()
        video.save_manifest()
        manifest = {"schema_version": "smartwear.uploaded_video/1", "source_kind": "uploaded_video",
                    "status": "complete", "original_file": original.name,
                    "original_sha256": sha256_file(original), "original_size_bytes": original.stat().st_size,
                    "decoded_frames": decoded, "analyzed_frames": video.frame_count,
                    "original_width": original_size[0], "original_height": original_size[1],
                    "declared_fps": fps, "duration_s": (previous_pts + 1000/fps)/1000,
                    "analysis_hz_limit": ANALYSIS_HZ, "analysis_max_size": [960, 540],
                    "mirrored_for_analysis": True, "clock_domain": "uploaded_video_relative",
                    "timestamp_method": "decoder_POS_MSEC; frame_index/declared_fps fallback",
                    "fallback_timestamp_frames": fallback_times, "sensor_source": SENSOR_SOURCE,
                    "robot_action_available": False, "consent_confirmed": True}
        (session / "uploaded_video.json").write_bytes(encoded(manifest))
        return output
    finally:
        capture.release()
        if video is not None:
            video.close()


def finish_video(output):
    """Reuse camera segmentation/keyframes with explicit null sensor slots."""
    session = Path(output).parent
    normalized = session / "camera.normalized.jsonl"
    normalize_camera_data(output, normalized)
    frames = [json.loads(line) for line in normalized.read_text(encoding="utf-8").splitlines()]
    sensors = []
    combined = []
    for frame in frames:
        hands = {side: {"tracking_status": frame["hand_actions"][side]["tracking_status"],
                       "imu_wrist": None, "force_emg_raw": None, "force_adc": None, "torque": None}
                 for side in ("left", "right")}
        sensors.append({"schema_version": "smartwear.sensors.v2", "timestamp_ms": frame["timestamp_ms"],
                        "sensor_source": SENSOR_SOURCE, "imu_head": None, "hand_sensors": hands})
        combined.append({**frame, "schema_version": "smartwear.multimodal.v2",
                         "imu_head": None, "hand_sensors": hands,
                         "provenance": {"hands": "camera_landmarks", "hand_actions": "camera_landmarks_heuristic",
                                        "sensors": SENSOR_SOURCE, "simulated_fields": [],
                                        "clock_domain": "uploaded_video_relative"}})
    for name, rows in (("real_sensors.jsonl", sensors), ("multimodal.jsonl", combined)):
        with (session / name).open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    (session / "real_sensors.meta.json").write_bytes(encoded({
        "schema_version": "smartwear.sensors_meta.v2", "source": SENSOR_SOURCE,
        "sample_count": len(frames), "matched_count": 0, "missing_count": len(frames),
        "camera_sha256": sha256_file(normalized), "sensors_sha256": sha256_file(session / "real_sensors.jsonl"),
        "simulated_fields": [], "reason": "No sensor stream was supplied with this uploaded video"}))
    segment_file(session / "multimodal.jsonl", session / "action_segments.json")
    extract_keyframes(output, session / "multimodal.jsonl", session / "action_segments.json", session / "keyframes.json")
    (session / "session_role.json").write_bytes(encoded({"schema_version": "smartwear.session_role.v1",
        "role": "video_observation", "segments_sha256": sha256_file(session / "action_segments.json")}))
    return frames


def publish_video(session, frames, backend_url):
    segments = json.loads((session / "action_segments.json").read_text(encoding="utf-8"))["segments"]
    keys = json.loads((session / "keyframes.json").read_text(encoding="utf-8"))
    images = [session / entry["image_path"] for entry in keys["entries"] if entry["status"] == "extracted"]
    payload = {"session_id": "VIDEO_" + session.name, "worker_type": "TRAINEE",
               "key_frames": [p.name for p in images], "action_phases": phases_for(segments, frames, measured=True),
               "dtw_metrics": {"similarity_score": 0., "muda_detected_seconds": 0.},
               "robot_trajectory_points": []}
    (session / "backend_payload_video.json").write_bytes(encoded(payload))
    root = backend_url.rstrip("/") + "/api/v1/sessions"
    key = os.getenv("SMARTWEAR_API_KEY")
    request_json(root + "/ingest", "POST", encoded(payload), key)
    for image in images:
        request_json(root + "/" + payload["session_id"] + "/keyframes/" + image.name,
                     "PUT", image.read_bytes(), key, "image/png")
    publish_recording(session, payload, backend_url, key)
    publish_source_data(session, payload, backend_url, key)
    return payload["session_id"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    os.environ["SMARTWEAR_CAPTURE_MODE"] = "upload"
    session = args.job_dir / args.job_dir.name
    try:
        write_status(args.job_dir, "starting", "Đang kiểm tra video và chuẩn bị AI")
        output = process_video(args.input, session, args.job_dir)
        if (args.job_dir / "stop.flag").exists():
            raise RuntimeError("Đã hủy phân tích; video được giữ lại.")
        write_status(args.job_dir, "processing", "Đang phân đoạn hành động và trích keyframe")
        frames = finish_video(output)
        if (args.job_dir / "stop.flag").exists():
            raise RuntimeError("Đã hủy phân tích; video và kết quả tạm được giữ lại.")
        write_status(args.job_dir, "publishing", "Đang lưu kết quả video; không có dữ liệu lực/IMU")
        session_id = publish_video(session, frames, args.backend_url)
        write_status(args.job_dir, "completed", "Đã phân tích video; chưa có mẫu so sánh hoặc dữ liệu cảm biến", session_id)
        return 0
    except Exception as exc:
        write_status(args.job_dir, "failed", str(exc))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
