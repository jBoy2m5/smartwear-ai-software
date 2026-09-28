"""ASGI application entry point."""

from contextlib import asynccontextmanager

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
from backend.websocket import router as websocket_router
from backend.websocket.manager import ConnectionManager


def create_app(settings: Settings | None = None) -> FastAPI:
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
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
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
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})

    @application.exception_handler(BackendError)
    async def handle_backend_error(_: Request, exc: BackendError) -> JSONResponse:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, ArtifactNotFoundError)
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

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

    return application


app = create_app()

