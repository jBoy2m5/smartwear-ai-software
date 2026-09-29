"""REST views tailored for the engineering dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.api.auth import require_api_key
from backend.api.dependencies import SessionServicePort, enforce_page_limit, get_session_service
from backend.schemas import DashboardCharts, DashboardSummary, PaginatedSessions, SessionDetail


Service = Annotated[SessionServicePort, Depends(get_session_service)]
SessionId = Annotated[
    str,
    Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"),
]
router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/history", response_model=PaginatedSessions)
def history(
    request: Request,
    service: Service,
    limit: int = Query(default=25, ge=1, le=1_000),
    offset: int = Query(default=0, ge=0),
) -> PaginatedSessions:
    """Return paginated analysis history for dashboard tables."""
    enforce_page_limit(request, limit)
    return service.list_sessions(limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(session_id: SessionId, service: Service) -> SessionDetail:
    """Return complete detail for a selected dashboard session."""
    return service.get_session(session_id)


@router.get("/statistics", response_model=DashboardSummary)
def statistics(service: Service) -> DashboardSummary:
    """Return aggregate session statistics."""
    return service.dashboard_summary()


@router.get("/kpis", response_model=DashboardSummary)
def kpis(service: Service) -> DashboardSummary:
    """Return the current engineering KPI snapshot."""
    return service.dashboard_summary()


@router.get("/charts", response_model=DashboardCharts)
def charts(
    request: Request,
    service: Service,
    limit: int = Query(default=50, ge=1, le=1_000),
) -> DashboardCharts:
    """Return chronological similarity and muda chart series."""
    enforce_page_limit(request, limit)
    return service.dashboard_charts(limit=limit)

