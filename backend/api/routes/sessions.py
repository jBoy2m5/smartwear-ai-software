"""REST endpoints for SmartWear sessions and generated artifacts."""

import mimetypes
from pathlib import Path as FilePath
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from fastapi.responses import FileResponse

from backend.api.auth import require_api_key
from backend.api.dependencies import SessionServicePort, get_session_service
from backend.core.config import get_settings
from backend.schemas import (
    DashboardSummary,
    IngestResponse,
    KeyFrameResponse,
    PaginatedSessions,
    SessionDetail,
    SessionInput,
)


SessionId = Annotated[
    str,
    Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"),
]
Service = Annotated[SessionServicePort, Depends(get_session_service)]
router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_session(
    payload: SessionInput,
    response: Response,
    service: Service,
) -> IngestResponse:
    """Validate, persist, and process one complete analysis session."""
    result = service.ingest(payload)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/", response_model=PaginatedSessions)
def list_sessions(
    service: Service,
    limit: int = Query(default=25, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
) -> PaginatedSessions:
    """List persisted sessions in descending update order."""
    return service.list_sessions(limit=limit, offset=offset)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(service: Service) -> DashboardSummary:
    """Return aggregate dashboard metrics."""
    return service.dashboard_summary()


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: SessionId, service: Service) -> SessionDetail:
    """Return one complete persisted session."""
    return service.get_session(session_id)


@router.get("/{session_id}/download-sop", response_class=FileResponse)
def download_sop(session_id: SessionId, service: Service) -> FileResponse:
    """Download the generated SOP report."""
    path = service.get_sop_path(session_id)
    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.get("/{session_id}/export-rosbag", response_class=FileResponse)
def download_robot_export(
    session_id: SessionId,
    service: Service,
    export_format: Literal["json", "db3", "rosbag"] = Query(default="db3", alias="format"),
) -> FileResponse:
    """Download a generated robot dataset artifact."""
    path = service.get_robot_export_path(session_id, export_format)
    media_types = {
        "json": "application/json",
        "db3": "application/vnd.sqlite3",
        "rosbag": "application/zip",
    }
    return FileResponse(path, media_type=media_types[export_format], filename=path.name)


@router.put("/{session_id}/keyframes/{filename}", response_model=KeyFrameResponse)
async def upload_keyframe(
    session_id: SessionId,
    filename: str,
    request: Request,
    service: Service,
) -> KeyFrameResponse:
    """Store a declared keyframe image owned by the backend."""
    content = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
    return service.store_keyframe(session_id, filename, content_type, content)


@router.get("/{session_id}/keyframes/{filename}", response_class=FileResponse)
def download_keyframe(
    session_id: SessionId,
    filename: str,
    service: Service,
) -> FileResponse:
    """Download a previously stored keyframe image."""
    path: FilePath = service.get_keyframe_path(session_id, filename)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)

