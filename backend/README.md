# SmartWear AI Backend

Production-oriented FastAPI service for receiving the immutable SmartWear analysis
contract, persisting normalized sessions, generating SOP reports, exporting ROS2
datasets, and streaming validated telemetry.

All backend source, tests, configuration, generated data, and container files are
owned by `backend/`. The service reads the AI interface contract but does not modify
or import implementation code from the AI module.

## Architecture

```text
backend/
|-- api/             HTTP authentication, dependencies, and REST routes
|-- core/            configuration, logging, and domain exceptions
|-- db/              SQLAlchemy engine, sessions, and transaction boundaries
|-- mock/            backend-owned telemetry simulator
|-- models/          normalized SQLAlchemy 2 models
|-- repositories/    persistence queries and aggregate mapping
|-- schemas/         strict Pydantic v2 contract and response models
|-- services/        use cases, SOP generation, and robot export
|-- tests/           isolated unit and integration tests
|-- websocket/       connection manager and live telemetry endpoint
|-- main.py          application factory and ASGI entry point
|-- Dockerfile       non-root production image
`-- requirements.txt runtime dependencies
```

Dependencies point inward: transports depend on service ports, services depend on
repositories and schemas, and repositories own SQLAlchemy-specific persistence.

## Local Setup

Run commands from the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

The service listens on `http://127.0.0.1:8000`. Interactive OpenAPI documentation
is available at `http://127.0.0.1:8000/docs`, ReDoc at `/redoc`, and the generated
OpenAPI document at `/openapi.json`.

## Configuration

Configuration uses `SMARTWEAR_*` environment variables. See `.env.example` for a
complete example.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SMARTWEAR_ENVIRONMENT` | `development` | `development`, `test`, or `production` |
| `SMARTWEAR_API_PREFIX` | `/api/v1` | REST API prefix |
| `SMARTWEAR_DATABASE_URL` | SQLite under `backend/data` | SQLAlchemy database URL |
| `SMARTWEAR_STATIC_DIR` | `backend/static` | Root mounted at `/static` |
| `SMARTWEAR_PDF_DIR` | `backend/static/pdf` | Generated SOP PDF directory |
| `SMARTWEAR_KEYFRAME_DIR` | `backend/static/images` | Uploaded keyframe directory |
| `SMARTWEAR_DATASET_DIR` | `backend/static/dataset` | JSON and ROS2 export directory |
| `SMARTWEAR_CORS_ORIGINS` | local frontend origins | JSON array or comma-separated origins |
| `SMARTWEAR_API_KEY` | unset | Required in production |
| `SMARTWEAR_LOG_LEVEL` | `INFO` | Backend log level |
| `SMARTWEAR_MAX_PAGE_SIZE` | `100` | Maximum REST collection page size |
| `SMARTWEAR_MAX_KEYFRAME_BYTES` | `10485760` | Maximum keyframe upload size |

When an API key is configured, REST clients send `X-API-Key`; WebSocket clients use
the `api_key` query parameter.

## REST API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/sessions/ingest` | Validate, upsert, and generate artifacts |
| `GET` | `/api/v1/sessions/` | List sessions with offset pagination |
| `GET` | `/api/v1/sessions/dashboard/summary` | Aggregate operational metrics |
| `GET` | `/api/v1/sessions/{session_id}` | Return a complete session |
| `PUT` | `/api/v1/sessions/{session_id}/analysis-result` | Attach the complete AI comparison JSON to an existing DEMO session |
| `GET` | `/api/v1/sessions/{session_id}/analysis-result` | Return all DTW/Muda/sensor details and image URLs |
| `PUT` | `/api/v1/sessions/{session_id}/analysis-images/expert/{filename}` | Upload an expert image referenced by the comparison |
| `GET` | `/api/v1/sessions/{session_id}/analysis-images/expert/{filename}` | View an uploaded expert image |
| `GET` | `/api/v1/sessions/{session_id}/download-sop` | Download SOP as `pdf` or `html` |
| `GET` | `/api/v1/sessions/{session_id}/export-rosbag` | Download `json`, `db3`, or `rosbag` |
| `PUT` | `/api/v1/sessions/{session_id}/keyframes/{filename}` | Upload a declared image |
| `GET` | `/api/v1/sessions/{session_id}/keyframes/{filename}` | Download an image |
| `GET` | `/api/v1/dashboard/history` | Paginated dashboard history |
| `GET` | `/api/v1/dashboard/sessions/{session_id}` | Dashboard session detail |
| `GET` | `/api/v1/dashboard/statistics` | Aggregate dashboard statistics |
| `GET` | `/api/v1/dashboard/kpis` | Current dashboard KPI snapshot |
| `GET` | `/api/v1/dashboard/charts` | Chronological dashboard chart data |
| `GET` | `/health` | Process liveness |
| `GET` | `/ready` | Application readiness |

