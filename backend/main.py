"""ASGI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.api.router import api_router
from backend.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the SmartWear FastAPI application."""
    runtime_settings = settings or get_settings()
    application = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
    )
    application.state.settings = runtime_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    application.include_router(api_router, prefix=runtime_settings.api_prefix)

    @application.get("/health", tags=["System"])
    def health() -> dict[str, str]:
        """Report that the HTTP process is responsive."""
        return {"status": "ok"}

    return application


app = create_app()

