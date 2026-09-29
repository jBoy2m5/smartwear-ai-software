import cv2
import mediapipe as mp
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

from hand_observation import HandActionDetector, observation
from process_recording import process_recording


# ============================================================
# SmartWear AI
# Camera + MediaPipe Hand Landmarker NEW API
# ============================================================

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/"
    "hand_landmarker.task"
)

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_PATH = SCRIPT_DIR / "hand_landmarker.task"
# Save each recording separately so earlier camera data is not overwritten.
OUTPUT_FILE = SCRIPT_DIR / f"camera_data_{datetime.now():%Y%m%d_%H%M%S_%f}.jsonl"


# ============================================================
# 1. Download MediaPipe model
# ============================================================

if not MODEL_PATH.exists():

    print("Dang tai hand_landmarker.task...")

    urlretrieve(
        MODEL_URL,
        MODEL_PATH
    )

    print("Da tai model.")


# ============================================================
# 2. MediaPipe NEW API
# ============================================================

BaseOptions = mp.tasks.BaseOptions

HandLandmarker = (
    mp.tasks.vision.HandLandmarker
)

HandLandmarkerOptions = (
    mp.tasks.vision.HandLandmarkerOptions
)

RunningMode = (
    mp.tasks.vision.RunningMode
)


# ============================================================
# 3. Configure Hand Landmarker
# ============================================================

options = HandLandmarkerOptions(

    base_options=BaseOptions(
        model_asset_path=str(
            MODEL_PATH.resolve()
        )
    ),

    running_mode=RunningMode.VIDEO,

    num_hands=2,

    min_hand_detection_confidence=0.5,

    min_hand_presence_confidence=0.5,

    min_tracking_confidence=0.5
)


# ============================================================
# 4. Open webcam
# ============================================================

camera = cv2.VideoCapture(0)

if not camera.isOpened():

    print("Khong mo duoc camera.")

    raise SystemExit(1)


print("Camera da mo.")
print("Nhan Q de thoat.")


# ============================================================
# 5. Start MediaPipe
# ============================================================

with HandLandmarker.create_from_options(
    options
) as landmarker:

    with open(
        OUTPUT_FILE,
        "x",
        encoding="utf-8"
    ) as file:

        start_time = time.perf_counter()
        action_detector = HandActionDetector()
        previous_action = None
        previous_timestamp_ms = -1

        while True:

            success, frame = camera.read()

            if not success:

                print("Khong doc duoc frame.")

                break


            # Mirror camera
            frame = cv2.flip(frame, 1)


            # OpenCV BGR -> RGB
            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )


            # Create MediaPipe Image
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )


            # Timestamp
            timestamp_ms = int(
                (
                    time.perf_counter()
                    - start_time
                ) * 1000
            )
            timestamp_ms = max(previous_timestamp_ms + 1, timestamp_ms)
            previous_timestamp_ms = timestamp_ms


            # =================================================
            # NEW API
            # =================================================

            result = landmarker.detect_for_video(
                mp_image,
                timestamp_ms
            )


            # =================================================
            # Prepare data
            # =================================================

            frame_data = {

                "timestamp": timestamp_ms,

                "camera": {

                    "frame_width":
                        int(frame.shape[1]),

                    "frame_height":
                        int(frame.shape[0])
                },

                "hands": []
            }


            # =================================================
            # Process hands
            # =================================================

            for hand_index, hand_landmarks in enumerate(
                result.hand_landmarks
            ):

                landmarks = []


                # 21 landmarks
                for point_index, point in enumerate(
                    hand_landmarks
                ):

                    landmarks.append({

                        "id": point_index,

                        "x": round(
                            point.x,
                            4
                        ),

                        "y": round(
                            point.y,
                            4
                        ),

                        "z": round(
                            point.z,
                            4
                        )
                    })


                    # Draw landmark
                    x = int(
                        point.x
                        * frame.shape[1]
                    )

                    y = int(
                        point.y
                        * frame.shape[0]
                    )

                    cv2.circle(
                        frame,
                        (x, y),
                        4,
                        (0, 255, 0),
                        -1
                    )


                # =================================================
                # Handedness
                # =================================================

                handedness = "unknown"

                if hand_index < len(
                    result.handedness
                ):

                    if len(
                        result.handedness[
                            hand_index
                        ]
                    ) > 0:

                        handedness = (
                            result.handedness[
                                hand_index
                            ][0].category_name
                        )


                # =================================================
                # World landmarks
                # =================================================

                world_landmarks = []

                if hand_index < len(
                    result.hand_world_landmarks
                ):

                    for point_index, point in enumerate(
                        result.hand_world_landmarks[
                            hand_index
                        ]
                    ):

                        world_landmarks.append({

                            "id": point_index,

                            "x": round(
                                point.x,
                                4
                            ),

                            "y": round(
                                point.y,
                                4
                            ),

                            "z": round(
                                point.z,
                                4
                            )
                        })


                # Add hand
                frame_data["hands"].append({

                    "hand_index":
                        hand_index,

                    "handedness":
                        handedness,

                    "landmarks":
                        landmarks,

                    "world_landmarks":
                        world_landmarks
                })

            # Save camera-derived action and hand state alongside the landmarks.
            primary_hand = frame_data["hands"][0]["landmarks"] if frame_data["hands"] else None
            action_label = action_detector.update(timestamp_ms, primary_hand)
            frame_data["action_estimate"] = observation(action_label, action_detector.pose)
            if action_label != previous_action:
                print(f"{timestamp_ms / 1000:.2f}s  {action_label}")
                previous_action = action_label


            # =================================================
            # Save JSONL
            # =================================================

            file.write(
                json.dumps(
                    frame_data,
                    ensure_ascii=False
                )
                + "\n"
            )

            file.flush()


            # =================================================
            # Display
            # =================================================

            cv2.putText(
                frame,

                f"Hands: {len(frame_data['hands'])}",

                (20, 40),

                cv2.FONT_HERSHEY_SIMPLEX,

                1,

                (0, 255, 0),

                2
            )

            cv2.putText(
                frame,

                "MediaPipe Hand Landmarker NEW API",

                (20, 80),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.65,

                (255, 255, 255),

                2
            )

            cv2.putText(
                frame,

                "Press Q to quit",

                (20, 115),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.65,

                (255, 255, 255),

                2
            )

            cv2.putText(
                frame,
                f"Action: {action_label}",
                (20, 155),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.85,
                (0, 255, 255),
                2
            )


            cv2.imshow(
                "SmartWear AI - Camera",
                frame
            )


            # Q to quit
            if cv2.waitKey(1) & 0xFF == ord("q"):

                break


# ============================================================
# 6. Cleanup
# ============================================================

camera.release()

cv2.destroyAllWindows()


print()
print("Da dung camera.")
print(
    f"Da luu du lieu vao: {OUTPUT_FILE}"
)

# The camera file is closed and the device released before processing begins.
try:
    process_recording(OUTPUT_FILE)
except (OSError, ValueError, RuntimeError) as exc:
    print(f"Khong hoan tat xu ly tu dong: {exc}")
    print("Co the thu lai bang lenh:")
    print(f'python -B "{SCRIPT_DIR / "process_recording.py"}" --input "{OUTPUT_FILE}"')
    raise SystemExit(1)
