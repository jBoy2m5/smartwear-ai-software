# AI → backend DEMO bridge

This bridge reads
a **completed** AI session, writes `backend_payload_demo.json` plus
`backend_payload_demo.meta.json` beside the session, sends the payload to backend
`POST /api/v1/sessions/ingest`, then uploads each declared PNG keyframe. After all
uploads succeed it writes `backend_publish_demo.receipt.json`. It never overwrites
the original AI outputs. If the backend is unavailable, the camera session remains
on disk; retry publication with the bridge command below.

For worker sessions, the bridge also uploads the **complete** `analysis_result.json`
and the expert sample images referenced by it. The backend session URL now includes
`analysis_result` (all per-hand DTW pairs, `worker_extra_ms`, Muda review, sensor
comparison, and reference selection) and `analysis_image_urls` with links for both
worker and expert images. The same detail is at
`/api/v1/sessions/<DEMO_ID>/analysis-result`. A separate
`backend_analysis_demo.receipt.json` confirms that the detailed analysis and all
expert images were sent. Publishing an older completed session again fills in this
new detail without re-recording or rewriting its original AI files.

If the AI session has `camera.avi` and a matching `camera.video.json`, the bridge
also uploads that original video and writes `backend_recording_demo.receipt.json`.
The backend detail exposes `recording_url` for the dashboard's AVI download. Older
sessions can be republished to attach their video without another camera recording.
It also packages the session's original camera, sensor, multimodal, action, keyframe,
comparison, and DEMO payload files in a separate ZIP (the AVI stays a separate
download). The backend exposes `source_data_url` and the bridge writes
`backend_source_data_demo.receipt.json` after the upload.

From the repository root, start backend in a separate terminal using its installed
environment (`python -m uvicorn backend.main:app --reload`), then run **one camera
command** in the AI terminal:

```powershell
python -B ai/integration/run_connected.py
```

Press **Q** to finish. The existing pipeline automatically chooses a practice
reference and compares the recording; the new wrapper then publishes it. This
requires the same camera/MediaPipe dependencies as `ai/camera_test.py` and a running
backend. To publish an already completed, internally consistent session:

```powershell
python -B ai/integration/backend_bridge.py "C:\Task\smartwear-ai\ai\generated_data\sessions\<session-name>" --publish
```

Without `--publish`, the bridge only constructs the two local DEMO JSON files.
Use `--backend-url` if backend runs elsewhere; configure the optional
`SMARTWEAR_API_KEY` environment variable if backend requires `X-API-Key`.

New camera captures track only the anatomical right hand. The raw camera frames
contain no left-hand landmarks or left-hand action; a `left: NO_HAND` placeholder
remains in the internal two-hand schema for compatibility. The dashboard preview
serves a clean JPEG and matching right-hand observation for the frontend to draw.
The backend contract has a single nonoverlapping `action_phases` list. New sessions
therefore contain `RIGHT_...` phases. The bridge can still read older two-hand
sessions and combine their concurrent labels, such as `LEFT_GRAB.RIGHT_OPEN`.
`key_frames` contains existing PNG basenames and those PNGs are uploaded after
ingest. Sessions and output files remain in `ai/generated_data/sessions/<name>/`;
backend persists its own database, SOP, robot export, and images under `backend/`.

**DEMO values, not measurements:** all published session IDs start with `DEMO_`.
The source sensor signal `force_emg_raw` is unitless. To populate the backend's
required `peak_force_N` and trajectory `force` fields for a software demo only, the
bridge computes `clamp((force_emg_raw - 80) / 720, 0, 1) × 20`. The result is a
display number in a field named N, **not physical Newton**. The similarity display
score is `100 / (1 + weighted mean per-hand normalized DTW cost)`; no comparable
worker actions gives 0, and an expert session gets demo baseline 100. This score
is not a calibrated work-quality percentage. `muda_detected_seconds` sums distinct
candidate durations or positive extra time. Missing actions add 0 because no worker
duration was observed; `shorter_visible_action` also adds 0 because it did not
increase elapsed time. These are **unconfirmed suspicions**, not verified wasted seconds.
Trajectory points sample the visible **right wrist** screen coordinates at intervals of at least
100 ms and map them onto a small flat demo plane. They are **not calibrated robot
coordinates** and must not control a robot. The detailed rules and input hashes
are recorded in `backend_payload_demo.meta.json`.

The bridge rejects missing or inconsistent source hashes instead of publishing
mixed recordings. A failed POST/upload can be retried; backend ingest is
idempotent for the same `session_id` and payload. The local receipt only appears
after all images upload successfully.
