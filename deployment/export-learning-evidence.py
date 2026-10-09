"""Download a reviewed before/after report and verify its source archives."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode, urljoin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    query = urlencode({'before_session_id': args.before, 'after_session_id': args.after})
    with urlopen(args.url.rstrip('/')+'/api/v1/knowledge/learning-experiment?'+query, timeout=30) as response:
        report = json.load(response)
    checks = []
    for item in report['source_evidence']:
        digest, size = hashlib.sha256(), 0
        with urlopen(urljoin(args.url, item['source_url']), timeout=60) as response:
            while chunk := response.read(1024*1024):
                digest.update(chunk)
                size += len(chunk)
        checks.append({'session_id': item['session_id'], 'ok': digest.hexdigest() == item['archive_sha256']
                       and size == item['archive_bytes'], 'sha256': digest.hexdigest(), 'bytes': size})
    report['download_verification'] = checks
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Evidence reports are new snapshots; an existing report is not overwritten.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f"Evidence ready: {report['evidence_ready']}; archives verified: {len(checks)}; output: {args.output}")
    return 0 if report['evidence_ready'] and checks and all(c['ok'] for c in checks) else 2

if __name__ == '__main__':
    raise SystemExit(main())
