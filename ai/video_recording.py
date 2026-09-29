"""Record mirrored, unannotated frames with an explicit JSONL/video index map."""

import hashlib
import json
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RecordingVideo:
    def __init__(self, camera_file, cv2):
        self.camera_file = Path(camera_file)
        self.video_file = self.camera_file.with_suffix(".avi")
        self.manifest_file = self.camera_file.with_suffix(".video.json")
        self.cv2 = cv2
        self.writer = None
        self.size = None
        self.frame_count = 0
        self.closed = False
        self.fps = 30.0  # Encoding rate only; recorded timestamps are authoritative.
        if self.video_file.exists() or self.manifest_file.exists():
            raise FileExistsError("Video or video metadata already exists")

    def write(self, frame):
        if self.closed:
            raise ValueError("Video is already closed")
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            raise ValueError("Expected a three-channel camera frame")
        size = (int(frame.shape[1]), int(frame.shape[0]))
        if any(value <= 0 or value % 2 for value in size):
            raise ValueError("Video width and height must be positive even numbers")
        if self.writer is None:
            self.size = size
            # Reserve exclusively before letting OpenCV open this new file.
            with self.video_file.open("xb"):
                pass
            self.writer = self.cv2.VideoWriter(str(self.video_file),
                self.cv2.VideoWriter_fourcc(*"MJPG"), self.fps, size)
            if not self.writer.isOpened():
                self.close()
                raise RuntimeError("Khong tao duoc video MJPG/AVI; dung ghi de tranh mat anh.")
        if size != self.size:
            raise ValueError("Camera resolution changed during recording")
        self.writer.write(frame)
        index = self.frame_count
        self.frame_count += 1
        return index

    def close(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        self.closed = True

    def save_manifest(self):
        if not self.closed:
            raise ValueError("Close the video and JSONL before saving metadata")
        if not self.frame_count:
            return None
        rows = [json.loads(line) for line in self.camera_file.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        if (len(rows) != self.frame_count
                or any(type(row.get("video_frame_index")) is not int or
                       row["video_frame_index"] != i for i, row in enumerate(rows))):
            raise ValueError("Camera/video frame mapping is incomplete")
        if not self.video_file.is_file() or not self.video_file.stat().st_size:
            raise ValueError("Recorded video is empty")
        metadata = {
            "schema_version": "smartwear.recording_video.v1",
            "video_file": self.video_file.name,
            "video_sha256": sha256_file(self.video_file),
            "camera_sha256": sha256_file(self.camera_file),
            "frame_count": self.frame_count,
            "frame_width": self.size[0], "frame_height": self.size[1],
            "codec": "MJPG", "encoding_fps": self.fps,
            "mirrored": True, "has_overlay": False,
            "timing": "video_frame_index maps to each raw timestamp; playback FPS is not capture timing",
        }
        with self.manifest_file.open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, allow_nan=False, indent=2)
        return self.manifest_file
