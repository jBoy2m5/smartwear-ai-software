"""Backend-owned telemetry simulator for development and tests."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from backend.schemas import TelemetryUpdate


class TelemetrySimulator:
    """Generate deterministic phase telemetry without depending on AI code."""

    phases = (
        ("REACH", 1.5, 1.2),
        ("GRAB", 1.0, 0.8),
        ("ASSEMBLY", 2.0, 1.8),
        ("RELEASE", 1.0, 0.8),
    )

    def __init__(self, interval_seconds: float = 0.05) -> None:
        self.interval_seconds = interval_seconds

    async def stream(self) -> AsyncIterator[TelemetryUpdate]:
        """Yield telemetry indefinitely until the WebSocket disconnects."""
        while True:
            for phase, duration, alert_threshold in self.phases:
                started = time.monotonic()
                while (elapsed := time.monotonic() - started) < duration:
                    force = self._force_for(phase, elapsed, duration)
                    alert = elapsed > alert_threshold
                    yield TelemetryUpdate(
                        timestamp=time.time(),
                        current_phase=phase,
                        realtime_force_N=round(force, 2),
                        pinch_distance_mm=12.4,
                        muda_alert=alert,
                        message=(
                            "Operation exceeded the standard phase duration"
                            if alert
                            else "Operation is within the expected range"
                        ),
                    )
                    await asyncio.sleep(self.interval_seconds)

    @staticmethod
    def _force_for(phase: str, elapsed: float, duration: float) -> float:
        if phase == "ASSEMBLY":
            return min(5.4, 1.0 + (4.4 * elapsed / duration))
        if phase == "GRAB":
            return 1.0
        return 0.0

