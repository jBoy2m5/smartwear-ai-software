"""Dashboard controls for the camera attached to the AI/backend workstation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response

from backend.api.auth import require_api_key

router = APIRouter(prefix="/capture", tags=["Capture"],
                   dependencies=[Depends(require_api_key)])
JobId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]


@router.post("/", status_code=status.HTTP_201_CREATED)
def start_capture(request: Request) -> dict:
    try:
        return request.app.state.capture_manager.start()
    except RuntimeError as exc:
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


@router.get("/{job_id}/frame", response_class=Response)
def preview_frame(job_id: JobId, request: Request) -> Response:
    try:
        directory = request.app.state.capture_manager.directory(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for path in reversed(sorted(directory.glob("preview_*.jpg"))):
        try:
            image = path.read_bytes()
        except FileNotFoundError:
            # The recorder may have removed an older frame while we listed it.
            continue
        return Response(image, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store, max-age=0"})
    raise HTTPException(status_code=404, detail="Camera chưa có hình")
