"""Smoke-test the actual MediaPipe model with a synthetic black frame; no hardware."""
import json
from pathlib import Path
import mediapipe as mp
import numpy as np

root = Path(__file__).resolve().parents[1]
options = mp.tasks.vision.HandLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=str(root / "ai/hand_landmarker.task")),
    running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2)
with mp.tasks.vision.HandLandmarker.create_from_options(options) as model:
    image = mp.Image(image_format=mp.ImageFormat.SRGB,
                     data=np.zeros((240, 320, 3), dtype=np.uint8))
    result = model.detect_for_video(image, 0)
    print(json.dumps({"test_input": "synthetic_black_frame", "mediapipe": mp.__version__,
                      "model_loaded": True, "detected_hands": len(result.hand_landmarks)}))
