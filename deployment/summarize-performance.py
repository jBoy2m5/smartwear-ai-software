"""Compare source delivery and AI retention; avoids treating scene changes as speedup."""
import json
import math
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def summarize(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if 'source_session' not in value:
        return value
    session = ROOT/'ai/generated_data/sessions'/value['source_session']
    rows = [json.loads(line) for line in (session/'camera_packets.jsonl').read_text().splitlines()]
    intervals = sorted(b['epoch_ms']-a['epoch_ms'] for a,b in zip(rows,rows[1:]))
    span = (rows[-1]['epoch_ms']-rows[0]['epoch_ms'])/1000 if len(rows)>1 else None
    capture = value['capture']
    return {'source_session':value['source_session'], 'source_fps':round((len(rows)-1)/span,3) if span else None,
            'interval_p50_ms':intervals[math.ceil(len(intervals)*.5)-1] if intervals else None,
            'interval_p95_ms':intervals[math.ceil(len(intervals)*.95)-1] if intervals else None,
            'jpeg_mean_bytes':round(sum(r['length'] for r in rows)/len(rows)) if rows else None,
            'received_jpeg':len(rows), 'inferred_frames':capture['inferred_frames'],
            'inference_retention_pct':round(capture['inferred_frames']/len(rows)*100,2) if rows else None,
            'dropped_for_inference':capture['camera_stats'].get('dropped_for_inference',0),
            'stream_errors':capture['camera_stats'].get('stream_errors',0),
            'performance':value.get('performance')}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = {'runs': [summarize(path) for path in args.paths],
              'limitations': ['Live runs use different camera images and host load; no causal FPS speedup is claimed.',
                              'Source FPS uses device timestamps; AI retention includes queued frames at stop.',
                              'Technical benchmarks do not provide human learning outcomes.']}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
