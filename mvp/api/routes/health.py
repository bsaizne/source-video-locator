"""routes.health — 健康检查。"""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1")
