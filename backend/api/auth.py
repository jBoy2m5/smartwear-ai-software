"""HTTP authentication dependencies."""

from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from backend.core.config import Settings


def require_api_key(
    request: Request,
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Require the configured API key, while allowing keyless development."""
    settings: Settings = request.app.state.settings
    if settings.api_key and api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

