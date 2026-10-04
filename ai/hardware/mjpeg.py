"""Bounded multipart-JPEG reader that preserves device timestamps and sequence."""

from dataclasses import dataclass
from email.message import Message
from urllib.request import urlopen


MAX_HEADER_LINE = 4096
MAX_HEADERS = 32
MAX_JPEG = 2_000_000


@dataclass(frozen=True)
class CameraFrame:
    jpeg: bytes
    epoch_ms: int
    sequence: int


def _line(stream):
    value = stream.readline(MAX_HEADER_LINE + 1)
    if len(value) > MAX_HEADER_LINE:
        raise ValueError("MJPEG header line is too long")
    return value


def _exact(stream, length):
    parts = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Incomplete JPEG frame")
        parts.append(chunk)
        remaining -= len(chunk)
    return b"".join(parts)


def boundary_from_content_type(content_type):
    message = Message()
    message["Content-Type"] = content_type or ""
    if message.get_content_type().lower() != "multipart/x-mixed-replace":
        raise ValueError("Camera response is not multipart MJPEG")
    boundary = message.get_param("boundary", header="content-type")
    if not boundary or len(boundary) > 70 or any(c in boundary for c in "\r\n"):
        raise ValueError("Missing or unsafe MJPEG boundary")
    return (boundary if boundary.startswith("--") else "--" + boundary).encode("ascii")


def read_parts(stream, content_type):
    """Yield complete JPEG parts regardless of network read chunk boundaries."""
    boundary = boundary_from_content_type(content_type)
    while True:
        marker = _line(stream).strip()
        if not marker:
            if marker == b"" and getattr(stream, "closed", False):
                return
            # Empty separator before a boundary is legal; EOF is caught below.
            marker = _line(stream).strip()
        if marker == boundary + b"--":
            return
        if marker != boundary:
            if not marker:
                return
            raise ValueError("Invalid MJPEG boundary")
        headers = {}
        for _ in range(MAX_HEADERS):
            raw = _line(stream)
            if raw in (b"\r\n", b"\n"):
                break
            if not raw or b":" not in raw:
                raise ValueError("Incomplete MJPEG part headers")
            key, value = raw.split(b":", 1)
            key = key.decode("ascii", errors="strict").strip().lower()
            if key in headers:
                raise ValueError("Duplicate MJPEG part header")
            headers[key] = value.decode("ascii", errors="strict").strip()
        else:
            raise ValueError("Too many MJPEG part headers")
        if headers.get("content-type", "").split(";", 1)[0].lower() != "image/jpeg":
            raise ValueError("MJPEG part is not JPEG")
        try:
            length = int(headers["content-length"])
            epoch = int(headers["x-timestamp-ms"])
            sequence = int(headers["x-frame-seq"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("MJPEG frame is missing length, timestamp or sequence") from exc
        if not 0 < length <= MAX_JPEG or epoch < 1_577_836_800_000 or sequence < 0:
            raise ValueError("Invalid MJPEG length, device clock or sequence")
        jpeg = _exact(stream, length)
        if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
            raise ValueError("Incomplete or invalid JPEG markers")
        yield CameraFrame(jpeg, epoch, sequence)


def open_camera_stream(url, timeout=5):
    response = urlopen(url, timeout=timeout)
    try:
        boundary_from_content_type(response.headers.get("Content-Type"))
        return response
    except Exception:
        response.close()
        raise
