"""Pydantic schemas for the immutable SmartWear interface contract."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictSchema(BaseModel):
    """Base schema that rejects undeclared interface fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WorkerType(str, Enum):
    """Worker classification supplied by the AI module."""

    EXPERT = "EXPERT"
    TRAINEE = "TRAINEE"


class ExportStatus(str, Enum):
    """Artifact generation state for a persisted session."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ActionPhaseInput(StrictSchema):
    """One timed phase from the interface contract."""

    phase: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    start_time: float = Field(ge=0, allow_inf_nan=False)
    end_time: float = Field(ge=0, allow_inf_nan=False)
    peak_force_N: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_time_order(self) -> "ActionPhaseInput":
        """Ensure a phase cannot end before it starts."""
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")
        return self


class DtwMetricsInput(StrictSchema):
    """Dynamic time-warping metrics from the interface contract."""

    similarity_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    muda_detected_seconds: float = Field(ge=0, allow_inf_nan=False)


class RobotTrajectoryPointInput(StrictSchema):
    """One timestamped robot pose and force sample."""

    t: float = Field(ge=0, allow_inf_nan=False)
    pos: tuple[float, float, float]
    force: float = Field(ge=0, allow_inf_nan=False)

    @field_validator("pos")
    @classmethod
    def validate_finite_position(
        cls,
        value: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Reject NaN and infinite Cartesian coordinates."""
        if any(coordinate != coordinate or abs(coordinate) == float("inf") for coordinate in value):
            raise ValueError("pos coordinates must be finite")
        return value


class SessionInput(StrictSchema):
    """Complete AI-to-backend analysis payload."""

    session_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    worker_type: WorkerType
    key_frames: list[str]
    action_phases: list[ActionPhaseInput]
    dtw_metrics: DtwMetricsInput
    robot_trajectory_points: list[RobotTrajectoryPointInput]

    @field_validator("key_frames")
    @classmethod
    def validate_keyframes(cls, value: list[str]) -> list[str]:
        """Require unique, basename-only keyframe references."""
        if len(value) != len(set(value)):
            raise ValueError("key_frames must not contain duplicates")
        for filename in value:
            if not filename or filename != PurePath(filename).name or "\\" in filename:
                raise ValueError("key_frames must contain safe filenames only")
        return value

    @model_validator(mode="after")
    def validate_timelines(self) -> "SessionInput":
        """Require chronological phases and trajectory samples."""
        for previous, current in zip(self.action_phases, self.action_phases[1:]):
            if current.start_time < previous.end_time:
                raise ValueError("action_phases must be chronological and non-overlapping")
        trajectory_times = [point.t for point in self.robot_trajectory_points]
        if any(current <= previous for previous, current in zip(trajectory_times, trajectory_times[1:])):
            raise ValueError("robot_trajectory_points must have strictly increasing t values")
        return self


class IngestResponse(StrictSchema):
    """Result returned after a session is persisted and processed."""

    session_id: str
    created: bool
    export_status: ExportStatus
    message: str
    sop_download_url: str | None = None
    robot_json_url: str | None = None
    robot_export_url: str | None = None


class SessionSummary(StrictSchema):
    """Compact session representation used by list endpoints."""

    session_id: str
    worker_type: WorkerType
    similarity_score: float
    muda_detected_seconds: float
    export_status: ExportStatus
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionInput):
    """Persisted session with backend metadata and artifact links."""

    # Optional companion document preserves the original AI comparison contract.
    # Older sessions and clients continue to use the existing summary fields.
    analysis_result: dict | None = None
    analysis_image_urls: dict[str, dict[str, str]] | None = None
    recording_url: str | None = None
    source_data_url: str | None = None
    export_status: ExportStatus
    export_error: str | None = None
    created_at: datetime
    updated_at: datetime
    sop_download_url: str | None = None
    robot_json_url: str | None = None
    robot_export_url: str | None = None


class PaginatedSessions(StrictSchema):
    """Offset-paginated session collection."""

    items: list[SessionSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class DashboardSummary(StrictSchema):
    """Aggregate metrics for the operations dashboard."""

    total_sessions: int = Field(ge=0)
    expert_sessions: int = Field(ge=0)
    trainee_sessions: int = Field(ge=0)
    average_similarity_score: float = Field(ge=0, le=100)
    total_muda_detected_seconds: float = Field(ge=0)


class DashboardChartPoint(StrictSchema):
    """One session point used by dashboard charts."""

    session_id: str
    similarity_score: float = Field(ge=0, le=100)
    muda_detected_seconds: float = Field(ge=0)
    updated_at: datetime


class DashboardCharts(StrictSchema):
    """Time-ordered chart series derived from persisted sessions."""

    points: list[DashboardChartPoint]


class DashboardUpdate(StrictSchema):
    """Realtime dashboard event derived from an ingested analysis result."""

    event: str = Field(default="DASHBOARD_UPDATE", pattern=r"^DASHBOARD_UPDATE$")
    session_id: str
    current_action: str
    similarity_score: float = Field(ge=0, le=100)
    force: float = Field(ge=0, allow_inf_nan=False)
    warning: str | None = None


class KeyFrameResponse(StrictSchema):
    """Metadata returned after a keyframe upload."""

    session_id: str
    filename: str
    size: int = Field(ge=0)
    content_type: str

