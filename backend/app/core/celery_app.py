from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "aml_compliance_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # Explicitly list every module that contains @celery_app.task decorators.
    # This replaces autodiscover_tasks(["app"]) which only imported the empty
    # app/tasks/__init__.py and never reached the actual task modules.
    include=[
        "app.tasks.kyc_tasks",
        "app.tasks.schedule_tasks",
        "app.tasks.sync_tasks",
    ],
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

