import json
import os
from pathlib import Path

import httpx


SAMPLE_PATH = Path(__file__).parent / "shared" / "sample" / "analysis_result.example.json"
INGEST_URL = os.getenv(
    "SMARTWEAR_API_URL",
    "http://127.0.0.1:8000/api/v1/sessions/ingest",
)


def main():
    with SAMPLE_PATH.open(encoding="utf-8") as sample_file:
        payload = json.load(sample_file)

    response = httpx.post(INGEST_URL, json=payload, timeout=10.0)
    response.raise_for_status()
    print(f"HTTP {response.status_code}: {response.json()}")


if __name__ == "__main__":
    main()