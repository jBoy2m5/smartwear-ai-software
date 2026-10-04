"""Run the complete offline pipeline for the exact camera file just recorded."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = AI_DIR / "generated_data" / "sessions"


def process_recording(camera_file, output_root=DEFAULT_OUTPUT_ROOT, session_dir=None):
    camera_file = Path(camera_file).resolve()
    if not camera_file.is_file():
        raise FileNotFoundError(f"Khong tim thay file camera: {camera_file}")
    with camera_file.open(encoding="utf-8") as stream:
        if not any(line.strip() for line in stream):
            raise ValueError("Camera chua ghi duoc khung hinh nao; khong co du lieu de xu ly.")

    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if session_dir is None:
        # Manual retries of older recordings get a fresh session; never overwrite.
        session = Path(tempfile.mkdtemp(prefix=camera_file.stem + "_", dir=output_root))
    else:
        session = Path(session_dir).resolve()
        if not session.is_dir() or session != camera_file.parent or session.parent != output_root:
            raise ValueError("Session must be the camera file's directory inside output_root")
    normalized = session / "camera.normalized.jsonl"
    hardware_marker = session / "hardware_capture.json"
    measured = hardware_marker.is_file()
    hardware = json.loads(hardware_marker.read_text(encoding="utf-8")) if measured else None
    if measured and (hardware.get("schema_version") != "smartwear.hardware_capture.v1"
                     or hardware.get("status") != "complete"
                     or not (session / "wrist_raw.jsonl").is_file()):
        raise ValueError("Hardware capture marker or raw wrist stream is incomplete; no DEMO fallback")
    sensors = session / ("real_sensors.jsonl" if measured else "sensors.jsonl")
    combined = session / "multimodal.jsonl"
    segments = session / "action_segments.json"
    keyframes = session / "keyframes.json"
    steps = [
        ("Chuan hoa camera", AI_DIR / "preprocessing" / "normalize_camera.py",
         ["--input", camera_file, "--output", normalized]),
        (("Ghep cam bien do that" if measured else "Tao cam bien mo phong"),
         (AI_DIR / "hardware" / "align.py" if measured else
          AI_DIR / "sensors" / "simulate_sensors.py"),
         (["--session", session, "--window-ms", hardware["alignment_window_ms"],
           "--device-id", hardware["device_id"],
           *(["--force-channel", hardware["force_channel"]]
             if hardware.get("force_channel") is not None else [])] if measured else
          ["--camera-file", normalized, "--output", sensors])),
        ("Ghep du lieu multimodal", AI_DIR / "preprocessing" / "build_multimodal.py",
         ["--camera-file", normalized, "--sensor-file", sensors, "--output", combined]),
        ("Chia doan hanh dong", AI_DIR / "preprocessing" / "segment_actions.py",
         ["--input", combined, "--output", segments]),
        ("Trich anh tieu bieu", AI_DIR / "preprocessing" / "extract_keyframes.py",
         ["--camera-file", camera_file, "--multimodal-file", combined,
          "--segments-file", segments, "--output", keyframes]),
    ]
    print(f"Thu muc ket qua: {session}", flush=True)
    for number, (name, script, args) in enumerate(steps, 1):
        print(f"[{number}/{len(steps)}] {name}...", flush=True)
        result = subprocess.run(
            [sys.executable, "-B", str(script), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Buoc '{name}' that bai: {detail}\n"
                               f"File camera van duoc giu tai: {camera_file}\n"
                               f"Ket qua chua hoan tat: {session}")
    print(f"HOAN TAT. File ket qua: {combined}", flush=True)
    print(f"Cac doan hanh dong: {segments}", flush=True)
    keyframe_result = json.loads(keyframes.read_text(encoding="utf-8"))
    if keyframe_result["status"] == "skipped_no_video":
        print("Ban ghi cu khong co video: chua co anh tieu bieu.", flush=True)
    else:
        print(f"Anh tieu bieu: {keyframes.with_suffix('')} ({keyframe_result['extracted_count']} anh)", flush=True)
    print(f"Danh sach anh: {keyframes}", flush=True)
    print(("SmartWrist ADC/IMU are measured inputs; head IMU and torque are unavailable."
           if measured else "IMU, luc/EMG va torque la so mo phong."), flush=True)
    return combined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        process_recording(args.input, args.output_root)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Khong hoan tat xu ly: {exc}\n")


if __name__ == "__main__":
    main()
