from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "aml_compliance_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes limit per screening run
)

# Auto-discover tasks from app.tasks sub-modules
celery_app.autodiscover_tasks(["app"])
