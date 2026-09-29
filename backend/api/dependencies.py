"""Application service ports and FastAPI dependency providers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from fastapi import HTTPException, Request, status

from backend.schemas import (
    DashboardCharts,
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

    def dashboard_charts(self, *, limit: int) -> DashboardCharts: ...

    def get_sop_path(
        self,
        session_id: str,
        output_format: Literal["pdf", "html"],
    ) -> Path: ...

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


def enforce_page_limit(request: Request, limit: int) -> int:
    """Validate pagination against the settings of the active app instance."""
    settings: Settings = request.app.state.settings
    if limit > settings.max_page_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"limit must be less than or equal to {settings.max_page_size}",
        )
    return limit

