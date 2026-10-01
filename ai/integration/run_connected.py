"""Record with the existing camera pipeline, then send its DEMO contract to backend."""

import argparse
import os
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from camera_test import finish_recording, record_camera  # noqa: E402
from integration.backend_bridge import publish  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("expert", "worker"))
    parser.add_argument("--expert-session", type=Path)
    parser.add_argument("--practice-sample")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.getenv("SMARTWEAR_API_KEY"))
    args = parser.parse_args(argv)
    if args.role == "worker" and args.expert_session is None:
        parser.error("--role worker requires --expert-session")
    if args.role != "worker" and args.expert_session is not None:
        parser.error("--expert-session requires --role worker")
    if args.practice_sample and args.role:
        parser.error("--practice-sample cannot be combined with --role")
    try:
        output = record_camera()
        finish_recording(output, args.role, args.expert_session, args.practice_sample)
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        parser.exit(1, f"Camera/analysis failed: {exc}\n")
    try:
        receipt = publish(output.parent, args.backend_url, args.api_key)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Camera data remains in {output.parent}; backend send failed: {exc}\n"
                    f"Retry: python -B ai/integration/backend_bridge.py '{output.parent}' --publish\n")
    print(f"Backend received DEMO session: {receipt['session_id']}")
    print(f"Full DTW/Muda analysis: {args.backend_url.rstrip('/')}/api/v1/sessions/"
          f"{receipt['session_id']}/analysis-result")
    print(f"Session folder: {output.parent}")


if __name__ == "__main__":
    main()
