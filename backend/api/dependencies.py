"""Application service ports and FastAPI dependency providers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from fastapi import HTTPException, Request, status

from backend.schemas import (
    DashboardSummary,
    IngestResponse,
    KeyFrameResponse,
    PaginatedSessions,
    SessionDetail,
    SessionInput,
)


class SessionServicePort(Protocol):
    """Operations exposed by the session application service."""

    def ingest(self, payload: SessionInput) -> IngestResponse: ...

    def list_sessions(self, *, limit: int, offset: int) -> PaginatedSessions: ...

    def get_session(self, session_id: str) -> SessionDetail: ...

    def dashboard_summary(self) -> DashboardSummary: ...

    def get_sop_path(self, session_id: str) -> Path: ...

    def get_robot_export_path(
        self,
        session_id: str,
        export_format: Literal["json", "db3", "rosbag"],
    ) -> Path: ...

    def store_keyframe(
        self,
        session_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> KeyFrameResponse: ...

    def get_keyframe_path(self, session_id: str, filename: str) -> Path: ...


def get_session_service(request: Request) -> SessionServicePort:
    """Resolve the configured session service from application state."""
    service = getattr(request.app.state, "session_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session service is not initialized",
        )
    return service

