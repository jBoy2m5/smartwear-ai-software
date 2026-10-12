"""ASGI application entry point."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.api.router import api_router
from backend.core.config import Settings, get_settings
from backend.core.exceptions import (
    ArtifactNotFoundError,
    BackendError,
    InvalidKeyFrameError,
    ResourceNotFoundError,
    UndeclaredKeyFrameError,
)
from backend.core.logging import configure_logging
from backend.db import build_database
from backend.services import RobotDatasetExporter, SessionService, SopGenerator
from backend.services.capture import CaptureManager
from backend.services.knowledge import KnowledgeService
from backend.websocket import router as websocket_router
from backend.websocket.manager import ConnectionManager


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, serve_frontend: bool = True) -> FastAPI:
    """Create the SmartWear FastAPI application."""
    runtime_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(runtime_settings.log_level)
        for directory in (
            runtime_settings.static_dir,
            runtime_settings.pdf_dir,
            runtime_settings.keyframe_dir,
            runtime_settings.dataset_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        database = build_database(runtime_settings)
        database.create_schema()
        application.state.database = database
        application.state.session_service = SessionService(
            database,
            runtime_settings,
            sop_generator=SopGenerator(runtime_settings.pdf_dir),
            robot_exporter=RobotDatasetExporter(runtime_settings.dataset_dir),
        )
        application.state.capture_manager = CaptureManager(runtime_settings)
        application.state.knowledge_service = KnowledgeService(database, runtime_settings,
                                                               application.state.session_service)
        application.state.knowledge_service.seed()
        yield
        database.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.connection_manager = ConnectionManager()
    application.mount(
        "/static",
        StaticFiles(directory=runtime_settings.static_dir, check_dir=False),
        name="static",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    application.include_router(api_router, prefix=runtime_settings.api_prefix)
    application.include_router(websocket_router)

    @application.exception_handler(ResourceNotFoundError)
    async def handle_not_found(_: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @application.exception_handler(UndeclaredKeyFrameError)
    async def handle_undeclared_keyframe(_: Request, exc: UndeclaredKeyFrameError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @application.exception_handler(InvalidKeyFrameError)
    async def handle_invalid_keyframe(_: Request, exc: InvalidKeyFrameError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exc)},
        )

    @application.exception_handler(BackendError)
    async def handle_backend_error(_: Request, exc: BackendError) -> JSONResponse:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, ArtifactNotFoundError)
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Log unexpected failures and return a stable, non-sensitive response."""
        logger.error(
            "Unhandled backend error method=%s path=%s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    @application.get("/health", tags=["System"])
    def health() -> dict[str, str]:
        """Report that the HTTP process is responsive."""
        return {"status": "ok"}

    @application.get("/ready", tags=["System"])
    def ready(request: Request) -> dict[str, str]:
        """Report whether application services were initialized."""
        if not hasattr(request.app.state, "session_service"):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready"},
            )
        return {"status": "ready"}

    frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if serve_frontend and (frontend_dist / "index.html").is_file():
        application.mount("/", StaticFiles(directory=frontend_dist, html=True),
                          name="frontend")

    return application


app = create_app()

