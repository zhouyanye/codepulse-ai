from fastapi import APIRouter, HTTPException
from models.request_models import HealthCheckResponse
import datetime

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    健康检查端点
    """
    try:
        return HealthCheckResponse(
            status="healthy",
            timestamp=datetime.datetime.now().isoformat(),
            version="1.0.0"
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service unhealthy")