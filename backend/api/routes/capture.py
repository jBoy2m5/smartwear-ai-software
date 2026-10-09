"""Dashboard controls and raw-frame previews from the AI workstation camera."""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from backend.schemas.knowledge import CaptureContext
from fastapi.responses import JSONResponse, Response

from backend.api.auth import require_api_key

router = APIRouter(prefix="/capture", tags=["Capture"],
                   dependencies=[Depends(require_api_key)])
JobId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]


@router.get("/devices")
def device_health(request: Request, refresh: bool = False) -> dict:
    return request.app.state.capture_manager.devices(refresh)


@router.post("/", status_code=status.HTTP_201_CREATED)
def start_capture(request: Request, capture_mode: Literal["hardware", "demo"] = "hardware",
                  context: CaptureContext | None = Body(default=None)) -> dict:
    try:
        if context is not None:
            if capture_mode == 'demo' and context.role != 'demo':
                raise ValueError('Expert/worker reference workflows require measured hardware')
            resolved = request.app.state.knowledge_service.capture_context(context)
            return request.app.state.capture_manager.start(capture_mode, context=resolved)
        return request.app.state.capture_manager.start(capture_mode)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{job_id}")
def capture_status(job_id: JobId, request: Request) -> dict:
    try:
        return request.app.state.capture_manager.status(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/stop")
def stop_capture(job_id: JobId, request: Request) -> dict:
    try:
        return request.app.state.capture_manager.stop(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{job_id}/preview")
def preview_observation(job_id: JobId, request: Request) -> JSONResponse:
    try:
        directory = request.app.state.capture_manager.directory(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for path in reversed(sorted(directory.glob("preview_*.json"))):
        if not path.with_suffix(".jpg").is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        import time
        published = document.get('published_epoch_ms')
        document['preview_age_ms'] = max(0, time.time_ns() // 1_000_000 - published) if published else None
        received = document.get('frame_received_epoch_ms')
        document['frame_age_ms'] = max(0, time.time_ns() // 1_000_000 - received) if received else document['preview_age_ms']
        return JSONResponse(document, headers={"Cache-Control": "no-store, max-age=0"})
    raise HTTPException(status_code=404, detail="Camera chưa có hình")


@router.get("/{job_id}/frame", response_class=Response)
def preview_frame(job_id: JobId, request: Request, index: int | None = None) -> Response:
    try:
        directory = request.app.state.capture_manager.directory(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if index is not None and (index < 0 or index > 99999999):
        raise HTTPException(status_code=422, detail="Invalid preview frame index")
    paths = ([directory / f"preview_{index:08d}.jpg"] if index is not None else
             reversed(sorted(directory.glob("preview_*.jpg"))))
    for path in paths:
        try:
            image = path.read_bytes()
        except FileNotFoundError:
            # The recorder may have removed an older frame while we listed it.
            continue
        return Response(image, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store, max-age=0"})
    raise HTTPException(status_code=404, detail="Camera chưa có hình")
