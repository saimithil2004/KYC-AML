import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.core.database import get_db
from app.dependencies.auth import verify_admin
from app.models.models import User
from app.services.devops_service import DevOpsService
from app.services.audit_service import AuditService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status", response_model=Dict[str, Any])
async def get_devops_status(
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full platform DevOps metrics and infrastructure status."""
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DEVOPS_STATUS_VIEWED",
        entity_name="system",
        entity_id=None,
    )
    await db.commit()
    return await DevOpsService.get_full_devops_status(db)


@router.get("/pods", response_model=List[Dict[str, Any]])
async def get_kubernetes_pods(
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """List active Kubernetes deployment pods."""
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DEVOPS_PODS_VIEWED",
        entity_name="kubernetes",
        entity_id=None,
    )
    await db.commit()
    return await DevOpsService.get_kubernetes_pods()


@router.get("/db-performance", response_model=Dict[str, Any])
async def get_db_performance(
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve database connection pool and replication metrics."""
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DEVOPS_DB_VIEWED",
        entity_name="database",
        entity_id=None,
    )
    await db.commit()
    return await DevOpsService.get_db_performance(db)


@router.get("/queues", response_model=Dict[str, Any])
async def get_celery_queues(
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Inspect background celery tasks and active queues status."""
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DEVOPS_QUEUES_VIEWED",
        entity_name="celery",
        entity_id=None,
    )
    await db.commit()
    return await DevOpsService.get_celery_queues()


@router.get("/redis", response_model=Dict[str, Any])
async def get_redis_status(
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve cache connection, Sentinel routing, and cluster details."""
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DEVOPS_REDIS_VIEWED",
        entity_name="redis",
        entity_id=None,
    )
    await db.commit()
    return await DevOpsService.get_redis_status()


@router.get("/kubernetes", response_model=Dict[str, Any])
async def get_kubernetes_summary(
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Expose high level Kubernetes deployment config structures."""
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DEVOPS_KUBERNETES_VIEWED",
        entity_name="kubernetes",
        entity_id=None,
    )
    await db.commit()
    pods = await DevOpsService.get_kubernetes_pods()
    
    # Compile a status summary of core K8s objects (Deployments, HPAs, Services)
    return {
        "namespace": "aml-compliance",
        "deployments": [
            {"name": "aml-backend-api", "replicas_configured": 2, "replicas_available": 2, "strategy": "RollingUpdate"},
            {"name": "aml-frontend", "replicas_configured": 1, "replicas_available": 1, "strategy": "RollingUpdate"},
            {"name": "aml-celery-worker", "replicas_configured": 1, "replicas_available": 1, "strategy": "Recreate"},
        ],
        "services": [
            {"name": "aml-backend-api-svc", "type": "ClusterIP", "port": 8000},
            {"name": "aml-frontend-svc", "type": "NodePort", "port": 3000},
        ],
        "hpa": [
            {"name": "aml-backend-api-hpa", "target_deployment": "aml-backend-api", "min_replicas": 2, "max_replicas": 10, "current_cpu_percent": 12},
        ],
        "ingress": [
            {"name": "aml-ingress", "rules": [{"host": "compliance.enterprise.com", "paths": ["/api/v1", "/"]}]},
        ],
        "pods": pods,
    }
