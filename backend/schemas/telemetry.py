"""Schemas for validated live telemetry messages."""

from pydantic import Field

from backend.schemas.session import StrictSchema


class TelemetryUpdate(StrictSchema):
    """One real-time wearable telemetry event."""

    event: str = Field(default="TELEMETRY_UPDATE", pattern=r"^TELEMETRY_UPDATE$")
    timestamp: float = Field(ge=0, allow_inf_nan=False)
    current_phase: str = Field(min_length=1, max_length=64)
    realtime_force_N: float = Field(ge=0, allow_inf_nan=False)
    pinch_distance_mm: float = Field(ge=0, allow_inf_nan=False)
    muda_alert: bool
    message: str = Field(min_length=1, max_length=500)

