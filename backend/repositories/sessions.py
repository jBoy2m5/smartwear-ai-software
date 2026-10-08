"""SQLAlchemy repository for the session aggregate."""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from backend.models import ActionPhase, AnalysisSession, DtwMetrics, KeyFrame, RobotTrajectoryPoint
from backend.models.session import utc_now
from backend.schemas import SessionInput


class SessionRepository:
    """Persist and query session aggregates within a caller-owned transaction."""

    _aggregate_options = (
        selectinload(AnalysisSession.action_phases),
        selectinload(AnalysisSession.dtw_metrics),
        selectinload(AnalysisSession.trajectory_points),
        selectinload(AnalysisSession.key_frames),
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, session_id: str) -> AnalysisSession | None:
        """Load one complete aggregate by its public identifier."""
        statement = (
            select(AnalysisSession)
            .where(AnalysisSession.session_id == session_id)
            .options(*self._aggregate_options)
        )
        return self.session.scalar(statement)

    def delete(self, session_id: str) -> bool:
        entity = self.get(session_id)
        if entity is None:
            return False
        self.session.delete(entity)
        self.session.flush()
        return True

    def upsert(self, payload: SessionInput) -> tuple[AnalysisSession, bool]:
        """Create or replace a complete aggregate atomically."""
        entity = self.get(payload.session_id)
        created = entity is None
        if entity is None:
            entity = AnalysisSession(session_id=payload.session_id, worker_type=payload.worker_type.value)
            self.session.add(entity)
        else:
            entity.worker_type = payload.worker_type.value
            entity.action_phases.clear()
            entity.trajectory_points.clear()
            entity.key_frames.clear()
            entity.dtw_metrics = None  # type: ignore[assignment]
            self.session.flush()

        entity.export_status = "PENDING"
        entity.export_error = None
        entity.updated_at = utc_now()
        entity.action_phases.extend(
            ActionPhase(
                sequence_index=index,
                phase=phase.phase,
                start_time=phase.start_time,
                end_time=phase.end_time,
                peak_force_n=phase.peak_force_N,
            )
            for index, phase in enumerate(payload.action_phases)
        )
        entity.dtw_metrics = DtwMetrics(
            similarity_score=payload.dtw_metrics.similarity_score,
            muda_detected_seconds=payload.dtw_metrics.muda_detected_seconds,
        )
        entity.trajectory_points.extend(
            RobotTrajectoryPoint(
                sequence_index=index,
                timestamp=point.t,
                position_x=point.pos[0],
                position_y=point.pos[1],
                position_z=point.pos[2],
                force=point.force,
            )
            for index, point in enumerate(payload.robot_trajectory_points)
        )
        entity.key_frames.extend(
            KeyFrame(sequence_index=index, filename=filename)
            for index, filename in enumerate(payload.key_frames)
        )
        self.session.flush()
        return entity, created

    def list(self, *, limit: int, offset: int) -> tuple[list[AnalysisSession], int]:
        """Return a page and total row count."""
        total = self.session.scalar(select(func.count()).select_from(AnalysisSession)) or 0
        statement = (
            select(AnalysisSession)
            .options(selectinload(AnalysisSession.dtw_metrics))
            .order_by(AnalysisSession.updated_at.desc(), AnalysisSession.session_id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement)), total

    def dashboard(self) -> dict[str, int | float]:
        """Compute dashboard aggregates in one database query."""
        statement = select(
            func.count(AnalysisSession.session_id),
            func.sum(case((AnalysisSession.worker_type == "EXPERT", 1), else_=0)),
            func.sum(case((AnalysisSession.worker_type == "TRAINEE", 1), else_=0)),
            func.coalesce(func.avg(DtwMetrics.similarity_score), 0.0),
            func.coalesce(func.sum(DtwMetrics.muda_detected_seconds), 0.0),
        ).outerjoin(DtwMetrics, DtwMetrics.session_id == AnalysisSession.session_id)
        total, experts, trainees, average_similarity, total_muda = self.session.execute(statement).one()
        return {
            "total_sessions": int(total or 0),
            "expert_sessions": int(experts or 0),
            "trainee_sessions": int(trainees or 0),
            "average_similarity_score": float(average_similarity or 0.0),
            "total_muda_detected_seconds": float(total_muda or 0.0),
        }

    def update_keyframe_path(self, session_id: str, filename: str, stored_path: str) -> bool:
        """Attach a backend-owned image path to a declared keyframe."""
        statement = select(KeyFrame).where(
            KeyFrame.session_id == session_id,
            KeyFrame.filename == filename,
        )
        keyframe = self.session.scalar(statement)
        if keyframe is None:
            return False
        keyframe.stored_path = stored_path
        self.session.flush()
        return True

    def update_export_status(
        self,
        session_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update artifact generation state for a persisted session."""
        entity = self.session.get(AnalysisSession, session_id)
        if entity is None:
            return
        entity.export_status = status
        entity.export_error = error
        entity.updated_at = utc_now()
        self.session.flush()

