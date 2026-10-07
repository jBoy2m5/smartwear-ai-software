"""Observe four measured FSR ADC channels over MQTT without opening serial."""
import argparse
import json
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--duration-s', type=int, default=60)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
rows = []
lock = threading.Lock()

def receive(client, userdata, message):
    row = json.loads(message.payload)
    row['received_epoch_ms'] = time.time_ns() // 1_000_000
    with lock:
        rows.append(row)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = lambda c, u, f, r, p: c.subscribe('wearable/user01/wrist/data')
client.on_message = receive
client.connect('192.168.137.1', 1883)
client.loop_start()
started = time.monotonic()
seen = 0
print('Monitoring four FSR ADC channels; press/release each sensor.', flush=True)
try:
    while time.monotonic() - started < args.duration_s:
        time.sleep(1)
        with lock:
            batch = rows[seen:]
            seen = len(rows)
        if not batch:
            print(f'{time.monotonic()-started:.0f}s: no samples', flush=True)
            continue
        values = [row['force'] for row in batch]
        ranges = [(min(v[i] for v in values), max(v[i] for v in values)) for i in range(4)]
        print(f'{time.monotonic()-started:.0f}s ADC={values[-1]} ranges={ranges}', flush=True)
finally:
    client.loop_stop()
    client.disconnect()
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row) + '\n')
print(f'Total samples: {len(rows)}', flush=True)
if rows:
    print('Overall ADC ranges:', [(min(r['force'][i] for r in rows),
                                 max(r['force'][i] for r in rows)) for i in range(4)], flush=True)
