"""API routes. Every route is mounted under /api (see app/main.py)."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    llm_ready = bool(settings.azure_openai_endpoint and settings.azure_openai_deployment)
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="configured" if settings.database_url else "not configured",
        llm="configured" if llm_ready else "not configured",
    )
