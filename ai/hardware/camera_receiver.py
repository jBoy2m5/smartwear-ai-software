"""One bounded MJPEG consumer, with original JPEG bytes saved before inference."""

import hashlib
import json
import queue
import threading
import time
import urllib.error
from collections import Counter
from pathlib import Path

from hardware.mjpeg import open_camera_stream, read_parts


class CameraReceiver:
    def __init__(self, session, url, queue_size=6):
        self.session = Path(session)
        self.url = url
        self.frames = queue.Queue(maxsize=queue_size)
        self.stop_event = threading.Event()
        self.worker = None
        self.counters = Counter()
        self.lock = threading.Lock()
        self.error = None
        self.last_sequence = None
        self.last_epoch = None
        self.last_stream_error = None

    def _record(self, stream, index, frame, received_epoch_ms):
        offset = stream.tell()
        stream.write(frame.jpeg)
        stream.flush()
        index.write(json.dumps({"seq": frame.sequence, "epoch_ms": frame.epoch_ms,
                                "received_epoch_ms": received_epoch_ms,
                                "offset": offset, "length": len(frame.jpeg),
                                "sha256": hashlib.sha256(frame.jpeg).hexdigest()}) + "\n")
        index.flush()

    def _receive(self):
        try:
            with (self.session / "camera_raw.mjpeg").open("xb") as raw, \
                    (self.session / "camera_packets.jsonl").open("x", encoding="utf-8") as index:
                delay = 0.5
                while not self.stop_event.is_set():
                    try:
                        with open_camera_stream(self.url) as response:
                            delay = 0.5
                            for frame in read_parts(response, response.headers.get("Content-Type")):
                                if self.stop_event.is_set():
                                    break
                                received = time.time_ns() // 1_000_000
                                if (self.last_sequence is not None and
                                        (frame.sequence <= self.last_sequence
                                         or frame.epoch_ms <= self.last_epoch)):
                                    raise RuntimeError("Camera sequence or clock reset; start a new session")
                                self.last_sequence, self.last_epoch = frame.sequence, frame.epoch_ms
                                self._record(raw, index, frame, received)
                                item = (frame, received)
                                try:
                                    self.frames.put_nowait(item)
                                except queue.Full:
                                    try:
                                        self.frames.get_nowait()
                                        self.frames.task_done()
                                    except queue.Empty:
                                        pass  # Consumer drained it after the Full check.
                                    self.frames.put_nowait(item)
                                    with self.lock:
                                        self.counters["dropped_for_inference"] += 1
                                with self.lock:
                                    self.counters["received_jpeg"] += 1
                        if not self.stop_event.is_set():
                            with self.lock:
                                self.counters["stream_disconnects"] += 1
                    except urllib.error.HTTPError as exc:
                        with self.lock:
                            self.last_stream_error = str(exc)
                        if exc.code != 503:
                            raise
                        with self.lock:
                            self.counters["http_503"] += 1
                    except (EOFError, OSError, ValueError, urllib.error.URLError) as exc:
                        with self.lock:
                            self.counters["stream_errors"] += 1
                            self.last_stream_error = str(exc)
                    if not self.stop_event.is_set():
                        self.stop_event.wait(delay)
                        delay = min(delay * 2, 5)
        except Exception as exc:
            self.error = exc
            self.stop_event.set()

    def start(self):
        self.session.mkdir(parents=True, exist_ok=True)
        if (self.session / "camera_raw.mjpeg").exists():
            raise FileExistsError("Raw camera file already exists")
        self.worker = threading.Thread(target=self._receive, daemon=True)
        self.worker.start()

    def get(self, timeout=1):
        if self.error is not None:
            raise RuntimeError(f"Camera reader failed: {self.error}") from self.error
        try:
            return self.frames.get(timeout=timeout)
        except queue.Empty:
            if self.error is not None:
                raise RuntimeError(f"Camera reader failed: {self.error}") from self.error
            return None

    def snapshot(self):
        with self.lock:
            result = dict(self.counters)
            if self.last_stream_error is not None:
                result["last_stream_error"] = self.last_stream_error
        result["queue_size"] = self.frames.qsize()
        return result

    def stop(self):
        self.stop_event.set()
        if self.worker is not None:
            self.worker.join(timeout=10)
            if self.worker.is_alive():
                raise RuntimeError("Camera reader did not stop")
        if self.error is not None:
            raise RuntimeError(f"Camera reader failed: {self.error}") from self.error
