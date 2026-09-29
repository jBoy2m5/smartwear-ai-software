"""Capture two hands, save independent actions, then run the session pipeline."""

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

from hand_observation import SIDES, TwoHandActionDetector
from process_recording import process_recording

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_PATH = SCRIPT_DIR / "hand_landmarker.task"
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/"
             "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
COLORS = {"left": (255, 200, 80), "right": (80, 230, 120)}
WINDOW = "SmartWear AI - Two Hands"


def point_records(points):
    return [{"id": i, "x": round(p.x, 4), "y": round(p.y, 4), "z": round(p.z, 4)}
            for i, p in enumerate(points)]


def make_frame_data(result, timestamp_ms, width, height, detector):
    """Pure conversion shared by live capture and camera-free integration tests."""
    hands = []
    for index, landmarks in enumerate(result.hand_landmarks):
        categories = result.handedness[index] if index < len(result.handedness) else []
        world = result.hand_world_landmarks[index] if index < len(result.hand_world_landmarks) else []
        hands.append({
            "hand_index": index,
            "handedness": categories[0].category_name if categories else "unknown",
            "handedness_score": round(categories[0].score, 4) if categories else None,
            "landmarks": point_records(landmarks),
            "world_landmarks": point_records(world),
        })
    return {"schema_version": "smartwear.camera_raw.v2", "timestamp": timestamp_ms,
            "camera": {"frame_width": width, "frame_height": height}, "hands": hands,
            "hand_actions": detector.update(timestamp_ms, hands)}


def draw_frame(cv2, frame, data):
    for hand in data["hands"]:
        side = hand["handedness"].lower()
        color = COLORS.get(side, (150, 150, 150))
        for point in hand["landmarks"]:
            cv2.circle(frame, (int(point["x"] * frame.shape[1]),
                               int(point["y"] * frame.shape[0])), 4, color, -1)
    for index, side in enumerate(SIDES):
        action = data["hand_actions"][side]
        label = "UNCERTAIN" if action["tracking_status"] == "ambiguous" else action["label"]
        cv2.putText(frame, f"{side.upper()}: {label}", (20, 40 + index * 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS[side], 2)
    cv2.putText(frame, "Q: stop and process", (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def record_camera():
    # Offline pipeline and tests do not require OpenCV/MediaPipe installed.
    import cv2
    import mediapipe as mp

    if not MODEL_PATH.exists():
        print("Dang tai hand_landmarker.task...")
        urlretrieve(MODEL_URL, MODEL_PATH)
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=0.5, min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5)
    camera = cv2.VideoCapture(0)
    output = SCRIPT_DIR / f"camera_data_{datetime.now():%Y%m%d_%H%M%S_%f}.jsonl"
    try:
        if not camera.isOpened():
            raise RuntimeError("Khong mo duoc camera.")
        print("Camera da mo. LEFT = tay trai, RIGHT = tay phai. Nhan Q de dung.")
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker, \
                output.open("x", encoding="utf-8", newline="\n") as stream:
            detector = TwoHandActionDetector()
            started = time.perf_counter()
            previous_ms = -1
            previous_actions = None
            while True:
                success, frame = camera.read()
                if not success:
                    print("Khong doc duoc frame; xu ly phan da ghi.")
                    break
                frame = cv2.flip(frame, 1)
                timestamp = max(previous_ms + 1, int((time.perf_counter() - started) * 1000))
                previous_ms = timestamp
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = landmarker.detect_for_video(image, timestamp)
                data = make_frame_data(result, timestamp, frame.shape[1], frame.shape[0], detector)
                stream.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                current = tuple((data["hand_actions"][side]["label"],
                                 data["hand_actions"][side]["tracking_status"]) for side in SIDES)
                if current != previous_actions:
                    print(f"{timestamp / 1000:.2f}s  LEFT: {current[0][0]}  RIGHT: {current[1][0]}")
                    previous_actions = current
                draw_frame(cv2, frame, data)
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    print(f"Da luu du lieu camera: {output}")
    return output


def main():
    try:
        output = record_camera()
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        raise SystemExit(f"Loi camera: {exc}") from exc
    try:
        process_recording(output)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Khong hoan tat xu ly tu dong: {exc}")
        print(f'Thu lai: python -B "{SCRIPT_DIR / "process_recording.py"}" --input "{output}"')
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
