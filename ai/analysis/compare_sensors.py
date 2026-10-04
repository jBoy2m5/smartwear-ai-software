"""Validate and summarize per-hand sensor signals for action-aligned sessions.

Preferred real input is real_sensors.jsonl plus real_sensors.meta.json in a
session. It must already be aligned to camera timestamps. Otherwise the
camera-conditioned simulator output is used, or regenerated in memory.
"""

import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
from sensors.simulate_sensors import read_sensor_records, simulate_from_camera  # noqa: E402

SIDES = ("left", "right")
METRICS = ("force_mean", "force_peak", "torque_mean", "torque_peak",
           "torque_angle_change", "head_acceleration_mean",
           "wrist_acceleration_mean", "wrist_angular_speed_mean",
           "head_angular_speed_mean")


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_sensor_stream(session):
    """Return validated rows, provenance and units; never relabel fake as real."""
    session = Path(session)
    camera_file = session / "camera.normalized.jsonl"
    camera = [json.loads(line) for line in camera_file.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    if not camera or any(frame.get("schema_version") != "smartwear.camera.v2"
                         for frame in camera):
        raise ValueError(f"Two-hand normalized camera data is required: {session}")
    real = session / "real_sensors.jsonl"
    generated = session / "sensors.jsonl"
    if real.exists() or generated.exists():
        path = real if real.exists() else generated
        meta_path = path.with_suffix(".meta.json")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        source = metadata.get("source")
        expected = "measured_hardware" if path == real else "simulated_from_camera_observations"
        if (source != expected or metadata.get("schema_version") != "smartwear.sensors_meta.v2"
                or metadata.get("camera_sha256") != _sha256(camera_file)
                or metadata.get("sensors_sha256") != _sha256(path)):
            raise ValueError(f"Sensor source, schema or SHA-256 does not match: {path}")
        rows = list(read_sensor_records(path))
        if source == "measured_hardware" and any(
                row.get("sensor_source") != "measured_hardware" for row in rows):
            raise ValueError("Measured metadata cannot describe simulated sensor rows")
        if (metadata.get("sample_count") != len(camera)
                or metadata.get("first_timestamp_ms") != camera[0]["timestamp_ms"]
                or metadata.get("last_timestamp_ms") != camera[-1]["timestamp_ms"]):
            raise ValueError(f"Sensor count or time range does not match camera: {path}")
        if source == "measured_hardware":
            calibration = metadata.get("calibration_id")
            units = metadata.get("units")
            if (not isinstance(calibration, str) or not calibration.strip()
                    or not isinstance(units, dict)
                    or any(not isinstance(units.get(key), str) or not units[key].strip()
                           for key in ("force", "torque", "angle", "acceleration", "angular_speed"))):
                raise ValueError("Measured sensors require calibration_id and explicit units")
            units = {key: units[key] for key in
                     ("force", "torque", "angle", "acceleration", "angular_speed")}
        else:
            calibration = None
            units = {"force": "arbitrary_simulator_units", "torque": "assumed_N_m",
                     "angle": "assumed_degrees",
                     "acceleration": "assumed_m_s2", "angular_speed": "assumed_rad_s"}
    else:
        rows = list(simulate_from_camera(camera))
        source = "simulated_in_memory_from_camera"
        calibration = None
        units = {"force": "arbitrary_simulator_units", "torque": "assumed_N_m",
                 "angle": "assumed_degrees",
                 "acceleration": "assumed_m_s2", "angular_speed": "assumed_rad_s"}
        path = None
    if len(rows) != len(camera):
        raise ValueError("Sensor and camera frame counts do not match")
    for index, (sensor, frame) in enumerate(zip(rows, camera)):
        if (sensor.get("schema_version") != "smartwear.sensors.v2"
                or sensor["timestamp_ms"] != frame["timestamp_ms"]
                or any(sensor["hand_sensors"][side]["tracking_status"] !=
                       frame["hand_actions"][side]["tracking_status"] for side in SIDES)):
            raise ValueError(f"Sensor timestamp or hand status mismatch at row {index}")
    provenance = {"source": source, "sensor_file": path.name if path else None,
                  "sensor_sha256": _sha256(path) if path else None,
                  "calibration_id": calibration, "units": units,
                  "time_alignment": "exact_camera_timestamps_required"}
    return rows, provenance


def _magnitude(values, axes):
    return math.sqrt(sum(values[axis] ** 2 for axis in axes))


def summarize_segment(rows, segment):
    side = segment["hand"]
    first, last = segment["start_frame_id"], segment["end_frame_id"]
    if (type(first) is not int or type(last) is not int or first < 0
            or last < first or last >= len(rows)):
        raise ValueError("Segment frame range is outside the sensor recording")
    samples = [row for row in rows[first:last + 1]
               if row["hand_sensors"][side]["tracking_status"] == "detected"
               and (row["hand_sensors"][side].get("force_emg_raw") is not None
                    or row["hand_sensors"][side].get("force_adc") is not None)]
    if not samples:
        return {"sample_count": 0, **{metric: None for metric in METRICS},
                "force_adc_mean": None, "force_adc_peak": None}
    hand = [row["hand_sensors"][side] for row in samples]
    force = [value["force_emg_raw"] for value in hand
             if value.get("force_emg_raw") is not None]
    adc = [value["force_adc"] for value in hand if value.get("force_adc") is not None]
    torque = [abs(value["torque"]["torque"]) for value in hand if value.get("torque")]
    angles = [value["torque"]["angle"] for value in hand if value.get("torque")]
    head_accel = [_magnitude(row["imu_head"], ("ax", "ay", "az")) for row in samples
                  if row.get("imu_head")]
    wrist_accel = [_magnitude(value["imu_wrist"], ("ax", "ay", "az")) for value in hand
                   if value.get("imu_wrist")]
    wrist_gyro = [_magnitude(value["imu_wrist"], ("gx", "gy", "gz")) for value in hand
                  if value.get("imu_wrist")]
    head_gyro = [_magnitude(row["imu_head"], ("gx", "gy", "gz")) for row in samples
                 if row.get("imu_head")]
    mean = lambda values: round(statistics.fmean(values), 4) if values else None
    return {"sample_count": len(samples),
            "force_mean": mean(force),
            "force_peak": round(max(force), 4) if force else None,
            "force_adc_mean": ([round(statistics.fmean(value[i] for value in adc), 4)
                                for i in range(4)] if adc else None),
            "force_adc_peak": ([max(value[i] for value in adc) for i in range(4)]
                                if adc else None),
            "torque_mean": mean(torque),
            "torque_peak": round(max(torque), 4) if torque else None,
            "torque_angle_change": round(angles[-1] - angles[0], 4) if angles else None,
            "head_acceleration_mean": mean(head_accel),
            "wrist_acceleration_mean": mean(wrist_accel),
            "wrist_angular_speed_mean": mean(wrist_gyro),
            "head_angular_speed_mean": mean(head_gyro)}


def compare_sensor_segments(expert_session, worker_session, action_document):
    expert_rows, expert_source = load_sensor_stream(expert_session)
    worker_rows, worker_source = load_sensor_stream(worker_session)
    expert_doc = json.loads((Path(expert_session) / "action_segments.json").read_text(encoding="utf-8"))
    worker_doc = json.loads((Path(worker_session) / "action_segments.json").read_text(encoding="utf-8"))
    expert_segments = {segment["segment_id"]: segment for segment in expert_doc["segments"]}
    worker_segments = {segment["segment_id"]: segment for segment in worker_doc["segments"]}
    expert_real = expert_source["source"] == "measured_hardware"
    worker_real = worker_source["source"] == "measured_hardware"
    compatible = (expert_source["units"] == worker_source["units"]
                  and expert_source["calibration_id"] == worker_source["calibration_id"])
    if expert_real and worker_real and compatible:
        status = "measured_comparison"
    elif not expert_real and not worker_real:
        status = "simulated_demo_comparison"
    else:
        status = "incompatible_sources_no_numeric_delta"
    tracks = {}
    for side in SIDES:
        pairs = []
        for aligned in action_document["hands"][side]["alignment"]:
            e = expert_segments[aligned["expert_segment_id"]]
            w = worker_segments[aligned["worker_segment_id"]]
            if e["hand"] != side or w["hand"] != side:
                raise ValueError("Aligned action segment hand does not match sensors")
            es = summarize_segment(expert_rows, e)
            ws = summarize_segment(worker_rows, w)
            pair_status = ("different_visible_action" if not aligned["same_label"] else
                           "incompatible_sources" if status == "incompatible_sources_no_numeric_delta"
                           else "comparable")
            delta = ({metric: (round(ws[metric] - es[metric], 4)
                               if ws[metric] is not None and es[metric] is not None else None)
                      for metric in METRICS}
                     if pair_status == "comparable"
                     and es["sample_count"] and ws["sample_count"] else None)
            pairs.append({"expert_segment_id": e["segment_id"],
                          "worker_segment_id": w["segment_id"],
                          "expert_label": e["label"], "worker_label": w["label"],
                          "comparison_status": pair_status,
                          "expert": es, "worker": ws, "worker_minus_expert": delta,
                          "worker_minus_expert_adc": (
                              [round(w - x, 4) for w, x in zip(ws["force_adc_mean"],
                                                                  es["force_adc_mean"])]
                              if pair_status == "comparable"
                              and ws["force_adc_mean"] is not None
                              and es["force_adc_mean"] is not None else None)})
        tracks[side] = {"status": "compared" if pairs else "insufficient_visible_actions",
                        "pairs": pairs}
    return {"status": status, "expert_source": expert_source,
            "worker_source": worker_source,
            "difference_note": ("Measured differences use matching raw units/device mappings; "
                                "ADC counts are not Newton. DEMO differences are illustrative."),
            "force_note": ("Measured force_emg_raw is a selected ADC channel only when its "
                           "mapping is configured; all four raw channels remain available. "
                           "ADC counts are not Newton or sEMG."),
            "hands": tracks}
