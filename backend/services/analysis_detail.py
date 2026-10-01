"""Store the complete AI comparison beside a backend session without changing ingest."""

from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
import io
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from PIL import Image, UnidentifiedImageError

from backend.core.exceptions import ArtifactNotFoundError, InvalidKeyFrameError

MAX_ANALYSIS_BYTES = 5 * 1024 * 1024
MAX_RECORDING_BYTES = 250 * 1024 * 1024
MAX_SOURCE_ARCHIVE_BYTES = 100 * 1024 * 1024


def _demo_id(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    candidate = "DEMO_" + safe
    if len(candidate) > 64:
        candidate = "DEMO_" + safe[:46] + "_" + hashlib.sha256(name.encode()).hexdigest()[:12]
    return candidate


def analysis_directory(keyframe_dir: Path, session_id: str) -> Path:
    return keyframe_dir.parent.parent / "data" / "analysis" / session_id


def analysis_path(keyframe_dir: Path, session_id: str) -> Path:
    return analysis_directory(keyframe_dir, session_id) / "analysis_result.json"


def recording_path(keyframe_dir: Path, session_id: str) -> Path:
    return analysis_directory(keyframe_dir, session_id) / "camera.avi"


def source_archive_path(keyframe_dir: Path, session_id: str) -> Path:
    return analysis_directory(keyframe_dir, session_id) / "ai_source_data.zip"


def save_source_archive(keyframe_dir: Path, session_id: str, content: bytes,
                        expected_sha256: str) -> Path:
    """Store a bounded, immutable archive of this session's original AI data."""
    if not content or len(content) > MAX_SOURCE_ARCHIVE_BYTES:
        raise ValueError("AI source archive is empty or too large")
    actual = hashlib.sha256(content).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or actual != expected_sha256:
        raise ValueError("AI source archive SHA-256 does not match")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > 1000 or sum(item.file_size for item in entries) > 250 * 1024 * 1024:
                raise ValueError("AI source archive has too many or oversized entries")
            for item in entries:
                path = PurePosixPath(item.filename)
                if (item.is_dir() or path.is_absolute() or ".." in path.parts
                        or "\\" in item.filename or item.flag_bits & 1):
                    raise ValueError("AI source archive contains an unsafe entry")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("AI source archive must be a valid ZIP") from exc
    destination = source_archive_path(keyframe_dir, session_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != actual:
            raise ValueError("A different AI source archive is already stored for this session")
        return destination
    handle = tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".upload", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if hashlib.sha256(destination.read_bytes()).hexdigest() != actual:
                raise ValueError("A different AI source archive is already stored for this session")
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def save_recording(keyframe_dir: Path, session_id: str, content: bytes,
                   expected_sha256: str) -> Path:
    """Attach the original AVI to an ingested session without replacing it."""
    if (not content or len(content) > MAX_RECORDING_BYTES
            or content[:4] != b"RIFF" or content[8:12] != b"AVI "):
        raise ValueError("Recording must be an AVI file within the size limit")
    actual = hashlib.sha256(content).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or actual != expected_sha256:
        raise ValueError("Recording SHA-256 does not match the uploaded video")
    destination = recording_path(keyframe_dir, session_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != actual:
            raise ValueError("A different recording is already stored for this session")
        return destination
    handle = tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".upload", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if hashlib.sha256(destination.read_bytes()).hexdigest() != actual:
                raise ValueError("A different recording is already stored for this session")
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _paths(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("expert_image_path", "worker_image_path") and item is not None:
                if not isinstance(item, str):
                    raise ValueError("Analysis image path must be a string or null")
                path = PurePosixPath(item)
                if (len(path.parts) != 2 or path.parts[0] != "keyframes"
                        or not path.name or path.name in (".", "..")
                        or "\\" in item or path.suffix.lower() != ".png"):
                    raise ValueError(f"Unsafe analysis image path: {item}")
                yield key.split("_", 1)[0], item
            else:
                yield from _paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _paths(item)


def image_references(document: dict) -> dict[str, set[str]]:
    images = {"expert": set(), "worker": set()}
    for role, relative in _paths(document):
        images[role].add(relative)
    return images


def parse_analysis(content: bytes, session_id: str) -> dict:
    if not content or len(content) > MAX_ANALYSIS_BYTES:
        raise ValueError("Analysis result is empty or too large")
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Analysis result must be UTF-8 JSON") from exc
    if (not isinstance(document, dict)
            or document.get("schema_version") != "smartwear.analysis_comparison.v2"
            or not isinstance(document.get("worker_session"), str)
            or session_id != _demo_id(document["worker_session"])
            or not isinstance(document.get("hands"), dict)
            or not isinstance(document.get("muda_review"), dict)):
        raise ValueError("Analysis result does not match the DEMO worker session")
    image_references(document)
    return document


def save_analysis(keyframe_dir: Path, session_id: str, content: bytes) -> dict:
    document = parse_analysis(content, session_id)
    destination = analysis_path(keyframe_dir, session_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Repeated publication of the same analysis is safe. A different source must
    # never silently replace the comparison already attached to this session.
    if destination.exists():
        if json.loads(destination.read_text(encoding="utf-8")) != document:
            raise ValueError("A different analysis result is already stored for this session")
        return document
    handle = tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if json.loads(destination.read_text(encoding="utf-8")) != document:
                raise ValueError("A different analysis result is already stored for this session")
    finally:
        temporary.unlink(missing_ok=True)
    return document


def load_analysis(keyframe_dir: Path, session_id: str) -> dict | None:
    path = analysis_path(keyframe_dir, session_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def image_urls(document: dict, session_id: str, api_prefix: str) -> dict[str, dict[str, str]]:
    references = image_references(document)
    root = f"{api_prefix}/sessions/{quote(session_id, safe='')}"
    return {
        "worker": {path: f"{root}/keyframes/{quote(PurePosixPath(path).name, safe='')}"
                   for path in sorted(references["worker"])},
        "expert": {path: f"{root}/analysis-images/expert/{quote(PurePosixPath(path).name, safe='')}"
                   for path in sorted(references["expert"])},
    }


def save_expert_image(keyframe_dir: Path, session_id: str, filename: str,
                      content: bytes, max_bytes: int) -> Path:
    document = load_analysis(keyframe_dir, session_id)
    if document is None:
        raise ArtifactNotFoundError("Analysis result must be uploaded before expert images")
    if (not filename or filename != PurePosixPath(filename).name or "\\" in filename
            or f"keyframes/{filename}" not in image_references(document)["expert"]):
        raise InvalidKeyFrameError("Expert image is not declared by the analysis result")
    if not content or len(content) > max_bytes:
        raise InvalidKeyFrameError("Expert image is empty or too large")
    destination_dir = analysis_directory(keyframe_dir, session_id) / "expert_images"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    handle = tempfile.NamedTemporaryFile(dir=destination_dir, suffix=".upload", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        try:
            with Image.open(temporary) as image:
                image.verify()
                if image.format != "PNG":
                    raise InvalidKeyFrameError("Expert image must be PNG")
        except UnidentifiedImageError as exc:
            raise InvalidKeyFrameError("Invalid expert image") from exc
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def get_expert_image(keyframe_dir: Path, session_id: str, filename: str) -> Path:
    document = load_analysis(keyframe_dir, session_id)
    if (document is None or f"keyframes/{filename}" not in image_references(document)["expert"]):
        raise ArtifactNotFoundError("Expert image is not declared")
    candidate = analysis_directory(keyframe_dir, session_id) / "expert_images" / filename
    if not candidate.is_file():
        raise ArtifactNotFoundError("Expert image has not been uploaded")
    return candidate
