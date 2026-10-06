"""Read-only LAN/dependency checks; writes a report without consuming camera stream."""
import argparse
import importlib.util
import json
import socket
import struct
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware.config import HardwareConfig
from hardware.ntp_server import timestamp, NTP_DELTA
from urllib.parse import urlsplit


def check_tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return {"ok": True}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def check_ntp(host):
    request = bytearray(48)
    request[0] = 0x23
    request[40:48] = timestamp(time.time())
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(2)
            client.connect((host, 123))
            client.send(request)
            response = client.recv(512)
        if (len(response) < 48 or response[0] & 7 != 4 or response[0] >> 6 == 3
                or not 1 <= response[1] <= 15 or response[24:32] != request[40:48]):
            raise ValueError("Invalid or unsynchronized NTP response")
        seconds, fraction = struct.unpack("!II", response[40:48])
        return {"ok": True, "stratum": response[1],
                "server_epoch": seconds - NTP_DELTA + fraction / (1 << 32)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/layer1-layer3/preflight.json"))
    args = parser.parse_args()
    config = HardwareConfig.from_environment()
    camera = urlsplit(config.camera_url)
    checks = {"camera_tcp": check_tcp(camera.hostname, camera.port or 80),
              "mqtt_tcp": check_tcp(config.mqtt_host, config.mqtt_port),
              "ntp": check_ntp(config.mqtt_host),
              "dependencies": {name: importlib.util.find_spec(name) is not None
                               for name in ("cv2", "mediapipe", "paho", "fastapi")}}
    result = {"config": config.__dict__, "checked_epoch_ms": time.time_ns() // 1_000_000,
              "checks": checks,
              "note": "Open TCP ports do not prove valid JPEG/MQTT samples or timing KPIs."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if (all(checks[k]["ok"] for k in ("camera_tcp", "mqtt_tcp", "ntp"))
                 and all(checks["dependencies"].values())) else 2


if __name__ == "__main__":
    raise SystemExit(main())
