"""Read diagnostics only when capture is stopped.

Opening a serial port can pulse control lines through the driver and reset an
ESP32-CAM-MB even without --reset. Do not use during camera/raw recording.
"""
import argparse
import concurrent.futures
import sys
import time

import serial


def read_port(port, reset=False):
    connection = serial.Serial(port=None, baudrate=115200, timeout=0.2)
    connection.dtr = False
    connection.rts = False
    connection.port = port
    try:
        connection.open()
        if reset:
            connection.rts = True
            time.sleep(0.1)
            connection.rts = False
        deadline = time.monotonic() + 10
        data = bytearray()
        while time.monotonic() < deadline:
            data.extend(connection.read(4096))
        # Keep diagnostics readable even if a driver repeats buffered output.
        lines = data.decode(errors="replace").splitlines()
        unique = list(dict.fromkeys(line for line in lines if line.strip()))
        return port, "\n".join(unique[-60:])[-10000:] or "(no serial output)"
    except serial.SerialException as exc:
        return port, str(exc)
    finally:
        connection.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ports", nargs="+")
    parser.add_argument("--reset", action="store_true", help="Pulse EN through RTS before reading")
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        for port, output in pool.map(lambda port: read_port(port, args.reset), args.ports):
            print(f"{port}:\n{output}")
