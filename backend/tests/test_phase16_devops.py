import os
import yaml
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db_pool_metrics, check_replica_health, get_read_db
from app.core.cache import cache
from app.services.devops_service import DevOpsService
from main import app

client = TestClient(app)

# ─── Mock DB Helper ───────────────────────────────────────────────────────────

class _ScalarResult:
    def __init__(self, items):
        self._items = items
    def first(self):
        return self._items[0] if self._items else None
    def all(self):
        return list(self._items)
    def scalars(self):
        return self

def make_mock_db(rows=None):
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=_ScalarResult(rows or []))
    db.get = AsyncMock(return_value=rows[0] if rows else None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db

# ─── TESTS ────────────────────────────────────────────────────────────────────

def test_config_variables_exist():
    """Verify that settings exposes new replica, sentinel, and cluster properties."""
    assert hasattr(settings, "DATABASE_REPLICA_URL")
    assert hasattr(settings, "REDIS_SENTINELS")
    assert hasattr(settings, "REDIS_SENTINEL_SERVICE_NAME")
    assert hasattr(settings, "REDIS_CLUSTER_MODE")
    assert hasattr(settings, "KUBERNETES_NAMESPACE")
    assert hasattr(settings, "DOCKER_IMAGE_VERSION")
    assert hasattr(settings, "PROMETHEUS_METRICS_ENABLED")


@pytest.mark.asyncio
async def test_database_replica_routing():
    """Verify get_read_db generator is initialized and executes queries."""
    generator = get_read_db()
    session = await anext(generator)
    assert session is not None
    await generator.aclose()


@pytest.mark.asyncio
async def test_replica_health_unconfigured():
    """Verify replica health check response when replica url is not set."""
    with patch("app.core.config.settings.DATABASE_REPLICA_URL", ""):
        health = await check_replica_health()
        assert health["status"] == "unconfigured"
        assert health["latency_ms"] == 0.0


def test_get_db_pool_metrics():
    """Verify connection pool metrics schema structure."""
    metrics = get_db_pool_metrics()
    assert "primary" in metrics
    assert "replica" in metrics
    assert "pool_size" in metrics["primary"]
    assert "checked_out" in metrics["primary"]


@pytest.mark.asyncio
async def test_cache_stats_sentinel_and_cluster():
    """Verify cache.stats reports sentinel and cluster configuration attributes."""
    stats = await cache.stats()
    assert "sentinel_active" in stats
    assert "cluster_active" in stats
    assert "latency_ms" in stats


@pytest.mark.asyncio
async def test_devops_service_system_metrics():
    """Verify system cpu/memory/disk metrics collection matches schema."""
    metrics = await DevOpsService.get_system_metrics()
    assert "cpu_percent" in metrics
    assert "memory_percent" in metrics
    assert "disk_percent" in metrics
    assert isinstance(metrics["cpu_percent"], float)


@pytest.mark.asyncio
async def test_devops_service_celery_queues():
    """Verify celery queues status querying checks Redis length."""
    stats = await DevOpsService.get_celery_queues()
    assert "queue_length" in stats
    assert "active_workers_count" in stats
    assert "active_tasks_count" in stats


@pytest.mark.asyncio
async def test_devops_service_screening_statistics():
    """Verify avg screening time aggregation parses monitoring history."""
    db = make_mock_db([1250])  # Average ms
    stats = await DevOpsService.get_screening_statistics(db)
    assert "total_cases" in stats
    assert "average_screening_time_sec" in stats
    # 1250 ms -> 1.25s
    assert stats["average_screening_time_sec"] == 1.25


def test_kubernetes_manifests_exist_and_valid():
    """Verify K8s manifest files are present under deployment folder and have valid YAML syntax."""
    manifest_dir = os.path.join("..", "deployment", "kubernetes")
    if not os.path.exists(manifest_dir):
        # Fallback to direct directory path check
        manifest_dir = os.path.join("deployment", "kubernetes")
    
    assert os.path.exists(manifest_dir), f"Kubernetes manifests folder missing at {manifest_dir}"
    
    yaml_files = [
        "namespace.yaml", "configmap.yaml", "secrets.yaml", "postgres.yaml",
        "redis.yaml", "backend.yaml", "celery.yaml", "frontend.yaml",
        "ingress.yaml", "network-policy.yaml"
    ]
    
    for f_name in yaml_files:
        f_path = os.path.join(manifest_dir, f_name)
        assert os.path.exists(f_path), f"K8s manifest file missing: {f_path}"
        # Validate syntax
        with open(f_path, "r", encoding="utf-8") as stream:
            try:
                list(yaml.safe_load_all(stream))
            except yaml.YAMLError as exc:
                pytest.fail(f"Invalid YAML manifest file: {f_path} - {exc}")


def test_docker_compose_files_exist_and_valid():
    """Verify docker compose production, monitoring, and scaling files exist and parse successfully."""
    compose_files = [
        "docker-compose.prod.yml",
        "docker-compose.monitoring.yml",
        "docker-compose.scaling.yml"
    ]
    for c_file in compose_files:
        c_path = os.path.join("..", c_file)
        if not os.path.exists(c_path):
            c_path = c_file
        
        assert os.path.exists(c_path), f"Docker compose file missing: {c_path}"
        with open(c_path, "r", encoding="utf-8") as stream:
            try:
                yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                pytest.fail(f"Invalid YAML docker compose file: {c_path} - {exc}")


def test_nginx_and_traefik_configs_exist():
    """Verify load balancing configs exist."""
    nginx_path = os.path.join("..", "deployment", "nginx", "nginx.conf")
    if not os.path.exists(nginx_path):
        nginx_path = os.path.join("deployment", "nginx", "nginx.conf")
    
    traefik_path = os.path.join("..", "deployment", "traefik", "traefik.yml")
    if not os.path.exists(traefik_path):
        traefik_path = os.path.join("deployment", "traefik", "traefik.yml")

    assert os.path.exists(nginx_path)
    assert os.path.exists(traefik_path)


def test_github_workflows_exist_and_valid():
    """Verify GitHub Actions workflow configuration files exist and parse successfully."""
    workflow_dir = os.path.join("..", ".github", "workflows")
    if not os.path.exists(workflow_dir):
        workflow_dir = os.path.join(".github", "workflows")

    assert os.path.exists(workflow_dir)
    workflows = ["backend.yml", "frontend.yml", "docker.yml", "security.yml", "deploy.yml"]
    for wf in workflows:
        w_path = os.path.join(workflow_dir, wf)
        assert os.path.exists(w_path), f"Workflow file missing: {w_path}"
        with open(w_path, "r", encoding="utf-8") as stream:
            try:
                yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                pytest.fail(f"Invalid YAML workflow file: {w_path} - {exc}")


def test_health_startup_endpoint():
    """Verify liveness and readiness, plus startup probe endpoints."""
    # Test liveness
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    # Test readiness
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    assert "database" in res.json()["details"]

    # Test startup
    res = client.get("/api/v1/health/startup")
    assert res.status_code in (200, 503)
    if res.status_code == 200:
        assert res.json()["status"] == "healthy"


def test_metrics_endpoint_prometheus_format():
    """Verify metrics returns plain text format scraping data with no JSON formatting quoting."""
    res = client.get("/api/v1/health/metrics")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "aml_cpu_percent" in res.text
    assert "aml_db_latency_ms" in res.text
