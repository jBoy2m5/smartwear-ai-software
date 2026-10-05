"""Run right-hand camera capture for a dashboard-controlled session."""

import argparse
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from camera_test import finish_recording, record_camera  # noqa: E402
from integration.backend_bridge import publish  # noqa: E402


def write_status(job_dir, stage, message, session_id=None):
    document = {"stage": stage, "message": message, "session_id": session_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "capture_mode": os.getenv("SMARTWEAR_CAPTURE_MODE", "demo").strip().lower()}
    temporary = job_dir / "status.tmp"
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False)
    os.replace(temporary, job_dir / "status.json")


def publish_preview(job_dir, jpeg_bytes, data, keep=30):
    """Publish image and matching observation without replacing a served JPEG."""
    frame_index = data["video_frame_index"]
    name = f"preview_{frame_index:08d}"
    temporary = job_dir / f"{name}.tmp"
    temporary.write_bytes(jpeg_bytes)
    os.replace(temporary, job_dir / f"{name}.jpg")
    right_hand = next((hand for hand in data["hands"]
                       if hand["handedness"].lower() == "right"), None)
    document = {"frame_index": frame_index, "timestamp_ms": data["timestamp"],
                "camera": data["camera"],
                "right_action": data["hand_actions"]["right"],
                "right_landmarks": right_hand["landmarks"] if right_hand else []}
    if "wrist_status" in data:
        document["wrist_status"] = data["wrist_status"]
    metadata_tmp = job_dir / f"{name}.json.tmp"
    metadata_tmp.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    os.replace(metadata_tmp, job_dir / f"{name}.json")
    for old in sorted(job_dir.glob("preview_*.json"))[:-keep]:
        try:
            old.unlink()
            old.with_suffix(".jpg").unlink(missing_ok=True)
        except PermissionError:
            # A browser response may still be reading this older frame on Windows.
            pass


def encode_and_publish_preview(cv2, frame, data, job_dir):
    success, encoded = cv2.imencode(".jpg", frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 88])
    if success:
        publish_preview(job_dir, encoded.tobytes(), data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    job_dir = args.job_dir.resolve()
    if not job_dir.is_dir():
        parser.error("Capture job directory does not exist")
    last_preview = 0.0
    preview_error_logged = False
    preview_future = None

    def check_preview_error():
        nonlocal preview_error_logged
        if preview_future is None or not preview_future.done():
            return
        try:
            preview_future.result()
        except Exception as exc:
            # A failed live preview must not abort the saved camera session.
            if not preview_error_logged:
                print(f"Camera preview unavailable: {exc}", file=sys.stderr)
                preview_error_logged = True

    def preview(cv2, frame, data):
        nonlocal last_preview, preview_future
        now = time.monotonic()
        if preview_future is not None and not preview_future.done():
            return
        check_preview_error()
        if now - last_preview < 0.06:
            return
        # Only copy on the capture thread; JPEG compression and file writes run
        # separately so the next camera frame need not wait for the web preview.
        preview_future = executor.submit(encode_and_publish_preview, cv2,
                                         frame.copy(), data, job_dir)
        last_preview = now

    try:
        capture_mode = os.getenv("SMARTWEAR_CAPTURE_MODE", "demo").strip().lower()
        if capture_mode not in ("demo", "hardware"):
            raise ValueError("SMARTWEAR_CAPTURE_MODE must be demo or hardware")
        write_status(job_dir, "recording", ("Đang nhận ảnh ESP32; kiểm tra vòng tay ở hình xem trước"
                                            if capture_mode == "hardware" else
                                            "Camera đang ghi tay phải"))
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as executor:
            stop_requested = lambda: (job_dir / "stop.flag").exists() or time.monotonic() - started >= 180
            if capture_mode == "hardware":
                from hardware.record_hardware import record_hardware
                output = record_hardware(
                    camera_url=os.getenv("SMARTWEAR_CAMERA_URL", "http://192.168.0.101:81/stream"),
                    mqtt_host=os.getenv("SMARTWEAR_MQTT_HOST", "192.168.0.109"),
                    topic=os.getenv("SMARTWEAR_MQTT_TOPIC", "wearable/user01/wrist/data"),
                    force_channel=(int(os.environ["SMARTWEAR_FORCE_CHANNEL"])
                                   if os.getenv("SMARTWEAR_FORCE_CHANNEL") else None),
                    device_id=os.getenv("SMARTWEAR_WRIST_ID", "smartwrist-user01"),
                    stop_requested=stop_requested, on_frame=preview, show_window=False)
            else:
                output = record_camera(stop_requested=stop_requested,
                                       on_frame=preview, show_window=False)
        check_preview_error()
        write_status(job_dir, "processing", "Đang phân tích hành động và so với mẫu")
        finish_recording(output)
        write_status(job_dir, "publishing", "Đang lưu kết quả lên backend")
        receipt = publish(output.parent, args.backend_url, os.getenv("SMARTWEAR_API_KEY"))
        write_status(job_dir, "completed", "Đã lưu phiên và kết quả",
                     receipt["session_id"])
    except Exception as exc:
        write_status(job_dir, "failed", str(exc))
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
