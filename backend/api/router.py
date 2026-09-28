"""Top-level API router composition."""

from fastapi import APIRouter

from backend.api.routes.sessions import router as sessions_router


api_router = APIRouter()
api_router.include_router(sessions_router)

