"""Small LAN-only offline NTP reference using the gateway's clock (stratum 10).

Run on 192.168.137.1. This is a common relative time reference, not a claim of
UTC traceability. Do not run alongside Windows Time/Chrony on the same port.
"""
import argparse
import ipaddress
import socket
import struct
import time

NTP_DELTA = 2_208_988_800


def timestamp(unix_seconds):
    seconds = int(unix_seconds)
    return struct.pack("!II", (seconds + NTP_DELTA) & 0xffffffff,
                       int((unix_seconds - seconds) * (1 << 32)))


def reply(request, received, sent):
    if len(request) < 48 or request[0] & 7 != 3 or ((request[0] >> 3) & 7) not in (3, 4):
        raise ValueError("Expected NTP v3/v4 client request")
    if received < 1577836800:
        raise ValueError("Gateway clock is not set")
    packet = bytearray(48)
    packet[0] = (request[0] & 0x38) | 4
    packet[1] = 10
    packet[2] = 6
    packet[3] = 0xec  # -20 precision exponent; not a measured network accuracy.
    packet[8:12] = struct.pack("!I", 1 << 16)  # Conservative one-second UTC dispersion.
    packet[12:16] = b"LOCL"
    packet[16:24] = timestamp(received)
    packet[24:32] = request[40:48]
    packet[32:40] = timestamp(received)
    packet[40:48] = timestamp(sent)
    return bytes(packet)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="192.168.137.1")
    parser.add_argument("--port", type=int, default=123)
    parser.add_argument("--allow-subnet", default="192.168.137.0/24")
    args = parser.parse_args()
    allowed = ipaddress.ip_network(args.allow_subnet)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((args.bind, args.port))
        print(f"Offline NTP stratum 10: {args.bind}:{args.port}; allowed {allowed}", flush=True)
        while True:
            request, peer = server.recvfrom(512)
            received = time.time()
            if ipaddress.ip_address(peer[0]) not in allowed:
                continue
            try:
                response = reply(request, received, time.time())
            except ValueError:
                continue
            server.sendto(response, peer)


if __name__ == "__main__":
    main()
