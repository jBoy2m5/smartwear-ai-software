import json
from pathlib import Path


INPUT_FILE = Path("ai/camera_data.jsonl")
OUTPUT_FILE = Path("data/processed/normalized_camera.jsonl")


def normalize_camera_data():
    if not INPUT_FILE.exists():
        print(f"Khong tim thay file: {INPUT_FILE}")
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    frame_id = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as input_file, \
         open(OUTPUT_FILE, "w", encoding="utf-8") as output_file:

        for line in input_file:
            line = line.strip()

            if not line:
                continue

            data = json.loads(line)

            timestamp_ms = int(data["timestamp"])

            normalized_data = {
                "frame_id": frame_id,
                "timestamp_ms": timestamp_ms,
                "relative_time_s": round(timestamp_ms / 1000, 3),
                "camera": data["camera"],
                "hands": data["hands"]
            }

            output_file.write(
                json.dumps(
                    normalized_data,
                    ensure_ascii=False
                ) + "\n"
            )

            frame_id += 1

    print("Da normalize camera data.")
    print(f"So frame: {frame_id}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    normalize_camera_data()