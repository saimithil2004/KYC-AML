# Background Tasks Package
# Explicitly import every sub-module so that @celery_app.task decorators are
# executed (and tasks registered) whenever this package is imported.
from app.tasks import kyc_tasks, schedule_tasks, sync_tasks  # noqa: F401
