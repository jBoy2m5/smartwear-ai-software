"""Top-level API router composition."""

from fastapi import APIRouter

from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.sessions import router as sessions_router
from backend.api.routes.capture import router as capture_router
from backend.api.routes.knowledge import router as knowledge_router


api_router = APIRouter()
api_router.include_router(sessions_router)
api_router.include_router(dashboard_router)
api_router.include_router(capture_router)
api_router.include_router(knowledge_router)

