"""Measured technical capture; never creates an expert or learner review."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ai'))

def main():
    from hardware.record_hardware import record_hardware
    from hardware.config import HardwareConfig
    from integration.frontend_capture import encode_and_publish_preview
    from concurrent.futures import ThreadPoolExecutor
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-s', type=int, default=20)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    job = args.output.parent / (args.output.stem + '-preview')
    job.mkdir(parents=True, exist_ok=True)
    pending = None
    last = 0
    published = 0
    config = HardwareConfig.from_environment()
    with ThreadPoolExecutor(max_workers=1) as executor:
        def preview(cv2, frame, data):
            nonlocal pending, last, published
            now = time.monotonic()
            if pending is not None:
                if not pending.done():
                    return
                pending.result()
            if now - last < .1:
                return
            pending = executor.submit(encode_and_publish_preview, cv2, frame.copy(), data, job)
            last = now
            published += 1
        started = time.monotonic()
        try:
            output = record_hardware(camera_url=config.camera_url, mqtt_host=config.mqtt_host,
                mqtt_port=config.mqtt_port, topic=config.topic, duration_s=args.duration_s,
                show_window=False, on_frame=preview,
                capture_context={'role': 'demo', 'trial_stage': 'technical',
                                 'purpose': 'performance_benchmark'})
            marker = json.loads((output.parent / 'hardware_capture.json').read_text(encoding='utf-8'))
            report = {'source_session': output.parent.name, 'capture': marker,
                      'elapsed_total_s': round(time.monotonic()-started, 3),
                      'preview_submitted': published, 'kind': 'measured_technical_benchmark'}
            timing = output.parent / 'performance.json'
            if timing.is_file():
                report['performance'] = json.loads(timing.read_text(encoding='utf-8'))
        except Exception as exc:
            report = {'status': 'failed', 'error': str(exc),
                      'kind': 'measured_technical_benchmark'}
        if pending is not None:
            pending.result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report.get('status') == 'failed' else 0

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
