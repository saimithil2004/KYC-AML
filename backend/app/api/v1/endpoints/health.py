"""
Health & Observability Router — Phase 15
=========================================
Exposes service health status checks, system metrics, and Prometheus-compatible
metrics endpoint:
  - /health (Basic online check)
  - /health/live (Fast liveness check)
  - /health/ready (Database, Redis, and Celery checks)
  - /health/system (CPU, memory, disk details)
  - /health/full (Unified detailed dashboard status - Admin only)
  - /metrics (Prometheus-compatible raw metrics output)
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_admin
from app.models.models import User
from app.schemas.schemas import HealthResponse
from app.services.observability_service import ObservabilityService

from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
@router.get("/live", response_model=HealthResponse)
async def live_check() -> Dict[str, Any]:
    """Basic online / liveness check."""
    return {
        "status": "healthy",
        "latency_ms": 0.0,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/startup", response_model=HealthResponse)
async def startup_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Startup check checking base database capability."""
    start = time.perf_counter()
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency,
            "version": settings.VERSION,
            "timestamp": datetime.now(timezone.utc),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Startup check failed: database query failure: {e}",
        )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Database and Redis readiness check."""
    start = time.perf_counter()

    db_health = await ObservabilityService.get_database_health(db)
    redis_health = await ObservabilityService.get_redis_health()

    latency = round((time.perf_counter() - start) * 1000, 2)

    is_ready = db_health["status"] == "healthy" and redis_health["status"] == "healthy"

    details = {"database": db_health, "redis": redis_health}

    return {
        "status": "healthy" if is_ready else "unhealthy",
        "latency_ms": latency,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc),
        "details": details,
    }


@router.get("/system")
async def system_metrics(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get system resource metrics (requires active user)."""
    # Restrict system metrics viewing to compliance officers and admins
    if current_user.role not in ("admin", "compliance_officer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access system health metrics.",
        )

    metrics = await ObservabilityService.get_system_metrics()
    return {
        "status": "healthy",
        "latency_ms": 0.0,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc),
        "details": metrics,
    }


@router.get("/full")
async def full_observability(
    current_user: User = Depends(verify_admin), db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Unified system dashboard dump (requires Admin)."""
    data = await ObservabilityService.get_full_dashboard_metrics(db)
    return data


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(db: AsyncSession = Depends(get_db)) -> PlainTextResponse:
    """Prometheus-compatible plain text metrics reporter."""
    sys_m = await ObservabilityService.get_system_metrics()
    db_m = await ObservabilityService.get_database_health(db)
    redis_m = await ObservabilityService.get_redis_health()
    celery_m = await ObservabilityService.get_celery_health()
    api_m = await ObservabilityService.get_api_stats()

    # Generate standard Prometheus formatting lines
    lines = [
        "# HELP aml_cpu_percent System CPU usage percent",
        "# TYPE aml_cpu_percent gauge",
        f"aml_cpu_percent {sys_m.get('cpu_percent', 0.0)}",
        "# HELP aml_memory_percent System Memory usage percent",
        "# TYPE aml_memory_percent gauge",
        f"aml_memory_percent {sys_m.get('memory_percent', 0.0)}",
        "# HELP aml_disk_percent System Disk space usage percent",
        "# TYPE aml_disk_percent gauge",
        f"aml_disk_percent {sys_m.get('disk_percent', 0.0)}",
        "# HELP aml_db_latency_ms Database query execution time in ms",
        "# TYPE aml_db_latency_ms gauge",
        f"aml_db_latency_ms {db_m.get('latency_ms', 0.0)}",
        "# HELP aml_redis_latency_ms Redis connection ping latency in ms",
        "# TYPE aml_redis_latency_ms gauge",
        f"aml_redis_latency_ms {redis_m.get('latency_ms', 0.0)}",
        "# HELP aml_celery_queue_depth Celery default task queue depth size",
        "# TYPE aml_celery_queue_depth gauge",
        f"aml_celery_queue_depth {celery_m.get('queue_length', 0)}",
        "# HELP aml_celery_active_workers Count of active Celery worker instances",
        "# TYPE aml_celery_active_workers gauge",
        f"aml_celery_active_workers {celery_m.get('active_workers', 0)}",
        "# HELP aml_api_requests_count Total number of API requests recorded in past hour",
        "# TYPE aml_api_requests_count counter",
        f"aml_api_requests_count {api_m.get('request_count_1h', 0)}",
        "# HELP aml_api_latency_average_ms Average API request response duration in ms",
        "# TYPE aml_api_latency_average_ms gauge",
        f"aml_api_latency_average_ms {api_m.get('average_latency_ms', 0.0)}",
        "# HELP aml_api_error_rate_percent Percent of API requests failing in past hour",
        "# TYPE aml_api_error_rate_percent gauge",
        f"aml_api_error_rate_percent {api_m.get('error_rate_percent', 0.0)}",
    ]

    return PlainTextResponse("\n".join(lines) + "\n")
