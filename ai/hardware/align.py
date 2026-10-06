"""Align measured right-wrist ADC/IMU to camera device time without fake values."""

import argparse
import bisect
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sensors.simulate_sensors import read_camera_records, write_sensor_records
from hardware.mqtt_wrist import validate_wrist_payload


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def align_session(session, window_ms=10, force_channel=None, device_id="smartwrist-user01"):
    session = Path(session).resolve()
    camera_file = session / "camera.normalized.jsonl"
    wrist_file = session / "wrist_raw.jsonl"
    output = session / "real_sensors.jsonl"
    metadata_file = session / "real_sensors.meta.json"
    if output.exists() or metadata_file.exists():
        raise FileExistsError("Measured sensor output already exists")
    if type(window_ms) is not int or not 0 < window_ms <= 500:
        raise ValueError("Alignment window must be 1..500 ms")
    if force_channel is not None and (type(force_channel) is not int or not 0 <= force_channel < 4):
        raise ValueError("Force channel must be 0..3 or omitted")
    if not device_id or not all(c.isalnum() or c in "_-" for c in device_id):
        raise ValueError("Device ID must contain only letters, digits, _ or -")
    camera = list(read_camera_records(camera_file))
    if not camera or any(frame.get("schema_version") != "smartwear.camera.v2" for frame in camera):
        raise ValueError("Normalized v2 camera data is required")
    epochs = [frame.get("source_epoch_ms") for frame in camera]
    if any(type(epoch) is not int or epoch < 1_577_836_800_000 for epoch in epochs):
        raise ValueError("Camera source epoch is absent or invalid")
    if any(right <= left for left, right in zip(epochs, epochs[1:])):
        raise ValueError("Camera clock did not increase; do not merge across clock reset")
    raw = []
    with wrist_file.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            item = json.loads(line)
            sample = validate_wrist_payload(item)
            if type(item.get("generation")) is not int or item["generation"] < 0:
                raise ValueError("Wrist device generation is missing")
            sample["generation"] = item["generation"]
            raw.append(sample)
    if not raw or len({item["generation"] for item in raw}) != 1:
        raise ValueError("No wrist samples or wrist reboot/clock reset within this session")
    wrist_epochs = [item["t_ms"] for item in raw]
    if any(right <= left for left, right in zip(wrist_epochs, wrist_epochs[1:])):
        raise ValueError("Wrist timestamps did not increase")
    rows, offsets = [], []
    for frame, epoch in zip(camera, epochs):
        place = bisect.bisect_left(wrist_epochs, epoch)
        options = [raw[index] for index in (place - 1, place) if 0 <= index < len(raw)]
        nearest = min(options, key=lambda item: abs(item["t_ms"] - epoch)) if options else None
        matched = nearest is not None and abs(nearest["t_ms"] - epoch) <= window_ms
        if matched:
            offset = nearest["t_ms"] - epoch
            offsets.append(offset)
            imu = {axis: nearest["acc"][index] for index, axis in enumerate(("ax", "ay", "az"))}
            imu.update({axis: nearest["gyro"][index] for index, axis in enumerate(("gx", "gy", "gz"))})
        else:
            offset, imu = None, None
        right = {"tracking_status": frame["hand_actions"]["right"]["tracking_status"],
                 "sensor_status": "matched" if matched else "missing",
                 "imu_wrist": imu,
                 "force_emg_raw": (nearest["force"][force_channel]
                                   if matched and force_channel is not None else None),
                 "force_adc": nearest["force"] if matched else None,
                 "force_channel": force_channel,
                 "torque": None,
                 "source_epoch_ms": nearest["t_ms"] if matched else None,
                 "source_seq": nearest["seq"] if matched else None,
                 "alignment_offset_ms": offset}
        rows.append({"schema_version": "smartwear.sensors.v2",
                     "sensor_source": "measured_hardware",
                     "timestamp_ms": frame["timestamp_ms"], "imu_head": None,
                     "hand_sensors": {
                         "left": {"tracking_status": frame["hand_actions"]["left"]["tracking_status"],
                                  "imu_wrist": None, "force_emg_raw": None,
                                  "force_adc": None, "torque": None},
                         "right": right}})
    if not offsets:
        raise ValueError("No wrist sample matched a camera frame; no simulated fallback")
    count, last = write_sensor_records(output, rows)
    metadata = {
        "schema_version": "smartwear.sensors_meta.v2",
        "source": "measured_hardware", "sensor_source": "SmartWrist MQTT",
        "camera_sha256": sha256(camera_file), "sensors_sha256": sha256(output),
        "raw_wrist_sha256": sha256(wrist_file),
        "camera_raw_sha256": sha256(session / "camera.jsonl"),
        "sample_count": count, "first_timestamp_ms": camera[0]["timestamp_ms"],
        "last_timestamp_ms": last, "matched_count": len(offsets),
        "missing_count": count - len(offsets),
        "alignment_window_ms": window_ms,
        "max_abs_alignment_offset_ms": max(map(abs, offsets)),
        "mean_abs_alignment_offset_ms": round(statistics.fmean(map(abs, offsets)), 3),
        "median_alignment_offset_ms": statistics.median(offsets),
        "p95_abs_alignment_offset_ms": sorted(map(abs, offsets))[
            min(len(offsets) - 1, int(0.95 * len(offsets)))],
        "alignment_offset_distribution": {
            "wrist_before_camera": sum(value < 0 for value in offsets),
            "same_epoch_ms": sum(value == 0 for value in offsets),
            "wrist_after_camera": sum(value > 0 for value in offsets)},
        "device_id": device_id, "force_channel": force_channel,
        "calibration_id": (f"uncalibrated_{device_id}_adc_channel_{force_channel}"
                           if force_channel is not None else
                           f"uncalibrated_{device_id}_four_channel_adc"),
        "units": {"force": "adc_count", "torque": "unavailable",
                  "angle": "unavailable", "acceleration": "firmware_acc_raw_unverified",
                  "angular_speed": "firmware_gyro_raw_unverified"},
        "simulated_fields": [],
        "clock_note": "Device NTP epoch was used; nearest-sample offset is not a measured clock accuracy guarantee",
    }
    with metadata_file.open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--window-ms", type=int, default=10)
    parser.add_argument("--force-channel", type=int)
    parser.add_argument("--device-id", default="smartwrist-user01")
    args = parser.parse_args(argv)
    info = align_session(args.session, args.window_ms, args.force_channel, args.device_id)
    print(f"Measured wrist alignment: {info['matched_count']}/{info['sample_count']} "
          f"matched, {info['missing_count']} missing; "
          f"p95 abs offset {info['p95_abs_alignment_offset_ms']} ms, "
          f"max {info['max_abs_alignment_offset_ms']} ms")


if __name__ == "__main__":
    main()
