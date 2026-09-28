"""ASGI application entry point."""

from fastapi import FastAPI

from backend import __version__


def create_app() -> FastAPI:
    """Create the SmartWear FastAPI application."""
    application = FastAPI(
        title="SmartWear AI Backend",
        version=__version__,
    )

    @application.get("/health", tags=["System"])
    def health() -> dict[str, str]:
        """Report that the HTTP process is responsive."""
        return {"status": "ok"}

    return application


app = create_app()

