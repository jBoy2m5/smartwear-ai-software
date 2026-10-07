"""Summarize saved hardware inputs and extract a camera frame for inspection."""
import argparse
import collections
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('session', type=Path)
parser.add_argument('--preview', type=Path)
args = parser.parse_args()
for name in ('raw_capture.json', 'hardware_capture.json', 'real_sensors.meta.json', 'alignment_report.json'):
    path = args.session / name
    if path.is_file():
        print(name, path.read_text(encoding='utf-8'))
rows = [json.loads(line) for line in (args.session / 'wrist_raw.jsonl').read_text().splitlines() if line.strip()]
print('Wrist records:', len(rows))
if rows:
    print('First wrist record:', rows[0])
    payloads = [row.get('payload', row) for row in rows]
    print('IMU status:', dict(collections.Counter(row.get('imu_status') for row in payloads)))
    forces = [row['force'] for row in payloads if isinstance(row.get('force'), list)]
    if forces:
        print('ADC ranges:', [(min(row[i] for row in forces), max(row[i] for row in forces)) for i in range(4)])
camera = args.session / 'camera.jsonl'
if camera.is_file():
    frames = [json.loads(line) for line in camera.read_text().splitlines() if line.strip()]
    print('Camera inference records:', len(frames))
    if frames:
        print('First inference record:', frames[0])
        for side in ('left', 'right'):
            print(side, 'tracking:', dict(collections.Counter(
                frame.get('hand_actions', {}).get(side, {}).get('tracking_status') for frame in frames)))
            print(side, 'labels:', dict(collections.Counter(
                frame.get('hand_actions', {}).get(side, {}).get('label') for frame in frames)))
        print('Both hands detected:', sum(all(
            frame.get('hand_actions', {}).get(side, {}).get('tracking_status') == 'detected'
            for side in ('left', 'right')) for frame in frames))
if args.preview:
    import cv2
    import numpy as np
    packets = [json.loads(line) for line in (args.session / 'camera_packets.jsonl').read_text().splitlines()]
    packet = packets[len(packets) // 2]
    with (args.session / 'camera_raw.mjpeg').open('rb') as stream:
        stream.seek(packet['offset'])
        frame = cv2.imdecode(np.frombuffer(stream.read(packet['length']), np.uint8), cv2.IMREAD_COLOR)
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    if frame is None or not cv2.imwrite(str(args.preview), frame):
        raise RuntimeError('Cannot extract camera preview')
    print('Preview mean brightness:', float(frame.mean()))
