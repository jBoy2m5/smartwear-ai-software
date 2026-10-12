"""Non-streaming device checks. A TCP listener is not proof of valid images."""
import json
import socket
import struct
import time
from urllib.request import urlopen
from urllib.parse import urlsplit


def tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=.6):
            return True
    except OSError:
        return False


def ntp(host):
    from ai.hardware.ntp_server import timestamp
    packet = bytearray(48)
    packet[0] = 0x23
    packet[40:48] = timestamp(time.time())
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(.6)
            client.connect((host, 123))
            client.send(packet)
            reply = client.recv(512)
        return (len(reply) >= 48 and reply[0] & 7 == 4 and reply[0] >> 6 != 3
                and 1 <= reply[1] <= 15 and reply[24:32] == packet[40:48])
    except OSError:
        return False


def diagnose(config, active=False):
    camera = urlsplit(config.camera_url)
    board = None
    # A separate HTTP server lets status remain available during the synchronous stream.
    try:
        with urlopen(f'http://{camera.hostname}:82/status', timeout=.6) as response:
            board = json.loads(response.read(4097))
        if not isinstance(board, dict) or board.get('schema') != 'smartwear.cap.status/1':
            board = None
    except (OSError, ValueError):
        pass
    reachable = bool(board) or (not active and tcp(camera.hostname, camera.port or 80))
    mqtt_ok, ntp_ok = tcp(config.mqtt_host, config.mqtt_port), ntp(config.mqtt_host)
    camera_status = ('ready' if board and board.get('camera_ready') and board.get('ntp_ready')
                     else 'starting' if board else 'in_use' if active else
                     'tcp_only' if reachable else 'unreachable')
    return {'checked_epoch_ms': time.time_ns() // 1_000_000,
            'camera': {'state': camera_status, 'board': board,
                       'message': {'ready': 'Camera và đồng hồ đã khởi tạo; ảnh được kiểm khi quay.',
                           'starting': 'Bo đang khởi tạo camera hoặc đồng bộ giờ.',
                           'in_use': 'Camera đang được phiên quay sử dụng.',
                           'tcp_only': 'Cổng camera mở; firmware chưa có chẩn đoán boot.',
                           'unreachable': 'Không kết nối được camera; kiểm tra nguồn và hotspot.'}[camera_status]},
            'mqtt': {'ok': mqtt_ok, 'message': 'Broker kết nối được; mẫu vòng tay được kiểm khi quay.' if mqtt_ok else 'MQTT chưa kết nối được.'},
            'ntp': {'ok': ntp_ok}, 'capture_active': active,
            'can_start': not active and camera_status in ('ready', 'tcp_only') and mqtt_ok and ntp_ok}
