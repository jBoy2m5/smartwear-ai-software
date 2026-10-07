"""Record both hands from ESP32 MJPEG and the instrumented right SmartWrist."""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from camera_test import MODEL_PATH, SESSION_ROOT, draw_frame, make_frame_data  # noqa: E402
from hand_observation import TwoHandActionDetector  # noqa: E402
from hardware.camera_receiver import CameraReceiver  # noqa: E402
from hardware.mqtt_wrist import WristReceiver  # noqa: E402
from hardware.config import HardwareConfig  # noqa: E402
from hardware.live_alignment import multimodal_frame  # noqa: E402
from video_recording import RecordingVideo  # noqa: E402


def record_hardware(camera_url="http://192.168.137.111:81/stream",
                    mqtt_host="192.168.137.1", mqtt_port=1883,
                    topic="wearable/user01/wrist/data", force_channel=None,
                    device_id="smartwrist-user01", alignment_window_ms=10,
                    duration_s=180, stop_requested=None, on_frame=None,
                    show_window=True, on_multimodal=None):
    import cv2
    import mediapipe as mp
    import numpy as np

    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Missing MediaPipe hand model: {MODEL_PATH}")
    if (force_channel is not None and not 0 <= force_channel < 4) or not 0 < alignment_window_ms <= 500:
        raise ValueError("Invalid ADC channel or alignment window")
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    session = Path(tempfile.mkdtemp(
        prefix=f"hardware_{datetime.now():%Y%m%d_%H%M%S_%f}_", dir=SESSION_ROOT))
    camera_file = session / "camera.jsonl"
    marker = session / "hardware_capture.json"
    config = {"schema_version": "smartwear.hardware_capture.v1", "status": "recording",
              "camera_url": camera_url, "mqtt_host": mqtt_host,
              "mqtt_port": mqtt_port, "mqtt_topic": topic,
              "wrist_side": "right", "force_channel": force_channel,
              "device_id": device_id, "alignment_window_ms": alignment_window_ms}
    marker.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    receiver = CameraReceiver(session, camera_url)
    wrist = WristReceiver(session / "wrist_raw.jsonl", mqtt_host, topic, mqtt_port)
    video = RecordingVideo(camera_file, cv2)
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=0.5, min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5)
    started = time.monotonic()
    t0 = None
    last_report = started
    last_jpeg_count = 0
    last_inferred_count = 0
    last_wrist_count = 0
    inferred = 0
    print(f"Hardware session: {session}", flush=True)
    wrist_error = None
    try:
        try:
            wrist.start()
        except ConnectionError as exc:
            wrist_error = str(exc)
            print(f"SmartWrist unavailable; camera preview will continue: {exc}", flush=True)
        receiver.start()
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker, \
                camera_file.open("x", encoding="utf-8", newline="\n") as stream:
            detector = TwoHandActionDetector()
            while time.monotonic() - started < duration_s:
                if stop_requested is not None and stop_requested():
                    break
                item = receiver.get(timeout=0.5)
                if item is None:
                    if t0 is None and time.monotonic() - started > 15:
                        print(f"Camera connection diagnostics: {receiver.snapshot()}",
                              file=sys.stderr, flush=True)
                        raise TimeoutError("ESP32 camera did not supply a valid JPEG within 15 s")
                    continue
                packet, received_epoch_ms = item
                if t0 is None:
                    t0 = packet.epoch_ms
                timestamp = packet.epoch_ms - t0
                frame = cv2.imdecode(np.frombuffer(packet.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    with receiver.lock:
                        receiver.counters["decode_errors"] += 1
                    continue
                sample = wrist.buffer.nearest(packet.epoch_ms, alignment_window_ms)
                aligned = multimodal_frame(packet, frame, sample)
                if on_multimodal is not None:
                    on_multimodal(aligned)
                frame = cv2.flip(frame, 1)
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = landmarker.detect_for_video(image, timestamp)
                data = make_frame_data(result, timestamp, frame.shape[1], frame.shape[0],
                                       detector)
                wrist_state = wrist.snapshot()
                data["wrist_status"] = (
                    "receiving" if wrist_state.get("received", 0) > 0
                    and wrist_state.get("newest_sample_age_ms") is not None
                    and wrist_state["newest_sample_age_ms"] < 2000 else "missing")
                data["live_alignment"] = {"sensor_status": "matched" if sample else "missing",
                                          "delta_ms": aligned["delta_ms"],
                                          "wrist_seq": sample["seq"] if sample else None}
                data["wrist_sample"] = aligned["wrist"]
                data.update(source_epoch_ms=packet.epoch_ms,
                            source_frame_seq=packet.sequence,
                            received_epoch_ms=received_epoch_ms,
                            video_frame_index=video.write(frame))
                stream.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                inferred += 1
                if on_frame is not None:
                    on_frame(cv2, frame, data)
                if show_window:
                    draw_frame(cv2, frame, data)
                    cv2.imshow("SmartWear ESP32 - Left / Right Hands", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                now = time.monotonic()
                if now - last_report >= 5:
                    camera_stats, wrist_stats = receiver.snapshot(), wrist.snapshot()
                    jpeg_count = camera_stats.get("received_jpeg", 0)
                    wrist_count = wrist_stats.get("received", 0)
                    seconds = now - last_report
                    print(f"{now-started:.0f}s: JPEG {jpeg_count} "
                          f"({(jpeg_count-last_jpeg_count)/seconds:.1f} FPS), "
                          f"AI {inferred} ({(inferred-last_inferred_count)/seconds:.1f} FPS), "
                          f"dropped {camera_stats.get('dropped_for_inference', 0)}, "
                          f"wrist {wrist_count} ({(wrist_count-last_wrist_count)/seconds:.1f} Hz), "
                          f"missing seq {wrist_stats.get('seq_gaps', 0)}", flush=True)
                    last_jpeg_count, last_inferred_count = jpeg_count, inferred
                    last_wrist_count = wrist_count
                    last_report = now
    except BaseException as exc:
        config.update(status="failed", error=str(exc), camera_stats=receiver.snapshot(),
                      wrist_stats=wrist.snapshot(), inferred_frames=inferred)
        marker.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    finally:
        cleanup_error = None
        for close in (receiver.stop, wrist.stop, video.close):
            try:
                close()
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if show_window:
            cv2.destroyAllWindows()
        if cleanup_error is not None and sys.exc_info()[0] is None:
            config.update(status="failed", error=str(cleanup_error))
            marker.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            raise cleanup_error
    if not inferred:
        config.update(status="failed", error="No ESP32 camera frame was processed")
        marker.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ValueError("No ESP32 camera frame was processed; raw inputs remain on disk")
    video.save_manifest()
    elapsed = max(0.001, time.monotonic() - started)
    config.update(status="complete", first_camera_epoch_ms=t0,
                  camera_stats=receiver.snapshot(), wrist_stats=wrist.snapshot(),
                  inferred_frames=inferred, elapsed_s=round(elapsed, 3))
    config["wrist_status"] = ("received" if config["wrist_stats"].get("received", 0)
                              else "missing")
    if wrist_error:
        config["wrist_error"] = wrist_error
    config["average_received_fps"] = round(
        config["camera_stats"].get("received_jpeg", 0) / elapsed, 3)
    config["average_inference_fps"] = round(inferred / elapsed, 3)
    config["average_wrist_hz"] = round(config["wrist_stats"].get("received", 0) / elapsed, 3)
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, marker)
    print(f"Saved real-input camera and wrist streams: {session}", flush=True)
    return camera_file


def main(argv=None):
    # Windows redirected output can default to cp1252; reference titles use UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    defaults = HardwareConfig.from_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-url", default=defaults.camera_url)
    parser.add_argument("--mqtt-host", default=defaults.mqtt_host)
    parser.add_argument("--mqtt-port", type=int, default=defaults.mqtt_port)
    parser.add_argument("--topic", default=defaults.topic)
    parser.add_argument("--force-channel", type=int,
                        help="FSR ADC channel 0..3 used for scalar comparisons; all four are saved")
    parser.add_argument("--device-id", default="smartwrist-user01")
    parser.add_argument("--window-ms", type=int, default=defaults.alignment_window_ms)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--role", choices=("expert", "worker"))
    parser.add_argument("--expert-session", type=Path)
    parser.add_argument("--duration-s", type=int, default=180)
    parser.add_argument("--process", action="store_true",
                        help="Normalize, align measured wrist data and analyze after recording")
    parser.add_argument("--publish", action="store_true",
                        help="Process then send the measured result to backend")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    if args.duration_s <= 0 or args.duration_s > 3600:
        parser.error("--duration-s must be 1..3600")
    if args.publish and not args.process:
        parser.error("--publish requires --process")
    if (args.role == "worker") != (args.expert_session is not None):
        parser.error("--role worker requires --expert-session, and vice versa")
    output = record_hardware(args.camera_url, args.mqtt_host, args.mqtt_port,
                             args.topic, args.force_channel, args.device_id,
                             args.window_ms, args.duration_s, show_window=not args.headless)
    if args.process:
        from camera_test import finish_recording
        finish_recording(output, role=args.role, expert_session=args.expert_session)
        if args.publish:
            from integration.backend_bridge import publish
            receipt = publish(output.parent, args.backend_url, os.getenv("SMARTWEAR_API_KEY"))
            print(f"Published measured session: {receipt['session_id']}", flush=True)


if __name__ == "__main__":
    main()
