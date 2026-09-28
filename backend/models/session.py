"""Normalized SQLAlchemy models for SmartWear analysis sessions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class AnalysisSession(Base):
    """Aggregate root for one immutable-interface analysis payload."""

    __tablename__ = "analysis_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    worker_type: Mapped[str] = mapped_column(String(16), nullable=False)
    export_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    export_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now, nullable=False)

    action_phases: Mapped[list[ActionPhase]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ActionPhase.sequence_index",
    )
    dtw_metrics: Mapped[DtwMetrics] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    trajectory_points: Mapped[list[RobotTrajectoryPoint]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="RobotTrajectoryPoint.sequence_index",
    )
    key_frames: Mapped[list[KeyFrame]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="KeyFrame.sequence_index",
    )

    __table_args__ = (
        CheckConstraint("worker_type IN ('EXPERT', 'TRAINEE')", name="ck_session_worker_type"),
        CheckConstraint(
            "export_status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name="ck_session_export_status",
        ),
    )


class ActionPhase(Base):
    """Timed action segment within an analysis session."""

    __tablename__ = "action_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    peak_force_n: Mapped[float | None] = mapped_column(Float, nullable=True)

    session: Mapped[AnalysisSession] = relationship(back_populates="action_phases")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence_index", name="uq_phase_session_sequence"),
        CheckConstraint("sequence_index >= 0", name="ck_phase_sequence_nonnegative"),
        CheckConstraint("start_time >= 0", name="ck_phase_start_nonnegative"),
        CheckConstraint("end_time >= start_time", name="ck_phase_time_order"),
        CheckConstraint("peak_force_n IS NULL OR peak_force_n >= 0", name="ck_phase_force_nonnegative"),
    )


class DtwMetrics(Base):
    """Dynamic time-warping comparison metrics for a session."""

    __tablename__ = "dtw_metrics"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    muda_detected_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    session: Mapped[AnalysisSession] = relationship(back_populates="dtw_metrics")

    __table_args__ = (
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 100",
            name="ck_dtw_similarity_range",
        ),
        CheckConstraint("muda_detected_seconds >= 0", name="ck_dtw_muda_nonnegative"),
    )


class RobotTrajectoryPoint(Base):
    """Time-ordered robot pose and force sample."""

    __tablename__ = "robot_trajectory_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    position_z: Mapped[float] = mapped_column(Float, nullable=False)
    force: Mapped[float] = mapped_column(Float, nullable=False)

    session: Mapped[AnalysisSession] = relationship(back_populates="trajectory_points")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence_index", name="uq_trajectory_session_sequence"),
        CheckConstraint("sequence_index >= 0", name="ck_trajectory_sequence_nonnegative"),
        CheckConstraint("timestamp >= 0", name="ck_trajectory_timestamp_nonnegative"),
        CheckConstraint("force >= 0", name="ck_trajectory_force_nonnegative"),
        Index("ix_trajectory_session_timestamp", "session_id", "timestamp"),
    )


class KeyFrame(Base):
    """Declared keyframe and its optional backend-owned image path."""

    __tablename__ = "key_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str | None] = mapped_column(String(1_024), nullable=True)

    session: Mapped[AnalysisSession] = relationship(back_populates="key_frames")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence_index", name="uq_keyframe_session_sequence"),
        UniqueConstraint("session_id", "filename", name="uq_keyframe_session_filename"),
        CheckConstraint("sequence_index >= 0", name="ck_keyframe_sequence_nonnegative"),
    )

