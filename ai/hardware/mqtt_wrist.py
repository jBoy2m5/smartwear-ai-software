"""Validated bounded MQTT wrist receiver with append-only raw recording."""

import json
import math
import queue
import threading
import time
from collections import Counter
from pathlib import Path
from hardware.live_alignment import WristBuffer


def validate_wrist_payload(payload):
    value = payload if isinstance(payload, dict) else json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Wrist payload must be an object")
    epoch, sequence = value.get("t_ms"), value.get("seq")
    if (type(epoch) is not int or epoch < 1_577_836_800_000
            or type(sequence) is not int or sequence < 0):
        raise ValueError("Invalid wrist epoch or sequence")
    imu_status = value.get("imu_status", "ok")
    if imu_status not in ("ok", "unavailable"):
        raise ValueError("Invalid IMU status")
    if imu_status == "unavailable" and ("acc" not in value or "gyro" not in value
                                       or value["acc"] is not None or value["gyro"] is not None):
        raise ValueError("Unavailable IMU must explicitly contain null acc and gyro")
    for field, count in (("acc", 3), ("gyro", 3), ("force", 4)):
        if field in ("acc", "gyro") and imu_status == "unavailable":
            continue
        readings = value.get(field)
        if (not isinstance(readings, list) or len(readings) != count
                or any(type(item) not in (int, float) or not math.isfinite(item)
                       for item in readings)):
            raise ValueError(f"Invalid wrist {field} vector")
    if any(type(sample) is not int or not 0 <= sample <= 4095 for sample in value["force"]):
        raise ValueError("FSR ADC channels must be 0..4095 integer counts")
    result = {"t_ms": epoch, "seq": sequence,
            "acc": value["acc"], "gyro": value["gyro"],
            "force": [int(item) for item in value["force"]]}
    if "imu_status" in value:
        result["imu_status"] = imu_status
    if "imu_address" in value:
        address = value["imu_address"]
        if ((imu_status == "unavailable" and address is not None)
                or (imu_status == "ok" and (type(address) is not int or address not in (0x68, 0x69)))):
            raise ValueError("Invalid IMU address/status")
        result["imu_address"] = address
    if "imu_age_ms" in value:
        age = value["imu_age_ms"]
        if ((imu_status == "unavailable" and age is not None)
                or (imu_status == "ok" and (type(age) is not int or not 0 <= age <= 40))):
            raise ValueError("Invalid or stale IMU age")
        result["imu_age_ms"] = age
    return result


class WristReceiver:
    def __init__(self, path, host, topic="wearable/user01/wrist/data", port=1883,
                 queue_size=1024):
        self.path = Path(path)
        self.host, self.port, self.topic = host, port, topic
        self.pending = queue.Queue(maxsize=queue_size)
        self.counters = Counter()
        self.connected = threading.Event()
        self.finished = threading.Event()
        self.lock = threading.Lock()
        self.client = None
        self.writer = None
        self.last_seq = None
        self.last_epoch = None
        self.generation = 0
        self.writer_error = None
        self.last_received_epoch_ms = None
        self.buffer = WristBuffer(maxlen=100)

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        if reason_code == 0:
            client.subscribe(self.topic, qos=0)
            self.connected.set()
            with self.lock:
                self.counters["connects"] += 1
        else:
            self.connected.clear()

    def _on_disconnect(self, _client, _userdata, _flags, _reason_code, _properties):
        self.connected.clear()
        with self.lock:
            self.counters["disconnects"] += 1

    def _on_message(self, _client, _userdata, message):
        if message.topic != self.topic:
            return
        try:
            if len(message.payload) > 4096:
                raise ValueError("Oversized wrist JSON")
            sample = validate_wrist_payload(message.payload)
            sample["raw_payload"] = message.payload.decode("utf-8")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            with self.lock:
                self.counters["malformed"] += 1
            return
        sample["received_epoch_ms"] = time.time_ns() // 1_000_000
        sample["received_monotonic_ns"] = time.monotonic_ns()
        sample["topic"] = message.topic
        try:
            self.pending.put_nowait(sample)
        except queue.Full:
            with self.lock:
                self.counters["dropped_queue"] += 1

    def _write_loop(self):
        try:
            with self.path.open("x", encoding="utf-8", newline="\n") as stream:
                while not self.finished.is_set() or not self.pending.empty():
                    try:
                        sample = self.pending.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    sequence, epoch = sample["seq"], sample["t_ms"]
                    with self.lock:
                        if self.last_seq is not None:
                            if sequence <= self.last_seq or epoch <= self.last_epoch:
                                self.generation += 1
                                self.counters["resets"] += 1
                            elif sequence > self.last_seq + 1:
                                self.counters["seq_gaps"] += sequence - self.last_seq - 1
                        self.last_seq, self.last_epoch = sequence, epoch
                        self.last_received_epoch_ms = sample["received_epoch_ms"]
                        sample["generation"] = self.generation
                        self.counters["received"] += 1
                    self.buffer.append(sample)
                    stream.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
                    stream.flush()
                    self.pending.task_done()
        except Exception as exc:
            self.writer_error = exc

    def start(self, wait_s=5):
        import paho.mqtt.client as mqtt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(self.path)
        self.writer = threading.Thread(target=self._write_loop, daemon=True)
        self.writer.start()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"smartwear-collector-{time.time_ns():x}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()
        if not self.connected.wait(wait_s):
            self.stop()
            raise ConnectionError(f"MQTT wrist topic unavailable at {self.host}:{self.port}")

    def stop(self):
        if self.client is not None:
            self.client.disconnect()
            self.client.loop_stop()
        self.finished.set()
        if self.writer is not None:
            self.writer.join(timeout=10)
            if self.writer.is_alive():
                raise RuntimeError("Wrist raw writer did not finish")
        if self.writer_error is not None:
            raise RuntimeError(f"Wrist raw writer failed: {self.writer_error}")

    def snapshot(self):
        with self.lock:
            result = dict(self.counters)
            received = self.last_received_epoch_ms
        result["connected"] = self.connected.is_set()
        result["queue_size"] = self.pending.qsize()
        result["newest_sample_age_ms"] = (max(0, time.time_ns() // 1_000_000 - received)
                                          if received is not None else None)
        return result
