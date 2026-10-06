"""Collect camera JPEG packets and wrist MQTT JSON without running AI."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from hardware.camera_receiver import CameraReceiver  # noqa: E402
from hardware.mqtt_wrist import WristReceiver  # noqa: E402
from hardware.config import HardwareConfig  # noqa: E402
from process_recording import DEFAULT_OUTPUT_ROOT  # noqa: E402


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(path, document):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def collect_raw(camera_url="http://192.168.137.111:81/stream",
                mqtt_host="192.168.137.1", mqtt_port=1883,
                topic="wearable/user01/wrist/data", duration_s=60,
                output_dir=None, stop_requested=None):
    if not 0 < duration_s <= 3600:
        raise ValueError("duration_s must be 1..3600")
    if output_dir is None:
        DEFAULT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        session = Path(tempfile.mkdtemp(
            prefix=f"hardware_raw_{datetime.now():%Y%m%d_%H%M%S_%f}_",
            dir=DEFAULT_OUTPUT_ROOT))
    else:
        session = Path(output_dir).resolve()
        session.mkdir(parents=True, exist_ok=False)
    marker = session / "raw_capture.json"
    camera = CameraReceiver(session, camera_url)
    wrist = WristReceiver(session / "wrist_raw.jsonl", mqtt_host, topic, mqtt_port)
    capture_start = None
    last_report = None
    last_camera = last_wrist = 0
    document = {"schema_version": "smartwear.raw_capture.v1", "status": "recording",
                "camera_url": camera_url, "mqtt_host": mqtt_host, "mqtt_port": mqtt_port,
                "mqtt_topic": topic, "wrist_side": "right", "duration_requested_s": duration_s}
    _write_manifest(marker, document)
    print(f"Raw hardware session: {session}", flush=True)
    error = None
    try:
        wrist.start()
        camera.start()
        capture_start = last_report = time.monotonic()
        while time.monotonic() - capture_start < duration_s:
            if stop_requested is not None and stop_requested():
                break
            camera.get(timeout=0.5)  # Drain the preview queue; raw JPEGs are written separately.
            now = time.monotonic()
            if now - last_report >= 5:
                cs, ws = camera.snapshot(), wrist.snapshot()
                frames, samples = cs.get("received_jpeg", 0), ws.get("received", 0)
                span = now - last_report
                print(f"{now-capture_start:.0f}s: camera {frames} JPEG "
                      f"({(frames-last_camera)/span:.1f} FPS), wrist {samples} samples "
                      f"({(samples-last_wrist)/span:.1f} Hz), "
                      f"seq gaps {ws.get('seq_gaps', 0)}, bad MQTT {ws.get('malformed', 0)}, "
                      f"camera errors {cs.get('stream_errors', 0)}", flush=True)
                last_camera, last_wrist, last_report = frames, samples, now
    except Exception as exc:
        error = exc
    finally:
        capture_elapsed = (max(0.001, time.monotonic() - capture_start)
                           if capture_start is not None else 0)
        for close in (camera.stop, wrist.stop):
            try:
                close()
            except Exception as exc:
                if error is None:
                    error = exc
        cs, ws = camera.snapshot(), wrist.snapshot()
        document.update(camera_stats=cs, wrist_stats=ws,
                        capture_elapsed_s=round(capture_elapsed, 3),
                        camera_received_fps=(round(cs.get("received_jpeg", 0) / capture_elapsed, 3)
                                             if capture_elapsed else None),
                        wrist_received_hz=(round(ws.get("received", 0) / capture_elapsed, 3)
                                           if capture_elapsed else None))
        document["status"] = ("failed" if error else "raw_complete"
                              if cs.get("received_jpeg", 0) and ws.get("received", 0)
                              else "incomplete_inputs")
        if error:
            document["error"] = str(error)
        document["source_sha256"] = {
            name: _sha256(session / name) for name in
            ("camera_raw.mjpeg", "camera_packets.jsonl", "wrist_raw.jsonl")
            if (session / name).is_file()}
        packet_index = session / "camera_packets.jsonl"
        if packet_index.is_file():
            with packet_index.open(encoding="utf-8") as stream:
                offsets = [packet["epoch_ms"] - packet["received_epoch_ms"]
                           for line in stream if line.strip()
                           for packet in (json.loads(line),)]
            if offsets:
                document["camera_device_minus_receive_ms"] = {
                    "min": min(offsets), "max": max(offsets),
                    "mean": round(sum(offsets) / len(offsets), 3)}
                document["clock_note"] = (
                    "Device-minus-PC receive time includes transport delay; "
                    "it is not a camera-to-wrist clock accuracy measurement")
        _write_manifest(marker, document)
    if error:
        raise RuntimeError(f"Raw session saved at {session}: {error}") from error
    print(f"Raw capture {document['status']}: {session}", flush=True)
    return session, document


def main(argv=None):
    defaults = HardwareConfig.from_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-url", default=defaults.camera_url)
    parser.add_argument("--mqtt-host", default=defaults.mqtt_host)
    parser.add_argument("--mqtt-port", type=int, default=defaults.mqtt_port)
    parser.add_argument("--topic", default=defaults.topic)
    parser.add_argument("--duration-s", type=int, default=60)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        _, result = collect_raw(args.camera_url, args.mqtt_host, args.mqtt_port,
                                args.topic, args.duration_s, args.output_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Raw capture failed: {exc}\n")
    if result["status"] != "raw_complete":
        parser.exit(2, "Raw capture incomplete: camera or SmartWrist sent no samples\n")


if __name__ == "__main__":
    main()