Ingest is idempotent by `session_id`: the first successful request returns `201`,
and later replacements return `200`.

The existing ingest contract is unchanged. After ingest, the AI bridge attaches
its complete `analysis_result.json` separately. `GET /sessions/{session_id}` adds
optional `analysis_result` and `analysis_image_urls` fields; older sessions return
`null` for them until the detail is uploaded. The original AI field names and
per-hand alignments are preserved, including `worker_extra_ms`, image paths,
reference selection, sensor comparison, and all Muda review candidates. URLs
resolve worker images through the existing keyframe route and expert images through
the new expert-image route. This detailed comparison is stored alongside backend
data and does not change the existing score, SOP, or robot export contract.

The request body follows the immutable interface contract:

```json
{
  "session_id": "CYCLE_DENSO_001",
  "worker_type": "EXPERT",
  "key_frames": ["frame_assemble_01.jpg"],
  "action_phases": [
    {"phase": "REACH", "start_time": 0.0, "end_time": 1.8},
    {
      "phase": "ASSEMBLY",
      "start_time": 1.8,
      "end_time": 4.2,
      "peak_force_N": 5.4
    }
  ],
  "dtw_metrics": {
    "similarity_score": 91.5,
    "muda_detected_seconds": 0.8
  },
  "robot_trajectory_points": [
    {"t": 0.1, "pos": [0.12, 0.45, 0.88], "force": 0.0},
    {"t": 2.0, "pos": [0.15, 0.48, 0.70], "force": 5.4}
  ]
}
```

Unknown fields, unsafe identifiers, non-finite values, overlapping phases, and
unordered trajectory points are rejected with `422`.

## Live Telemetry

Connect to `ws://127.0.0.1:8000/ws/live-stream`. Valid `TelemetryUpdate` messages
received from one client are broadcast to all connected clients. Invalid messages
receive a `VALIDATION_ERROR` event.

For backend-only development without an AI producer, connect to:

```text
ws://127.0.0.1:8000/ws/live-stream?simulate=true
```

The simulator is isolated in `backend/mock/` and does not change AI-owned code.

## Tests

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

Tests use temporary SQLite databases and artifact directories under `backend/`, then
remove them. They cover schema validation, idempotent persistence, normalized rows,
dashboard queries, error recovery, PDF/ROS2 artifacts, images, authentication, CORS,
readiness, and WebSocket behavior.

## Docker

Build from the repository root using `backend/` as the context:

```powershell
docker build -t smartwear-backend backend
docker run --rm -p 8000:8000 -e SMARTWEAR_API_KEY=change-me smartwear-backend
```

The container runs as a non-root user. Production startup fails fast when
`SMARTWEAR_API_KEY` is missing.

## Generated Data

- `backend/data/smartwear.db`: normalized SQLite database
- `backend/data/keyframes/{session_id}`: validated keyframe images
- `backend/static/pdf/sop_{session_id}.pdf`: printable SOP report
- `backend/static/pdf/sop_{session_id}.html`: standalone HTML SOP report
- `backend/static/images/{session_id}/`: validated keyframe images
- `backend/static/dataset/robot_dataset_{session_id}.json`: portable robot dataset
- `backend/static/dataset/rosbag_{session_id}.db3`: ROS2 SQLite bag
- `backend/static/dataset/rosbag_{session_id}.zip`: bag DB3 plus `metadata.yaml`

These runtime directories are ignored by Git and remain inside the backend boundary.

