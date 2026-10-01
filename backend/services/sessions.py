"""Application service for SmartWear session use cases."""

from __future__ import annotations

import tempfile
from pathlib import Path, PurePath
from typing import Literal, Protocol

from PIL import Image, UnidentifiedImageError

from backend.core.config import Settings
from backend.core.exceptions import (
    ArtifactGenerationError,
    ArtifactNotFoundError,
    InvalidKeyFrameError,
    ResourceNotFoundError,
    UndeclaredKeyFrameError,
)
from backend.db.session import Database
from backend.models import AnalysisSession
from backend.repositories import SessionRepository
from backend.schemas import (
    DashboardCharts,
    DashboardChartPoint,
    DashboardSummary,
    ExportStatus,
    IngestResponse,
    KeyFrameResponse,
    PaginatedSessions,
    SessionDetail,
    SessionInput,
    SessionSummary,
)
from backend.services.analysis_detail import image_urls, load_analysis


class SopGeneratorPort(Protocol):
    """Port implemented by a backend-owned SOP generator."""

    def generate(self, payload: SessionInput) -> Path: ...


class RobotExporterPort(Protocol):
    """Port implemented by a backend-owned robot dataset exporter."""

    def export(self, payload: SessionInput) -> object: ...


class SessionService:
    """Coordinate persistence and backend-owned session resources."""

    _image_formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }

    def __init__(
        self,
        database: Database,
        settings: Settings,
        sop_generator: SopGeneratorPort | None = None,
        robot_exporter: RobotExporterPort | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.sop_generator = sop_generator
        self.robot_exporter = robot_exporter

    def ingest(self, payload: SessionInput) -> IngestResponse:
        """Upsert a validated session; artifact modules complete it later."""
        with self.database.transaction() as db_session:
            entity, created = SessionRepository(db_session).upsert(payload)
        try:
            if self.sop_generator is not None:
                self.sop_generator.generate(payload)
            if self.robot_exporter is not None:
                self.robot_exporter.export(payload)
        except Exception as exc:
            self._set_export_status(payload.session_id, ExportStatus.FAILED, str(exc))
            raise ArtifactGenerationError("Artifact generation failed") from exc

        all_artifacts_ready = self.sop_generator is not None and self.robot_exporter is not None
        export_status = ExportStatus.COMPLETED if all_artifacts_ready else ExportStatus.PENDING
        if all_artifacts_ready:
            self._set_export_status(payload.session_id, export_status)
        return IngestResponse(
            session_id=entity.session_id,
            created=created,
            export_status=export_status,
            message=(
                "Session stored and output artifacts generated"
                if all_artifacts_ready
                else "Session stored; artifact generation is pending"
            ),
            sop_download_url=(
                f"{self.settings.api_prefix}/sessions/{entity.session_id}/download-sop"
                if self.sop_generator is not None
                else None
            ),
            robot_json_url=(
                f"{self.settings.api_prefix}/sessions/{entity.session_id}/export-rosbag?format=json"
                if self.robot_exporter is not None
                else None
            ),
            robot_export_url=(
                f"{self.settings.api_prefix}/sessions/{entity.session_id}/export-rosbag?format=rosbag"
                if self.robot_exporter is not None
                else None
            ),
        )

    def list_sessions(self, *, limit: int, offset: int) -> PaginatedSessions:
        """Return a paginated session collection."""
        with self.database.transaction() as db_session:
            entities, total = SessionRepository(db_session).list(limit=limit, offset=offset)
            items = [self._to_summary(entity) for entity in entities]
        return PaginatedSessions(items=items, total=total, limit=limit, offset=offset)

    def get_session(self, session_id: str) -> SessionDetail:
        """Return one aggregate or raise a transport-independent not-found error."""
        with self.database.transaction() as db_session:
            entity = SessionRepository(db_session).get(session_id)
            if entity is None:
                raise ResourceNotFoundError(f"Session '{session_id}' was not found")
            return self._to_detail(entity)

    def dashboard_summary(self) -> DashboardSummary:
        """Return aggregate operational metrics."""
        with self.database.transaction() as db_session:
            return DashboardSummary.model_validate(SessionRepository(db_session).dashboard())

    def dashboard_charts(self, *, limit: int) -> DashboardCharts:
        """Return chronological session metrics for dashboard charts."""
        with self.database.transaction() as db_session:
            entities, _ = SessionRepository(db_session).list(limit=limit, offset=0)
            points = [
                DashboardChartPoint(
                    session_id=entity.session_id,
                    similarity_score=entity.dtw_metrics.similarity_score,
                    muda_detected_seconds=entity.dtw_metrics.muda_detected_seconds,
                    updated_at=entity.updated_at,
                )
                for entity in reversed(entities)
            ]
        return DashboardCharts(points=points)

    def get_sop_path(
        self,
        session_id: str,
        output_format: Literal["pdf", "html"] = "pdf",
    ) -> Path:
        """Resolve an existing generated SOP file."""
        self._require_session(session_id)
        candidate = self.settings.pdf_dir / f"sop_{session_id}.{output_format}"
        if candidate.is_file():
            return candidate
        raise ArtifactNotFoundError(f"SOP artifact for '{session_id}' was not found")

    def get_robot_export_path(
        self,
        session_id: str,
        export_format: Literal["json", "db3", "rosbag"],
    ) -> Path:
        """Resolve an existing generated robot export."""
        self._require_session(session_id)
        names = {
            "json": f"robot_dataset_{session_id}.json",
            "db3": f"rosbag_{session_id}.db3",
            "rosbag": f"rosbag_{session_id}.zip",
        }
        candidate = self.settings.dataset_dir / names[export_format]
        if not candidate.is_file():
            raise ArtifactNotFoundError(f"Robot artifact for '{session_id}' was not found")
        return candidate

    def store_keyframe(
        self,
        session_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> KeyFrameResponse:
        """Validate and atomically store a declared keyframe image."""
        safe_filename = self._safe_filename(filename)
        expected_format = self._image_formats.get(content_type)
        if expected_format is None:
            raise InvalidKeyFrameError("Only JPEG, PNG, and WebP keyframes are supported")
        if not content or len(content) > self.settings.max_keyframe_bytes:
            raise InvalidKeyFrameError("Keyframe is empty or exceeds the configured size limit")

        destination_dir = self.settings.keyframe_dir / session_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / safe_filename
        handle = tempfile.NamedTemporaryFile(dir=destination_dir, suffix=".upload", delete=False)
        temporary_path = Path(handle.name)
        try:
            with handle:
                handle.write(content)
            try:
                with Image.open(temporary_path) as image:
                    image.verify()
                    if image.format != expected_format:
                        raise InvalidKeyFrameError("Image content does not match Content-Type")
            except UnidentifiedImageError as exc:
                raise InvalidKeyFrameError("Invalid image data") from exc

            with self.database.transaction() as db_session:
                repository = SessionRepository(db_session)
                if repository.get(session_id) is None:
                    raise ResourceNotFoundError(f"Session '{session_id}' was not found")
                if not repository.update_keyframe_path(session_id, safe_filename, str(destination)):
                    raise UndeclaredKeyFrameError(
                        f"Keyframe '{safe_filename}' is not declared by session '{session_id}'"
                    )
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)

        if self.sop_generator is not None:
            detail = self.get_session(session_id)
            contract_fields = {
                "session_id",
                "worker_type",
                "key_frames",
                "action_phases",
                "dtw_metrics",
                "robot_trajectory_points",
            }
            self.sop_generator.generate(
                SessionInput.model_validate(detail.model_dump(include=contract_fields))
            )

        return KeyFrameResponse(
            session_id=session_id,
            filename=safe_filename,
            size=len(content),
            content_type=content_type,
        )

    def get_keyframe_path(self, session_id: str, filename: str) -> Path:
        """Resolve a stored keyframe path without permitting traversal."""
        safe_filename = self._safe_filename(filename)
        self._require_session(session_id)
        candidate = self.settings.keyframe_dir / session_id / safe_filename
        if not candidate.is_file():
            raise ArtifactNotFoundError(f"Keyframe '{safe_filename}' was not found")
        return candidate

    def _require_session(self, session_id: str) -> None:
        with self.database.transaction() as db_session:
            if SessionRepository(db_session).get(session_id) is None:
                raise ResourceNotFoundError(f"Session '{session_id}' was not found")

    def _set_export_status(
        self,
        session_id: str,
        status: ExportStatus,
        error: str | None = None,
    ) -> None:
        with self.database.transaction() as db_session:
            SessionRepository(db_session).update_export_status(session_id, status.value, error)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        if not filename or filename != PurePath(filename).name or "\\" in filename:
            raise InvalidKeyFrameError("Keyframe filename is unsafe")
        return filename

    def _to_summary(self, entity: AnalysisSession) -> SessionSummary:
        return SessionSummary(
            session_id=entity.session_id,
            worker_type=entity.worker_type,
            similarity_score=entity.dtw_metrics.similarity_score,
            muda_detected_seconds=entity.dtw_metrics.muda_detected_seconds,
            export_status=entity.export_status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _to_detail(self, entity: AnalysisSession) -> SessionDetail:
        artifact_ready = entity.export_status == ExportStatus.COMPLETED.value
        analysis = load_analysis(self.settings.keyframe_dir, entity.session_id)
        return SessionDetail(
            session_id=entity.session_id,
            worker_type=entity.worker_type,
            key_frames=[frame.filename for frame in entity.key_frames],
            action_phases=[
                {
                    "phase": phase.phase,
                    "start_time": phase.start_time,
                    "end_time": phase.end_time,
                    "peak_force_N": phase.peak_force_n,
                }
                for phase in entity.action_phases
            ],
            dtw_metrics={
                "similarity_score": entity.dtw_metrics.similarity_score,
                "muda_detected_seconds": entity.dtw_metrics.muda_detected_seconds,
            },
            robot_trajectory_points=[
                {
                    "t": point.timestamp,
                    "pos": [point.position_x, point.position_y, point.position_z],
                    "force": point.force,
                }
                for point in entity.trajectory_points
            ],
            export_status=entity.export_status,
            export_error=entity.export_error,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            sop_download_url=(
                f"{self.settings.api_prefix}/sessions/{entity.session_id}/download-sop"
                if artifact_ready
                else None
            ),
            robot_json_url=(
                f"{self.settings.api_prefix}/sessions/{entity.session_id}/export-rosbag?format=json"
                if artifact_ready
                else None
            ),
            robot_export_url=(
                f"{self.settings.api_prefix}/sessions/{entity.session_id}/export-rosbag?format=rosbag"
                if artifact_ready
                else None
            ),
            analysis_result=analysis,
            analysis_image_urls=(image_urls(analysis, entity.session_id, self.settings.api_prefix)
                                 if analysis is not None else None),
        )

