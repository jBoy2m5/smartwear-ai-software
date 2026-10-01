"""Run the existing two-hand camera pipeline for a dashboard-controlled session."""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from camera_test import finish_recording, record_camera  # noqa: E402
from integration.backend_bridge import publish  # noqa: E402


def write_status(job_dir, stage, message, session_id=None):
    document = {"stage": stage, "message": message, "session_id": session_id,
                "updated_at": datetime.now(timezone.utc).isoformat()}
    temporary = job_dir / "status.tmp"
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False)
    os.replace(temporary, job_dir / "status.json")


def publish_preview(job_dir, jpeg_bytes, frame_index, keep=20):
    """Publish a complete, uniquely named frame without replacing a served JPEG."""
    name = f"preview_{frame_index:08d}"
    temporary = job_dir / f"{name}.tmp"
    temporary.write_bytes(jpeg_bytes)
    os.replace(temporary, job_dir / f"{name}.jpg")
    for old in sorted(job_dir.glob("preview_*.jpg"))[:-keep]:
        try:
            old.unlink()
        except PermissionError:
            # A browser response may still be reading this older frame on Windows.
            pass


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

    def preview(cv2, frame, data):
        nonlocal last_preview, preview_error_logged
        now = time.monotonic()
        if now - last_preview < 0.15:
            return
        success, encoded = cv2.imencode(".jpg", frame,
                                        [cv2.IMWRITE_JPEG_QUALITY, 78])
        if success:
            try:
                publish_preview(job_dir, encoded.tobytes(), data["video_frame_index"])
            except OSError as exc:
                # Losing the live preview must not abort a recording or its analysis.
                if not preview_error_logged:
                    print(f"Camera preview unavailable: {exc}", file=sys.stderr)
                    preview_error_logged = True
            last_preview = now

    try:
        write_status(job_dir, "recording", "Camera đang ghi hai tay")
        started = time.monotonic()
        output = record_camera(stop_requested=lambda: (job_dir / "stop.flag").exists()
                               or time.monotonic() - started >= 180,
                               on_frame=preview, show_window=False)
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
