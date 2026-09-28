"""ASGI application entry point."""

from fastapi import FastAPI

from backend import __version__
from backend.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the SmartWear FastAPI application."""
    runtime_settings = settings or get_settings()
    application = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
    )
    application.state.settings = runtime_settings

    @application.get("/health", tags=["System"])
    def health() -> dict[str, str]:
        """Report that the HTTP process is responsive."""
        return {"status": "ok"}

    return application


app = create_app()

