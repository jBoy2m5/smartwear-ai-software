"""Run the complete offline pipeline for the exact camera file just recorded."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = AI_DIR.parent / "data" / "sessions"


def process_recording(camera_file, output_root=DEFAULT_OUTPUT_ROOT):
    camera_file = Path(camera_file).resolve()
    if not camera_file.is_file():
        raise FileNotFoundError(f"Khong tim thay file camera: {camera_file}")
    with camera_file.open(encoding="utf-8") as stream:
        if not any(line.strip() for line in stream):
            raise ValueError("Camera chua ghi duoc khung hinh nao; khong co du lieu de xu ly.")

    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    # Every processing attempt is isolated, including retries after a failure.
    session = Path(tempfile.mkdtemp(prefix=camera_file.stem + "_", dir=output_root))
    normalized = session / "camera.normalized.jsonl"
    sensors = session / "sensors.jsonl"
    combined = session / "multimodal.jsonl"
    segments = session / "action_segments.json"
    steps = [
        ("Chuan hoa camera", AI_DIR / "preprocessing" / "normalize_camera.py",
         ["--input", camera_file, "--output", normalized]),
        ("Tao cam bien mo phong", AI_DIR / "sensors" / "simulate_sensors.py",
         ["--camera-file", normalized, "--output", sensors]),
        ("Ghep du lieu multimodal", AI_DIR / "preprocessing" / "build_multimodal.py",
         ["--camera-file", normalized, "--sensor-file", sensors, "--output", combined]),
        ("Chia doan hanh dong", AI_DIR / "preprocessing" / "segment_actions.py",
         ["--input", combined, "--output", segments]),
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
    print("IMU, luc/EMG va torque la so mo phong.", flush=True)
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
