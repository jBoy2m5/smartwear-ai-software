"""Additive DEMO adapter from a completed AI session to backend SessionInput."""

import argparse
import hashlib
import io
import json
import math
import os
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import quote

LABELS = {"OPEN", "REACH", "GRAB", "ASSEMBLY", "RELEASE"}
SIDES = ("left", "right")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def demo_id(name):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    candidate = "DEMO_" + safe
    if len(candidate) > 64:
        candidate = "DEMO_" + safe[:46] + "_" + hashlib.sha256(name.encode()).hexdigest()[:12]
    return candidate


def measured_id(name):
    return "MEASURED_" + demo_id(name)[5:]


def bridge_kind(payload):
    return "measured" if payload["session_id"].startswith("MEASURED_") else "demo"


def demo_force(raw):
    """Map unitless simulated sensor signal to a nonphysical DEMO display number."""
    if raw is None:
        return None
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Non-finite simulated force")
    return round(max(0.0, min(1.0, (value - 80.0) / 720.0)) * 20.0, 3)


def source_data(session):
    session = Path(session).resolve()
    if not session.is_dir():
        raise ValueError(f"Session directory does not exist: {session}")
    segments_file = session / "action_segments.json"
    frames_file = session / "multimodal.jsonl"
    keys_file = session / "keyframes.json"
    role_file = session / "session_role.json"
    hardware = session / "hardware_capture.json"
    measured = hardware.is_file()
    sensors_file = session / ("real_sensors.meta.json" if measured else "sensors.meta.json")
    for path in (segments_file, frames_file, keys_file, role_file, sensors_file):
        if not path.is_file():
            raise ValueError(f"Missing session input: {path}")
    segments = read_json(segments_file)
    keys = read_json(keys_file)
    role = read_json(role_file)
    sensors = read_json(sensors_file)
    segment_hash = digest(segments_file)
    frame_hash = digest(frames_file)
    if (segments.get("schema_version") != "smartwear.action_segments.v2"
            or segments.get("action_source") != "camera_landmarks_heuristic"
            or segments.get("uses_simulated_sensors") is not False
            or segments.get("source_sha256") != frame_hash):
        raise ValueError("Action segments do not match camera-derived multimodal data")
    if (keys.get("segments_sha256") != segment_hash
            or keys.get("multimodal_sha256") != frame_hash):
        raise ValueError("Keyframes do not match action segments/multimodal data")
    if (role.get("schema_version") != "smartwear.session_role.v1"
            or role.get("segments_sha256") != segment_hash
            or role.get("role") not in ("expert", "worker", "demo_reference")):
        raise ValueError("Session role is missing or mismatched")
    sensor_source = "measured_hardware" if measured else "simulated_from_camera_observations"
    if sensors.get("source") != sensor_source:
        raise ValueError("Sensor source does not match capture mode")
    if measured and (read_json(hardware).get("status") != "complete"
                     or sensors.get("camera_sha256") != digest(session / "camera.normalized.jsonl")
                     or sensors.get("sensors_sha256") != digest(session / "real_sensors.jsonl")):
        raise ValueError("Measured capture or sensor hashes are incomplete")
    analysis_file = session / "analysis_result.json"
    analysis = read_json(analysis_file) if analysis_file.is_file() else None
    if role["role"] == "worker":
        if (analysis is None or analysis.get("schema_version") != "smartwear.analysis_comparison.v2"
                or analysis.get("worker_session") != session.name
                or analysis.get("worker_segments_sha256") != segment_hash):
            raise ValueError("Worker comparison is missing or belongs to another segmentation")
    frames = []
    with frames_file.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                frames.append(json.loads(line))
    if not frames or any(type(f.get("timestamp_ms")) is not int for f in frames):
        raise ValueError("Multimodal frames are empty or malformed")
    if any(f.get("provenance", {}).get("sensors") != sensor_source for f in frames):
        raise ValueError("Multimodal sensor provenance differs from capture mode")
    if any(b["timestamp_ms"] <= a["timestamp_ms"] for a, b in zip(frames, frames[1:])):
        raise ValueError("Multimodal timestamps must increase")
    images = {}
    for entry in keys.get("entries", []):
        if entry.get("status") != "extracted":
            continue
        relative = entry.get("image_path")
        if not isinstance(relative, str):
            raise ValueError("Invalid keyframe path")
        path = Path(relative.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
            raise ValueError("Unsafe keyframe path")
        actual = (session / path).resolve()
        if not actual.is_file() or not actual.is_relative_to(session):
            raise ValueError("Keyframe does not exist inside session")
        if actual.name in images and images[actual.name] != actual:
            raise ValueError("Duplicate keyframe basename")
        images[actual.name] = actual
    return session, segments["segments"], frames, role["role"], analysis, images, {
        "action_segments.json": segment_hash, "multimodal.jsonl": frame_hash,
        "keyframes.json": digest(keys_file), "session_role.json": digest(role_file),
        sensors_file.name: digest(sensors_file),
        **({"analysis_result.json": digest(analysis_file)} if analysis else {}),
    }, sensor_source


def phases_for(segments, frames, measured=False):
    tracks = {side: [] for side in SIDES}
    boundaries = set()
    for segment in segments:
        side = segment.get("hand")
        if side not in SIDES:
            raise ValueError("Unknown segment hand")
        start, end = segment.get("start_ms"), segment.get("end_ms")
        if type(start) is not int or type(end) is not int or start < 0 or end < start:
            raise ValueError("Invalid segment time")
        if (segment.get("tracking_status") == "detected"
                and segment.get("label") in LABELS and end > start):
            tracks[side].append(segment)
            boundaries.update((start, end))
    for side in SIDES:
        ordered = sorted(tracks[side], key=lambda s: s["start_ms"])
        if any(b["start_ms"] < a["end_ms"] for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Overlapping actions on one hand")
        tracks[side] = ordered
    phases = []
    points = sorted(boundaries)
    for start, end in zip(points, points[1:]):
        labels = []
        active_sides = []
        for side in SIDES:
            active = next((s for s in tracks[side] if s["start_ms"] <= start and s["end_ms"] >= end), None)
            if active:
                labels.append(side.upper() + "_" + active["label"])
                active_sides.append(side)
        if not labels:
            continue
        forces = ([] if measured else
                  [demo_force(f.get("hand_sensors", {}).get(side, {}).get("force_emg_raw"))
                   for f in frames if start <= f["timestamp_ms"] < end for side in active_sides])
        available = [v for v in forces if v is not None]
        phases.append({"phase": ".".join(labels), "start_time": start / 1000,
                       "end_time": end / 1000,
                       "peak_force_N": max(available) if available else None})
    return phases


def metrics_for(role, analysis):
    if role != "worker":
        return {"similarity_score": 100.0, "muda_detected_seconds": 0.0}
    weighted = []
    for side in SIDES:
        hand = analysis.get("hands", {}).get(side, {})
        if hand.get("status") == "compared":
            cost = float(hand["normalized_dtw_cost"])
            weight = min(int(hand["expert_segments"]), int(hand["worker_segments"]))
            if weight > 0 and math.isfinite(cost) and cost >= 0:
                weighted.append((cost, weight))
    similarity = (100 / (1 + sum(c * w for c, w in weighted) / sum(w for _, w in weighted))
                  if weighted else 0.0)
    total_ms = 0
    seen = set()
    for side in SIDES:
        for item in analysis.get("muda_review", {}).get("hands", {}).get(side, {}).get("candidates", []):
            identity = (side, item.get("worker_segment_id"))
            if identity in seen:
                continue
            seen.add(identity)
            reason = item.get("reason")
            duration = item.get("extra_ms") if reason == "longer_visible_action" else item.get("duration_ms")
            if reason in ("missing_visible_action", "shorter_visible_action"):
                duration = 0
            if isinstance(duration, (int, float)) and math.isfinite(duration):
                total_ms += max(0, duration)
    return {"similarity_score": round(similarity, 2),
            "muda_detected_seconds": round(total_ms / 1000, 3)}


def trajectory_for(frames):
    result = []
    last_ms = -100
    for frame in frames:
        ms = frame["timestamp_ms"]
        if ms - last_ms < 100:
            continue
        hand = next((item for item in frame.get("hands", [])
                     if str(item.get("handedness", "")).lower() == "right"), None)
        wrist = next((point for point in (hand.get("landmarks") or [])
                      if point.get("id") == 0), None) if hand else None
        if wrist is None:
            continue
        x, y = float(wrist["x"]), float(wrist["y"])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Non-finite camera landmark")
        force = demo_force(frame.get("hand_sensors", {}).get("right", {}).get("force_emg_raw"))
        result.append({"t": ms / 1000, "pos": [round(x * 0.4, 4),
                                                 round((1 - y) * 0.3, 4), 0.1],
                       "force": force if force is not None else 0.0})
        last_ms = ms
    return result


def build_payload(session_dir):
    session, segments, frames, role, analysis, images, hashes, source = source_data(session_dir)
    measured = source == "measured_hardware"
    payload = {"session_id": measured_id(session.name) if measured else demo_id(session.name),
               "worker_type": "TRAINEE" if role == "worker" else "EXPERT",
               "key_frames": sorted(images),
               "action_phases": phases_for(segments, frames, measured),
               "dtw_metrics": metrics_for(role, analysis),
               "robot_trajectory_points": [] if measured else trajectory_for(frames)}
    meta = {
        "schema_version": ("smartwear.backend_bridge_measured.v1" if measured
                           else "smartwear.backend_bridge_demo.v1"),
        "demo_only": not measured, "sensor_source": source,
        "session_id": payload["session_id"], "source_session": str(session),
        "source_sha256": hashes,
        "force_rule": ("Measured ADC counts remain in real_sensors and analysis; "
                       "peak_force_N is null because no Newton calibration exists" if measured else
                       "DEMO only: clamp((unitless force_emg_raw - 80)/720, 0, 1)*20; backend N field is display-only, not measured Newton"),
        "phase_rule": "Visible left/right labels share one nonoverlapping phase, e.g. LEFT_GRAB.RIGHT_OPEN",
        "similarity_rule": "DEMO: 100/(1+weighted mean per-hand normalized DTW cost); no comparison=0, expert baseline=100",
        "muda_rule": "DEMO sum of deduplicated unconfirmed review-candidate durations; missing action contributes 0; not confirmed waste",
        "trajectory_rule": ("No robot trajectory is exported for measured input without coordinate calibration"
                            if measured else
                            "DEMO 100ms-spaced right wrist screen coordinates mapped to a 0.4x0.3 plane at z=0.1; not a calibrated robot path"),
    }
    return payload, meta, images


def save_payload(session_dir, payload, meta):
    session = Path(session_dir)
    kind = bridge_kind(payload)
    for name, value in ((f"backend_payload_{kind}.json", payload),
                        (f"backend_payload_{kind}.meta.json", meta)):
        path = session / name
        data = encoded(value)
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError(f"Existing DEMO output differs; source changed: {path}")
        else:
            with path.open("xb") as stream:
                stream.write(data)


def analysis_assets(session_dir, analysis, worker_images):
    """Resolve only images declared by verified worker/expert keyframe manifests."""
    if analysis is None:
        return {}
    session = Path(session_dir).resolve()
    ai_dir = Path(__file__).resolve().parents[1]
    name = analysis.get("expert_session")
    if (not isinstance(name, str) or name in (".", "..")
            or Path(name).name != name or "\\" in name):
        raise ValueError("Unsafe expert session name")
    roots = (ai_dir / "generated_data" / "reference_samples" / name,
             ai_dir / "generated_data" / "sessions" / name)
    matches = [root for root in roots if root.is_dir()]
    if len(matches) != 1:
        raise ValueError("Expert session is missing or ambiguous")
    expert = matches[0].resolve()
    segment_file = expert / "action_segments.json"
    manifest_file = expert / "keyframes.json"
    if (not segment_file.is_file() or not manifest_file.is_file()
            or digest(segment_file) != analysis.get("expert_segments_sha256")):
        raise ValueError("Expert source hash does not match analysis")
    manifest = read_json(manifest_file)
    if manifest.get("segments_sha256") != digest(segment_file):
        raise ValueError("Expert keyframes do not match action segments")
    declared = {entry.get("image_path") for entry in manifest.get("entries", [])
                if entry.get("status") == "extracted"}
    references = {"expert": set(), "worker": set()}

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("expert_image_path", "worker_image_path") and item is not None:
                    role = key.split("_", 1)[0]
                    if not isinstance(item, str):
                        raise ValueError("Invalid analysis image reference")
                    references[role].add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(analysis)
    for relative in references["worker"]:
        if (not relative.startswith("keyframes/")
                or "/" in relative[len("keyframes/"):]
                or Path(relative).name not in worker_images):
            raise ValueError("Analysis refers to an undeclared worker image")
    images = {}
    for relative in references["expert"]:
        path = Path(relative)
        if (relative not in declared or path.is_absolute() or ".." in path.parts
                or not relative.startswith("keyframes/") or path.suffix.lower() != ".png"):
            raise ValueError("Analysis refers to an undeclared expert image")
        actual = (expert / path).resolve()
        if not actual.is_relative_to(expert) or not actual.is_file():
            raise ValueError("Expert image is missing")
        if path.name in images and images[path.name] != actual:
            raise ValueError("Duplicate expert image basename")
        images[path.name] = actual
    return images


def publish_analysis(session_dir, payload, worker_images, base_url, api_key):
    session = Path(session_dir)
    path = session / "analysis_result.json"
    if not path.is_file():
        return None  # Expert sessions have no worker comparison.
    analysis = read_json(path)
    images = analysis_assets(session, analysis, worker_images)
    kind = bridge_kind(payload)
    receipt_file = session / f"backend_analysis_{kind}.receipt.json"
    analysis_hash = digest(path)
    image_hashes = {name: digest(image) for name, image in sorted(images.items())}
    if receipt_file.exists():
        receipt = read_json(receipt_file)
        if (receipt.get("analysis_sha256") == analysis_hash
                and receipt.get("expert_images_sha256") == image_hashes
                and receipt.get("backend_url") == base_url):
            return receipt
        raise ValueError("Existing analysis receipt differs from current source/backend")
    root = base_url.rstrip("/") + "/api/v1/sessions/" + quote(payload["session_id"])
    request_json(root + "/analysis-result", "PUT", path.read_bytes(), api_key)
    for name, image in sorted(images.items()):
        request_json(root + "/analysis-images/expert/" + quote(name),
                     "PUT", image.read_bytes(), api_key, "image/png")
    receipt = {"schema_version": f"smartwear.backend_analysis_{kind}.v1",
               "session_id": payload["session_id"], "backend_url": base_url,
               "analysis_sha256": analysis_hash,
               "expert_images_sha256": image_hashes,
               "analysis_url": f"/api/v1/sessions/{payload['session_id']}/analysis-result"}
    with receipt_file.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return receipt


def request_json(url, method, data, api_key=None, content_type="application/json",
                 extra_headers=None, timeout=30):
    headers = {"Content-Type": content_type}
    if extra_headers:
        headers.update(extra_headers)
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        raise RuntimeError(f"Backend HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach backend at {url}: {exc.reason}") from exc


def publish_recording(session_dir, payload, base_url, api_key):
    """Publish a real camera recording when this AI session contains one."""
    session = Path(session_dir)
    video = session / "camera.avi"
    manifest_file = session / "camera.video.json"
    if not video.exists() and not manifest_file.exists():
        return None
    if not video.is_file() or not manifest_file.is_file():
        raise ValueError("Camera video or its manifest is missing")
    manifest = read_json(manifest_file)
    video_hash = digest(video)
    if (manifest.get("schema_version") != "smartwear.recording_video.v1"
            or manifest.get("video_file") != video.name
            or manifest.get("video_sha256") != video_hash
            or manifest.get("camera_sha256") != digest(session / "camera.jsonl")):
        raise ValueError("Camera video does not match its manifest and camera data")
    kind = bridge_kind(payload)
    receipt_file = session / f"backend_recording_{kind}.receipt.json"
    if receipt_file.exists():
        receipt = read_json(receipt_file)
        if (receipt.get("video_sha256") == video_hash
                and receipt.get("backend_url") == base_url):
            return receipt
        raise ValueError("Existing recording receipt differs from current video/backend")
    url = (base_url.rstrip("/") + "/api/v1/sessions/"
           + quote(payload["session_id"]) + "/recording")
    result = request_json(url, "PUT", video.read_bytes(), api_key, "video/x-msvideo",
                          {"X-Content-SHA256": video_hash}, timeout=120)
    if result.get("session_id") != payload["session_id"]:
        raise RuntimeError("Backend returned a different recording session_id")
    receipt = {"schema_version": f"smartwear.backend_recording_{kind}.v1",
               "session_id": payload["session_id"], "backend_url": base_url,
               "video_sha256": video_hash, "recording_url": result["recording_url"]}
    with receipt_file.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return receipt


def source_archive_bytes(session_dir):
    """Package original AI observations and results without the separate AVI."""
    session = Path(session_dir).resolve()
    filenames = (
        "camera.jsonl", "camera.normalized.jsonl", "camera.video.json",
        "sensors.jsonl", "sensors.meta.json", "multimodal.jsonl",
        "action_segments.json", "keyframes.json", "session_role.json",
        "analysis_result.json", "backend_payload_demo.json",
        "backend_payload_demo.meta.json", "backend_payload_measured.json",
        "backend_payload_measured.meta.json", "hardware_capture.json",
        "camera_packets.jsonl", "wrist_raw.jsonl",
        "real_sensors.jsonl", "real_sensors.meta.json",
    )
    paths = [session / name for name in filenames if (session / name).is_file()]
    # Raw JPEG bytes always remain in the local session. Include them in the
    # backend's bounded ZIP only when the file is small enough for its API.
    raw_jpeg = session / "camera_raw.mjpeg"
    if (raw_jpeg.is_file() and
            sum(path.stat().st_size for path in paths) + raw_jpeg.stat().st_size
            <= 40 * 1024 * 1024):
        paths.append(raw_jpeg)
    keyframes = session / "keyframes"
    if keyframes.is_dir():
        paths.extend(sorted(keyframes.glob("*.png")))
    if not paths:
        raise ValueError("AI session has no source data to archive")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            resolved = path.resolve()
            if not resolved.is_relative_to(session):
                raise ValueError("AI source file escapes the session directory")
            entry = zipfile.ZipInfo(path.relative_to(session).as_posix(),
                                    date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, resolved.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def publish_source_data(session_dir, payload, base_url, api_key):
    session = Path(session_dir)
    content = source_archive_bytes(session)
    archive_hash = hashlib.sha256(content).hexdigest()
    kind = bridge_kind(payload)
    receipt_file = session / f"backend_source_data_{kind}.receipt.json"
    if receipt_file.exists():
        receipt = read_json(receipt_file)
        if (receipt.get("archive_sha256") == archive_hash
                and receipt.get("backend_url") == base_url):
            return receipt
        raise ValueError("Existing source-data receipt differs from current AI files/backend")
    url = (base_url.rstrip("/") + "/api/v1/sessions/"
           + quote(payload["session_id"]) + "/source-data")
    result = request_json(url, "PUT", content, api_key, "application/zip",
                          {"X-Content-SHA256": archive_hash}, timeout=120)
    if result.get("session_id") != payload["session_id"]:
        raise RuntimeError("Backend returned a different source-data session_id")
    receipt = {"schema_version": f"smartwear.backend_source_data_{kind}.v1",
               "session_id": payload["session_id"], "backend_url": base_url,
               "archive_sha256": archive_hash, "source_data_url": result["source_data_url"]}
    with receipt_file.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return receipt


def publish(session_dir, base_url="http://127.0.0.1:8000", api_key=None):
    payload, meta, images = build_payload(session_dir)
    save_payload(session_dir, payload, meta)
    session = Path(session_dir)
    kind = bridge_kind(payload)
    receipt_file = session / f"backend_publish_{kind}.receipt.json"
    payload_hash = hashlib.sha256(encoded(payload)).hexdigest()
    if receipt_file.exists():
        receipt = read_json(receipt_file)
        if receipt.get("payload_sha256") != payload_hash or receipt.get("backend_url") != base_url:
            raise ValueError("Existing publish receipt does not match current payload/backend")
    else:
        root = base_url.rstrip("/") + "/api/v1/sessions"
        response = request_json(root + "/ingest", "POST", encoded(payload), api_key)
        if response.get("session_id") != payload["session_id"]:
            raise RuntimeError("Backend returned a different session_id")
        for name, path in images.items():
            request_json(root + "/" + quote(payload["session_id"]) + "/keyframes/" + quote(name),
                         "PUT", path.read_bytes(), api_key, "image/png")
        receipt = {"schema_version": f"smartwear.backend_publish_{kind}.v1",
                   "session_id": payload["session_id"], "backend_url": base_url,
                   "payload_sha256": payload_hash, "uploaded_keyframes": sorted(images),
                   "backend_response": response}
        with receipt_file.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    publish_analysis(session_dir, payload, images, base_url, api_key)
    publish_recording(session_dir, payload, base_url, api_key)
    publish_source_data(session_dir, payload, base_url, api_key)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.getenv("SMARTWEAR_API_KEY"))
    args = parser.parse_args(argv)
    try:
        if args.publish:
            receipt = publish(args.session_dir, args.backend_url, args.api_key)
            print(f"Backend received {bridge_kind({'session_id': receipt['session_id']})} session: {receipt['session_id']}")
            if (args.session_dir / "analysis_result.json").is_file():
                print(f"Full DTW/Muda analysis: {args.backend_url.rstrip('/')}/api/v1/sessions/"
                      f"{receipt['session_id']}/analysis-result")
        else:
            payload, meta, _ = build_payload(args.session_dir)
            save_payload(args.session_dir, payload, meta)
            print(f"Payload: {args.session_dir / ('backend_payload_' + bridge_kind(payload) + '.json')}")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, f"Bridge failed: {exc}\n")


if __name__ == "__main__":
    main()
