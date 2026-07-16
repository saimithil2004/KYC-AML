import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocalSync
from app.services.database_integration.sync_service import SyncService

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.sync_tasks.sync_customers")
def sync_customers_task():
    logger.info("[CELERY] Running customers sync task")
    db = SessionLocalSync()
    try:
        service = SyncService(db)
        return service.sync_customers()
    except Exception as e:
        logger.error(f"[CELERY] Customers sync task failed: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="tasks.sync_tasks.sync_accounts")
def sync_accounts_task():
    logger.info("[CELERY] Running accounts sync task")
    db = SessionLocalSync()
    try:
        service = SyncService(db)
        return service.sync_accounts()
    except Exception as e:
        logger.error(f"[CELERY] Accounts sync task failed: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="tasks.sync_tasks.sync_transactions")
def sync_transactions_task():
    logger.info("[CELERY] Running transactions sync task")
    db = SessionLocalSync()
    try:
        service = SyncService(db)
        return service.sync_transactions()
    except Exception as e:
        logger.error(f"[CELERY] Transactions sync task failed: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="tasks.sync_tasks.sync_companies")
def sync_companies_task():
    logger.info("[CELERY] Running companies sync task")
    db = SessionLocalSync()
    try:
        service = SyncService(db)
        return service.sync_companies()
    except Exception as e:
        logger.error(f"[CELERY] Companies sync task failed: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="tasks.sync_tasks.daily_sync")
def daily_sync_task():
    """Performs daily full import synchronization across all datasets."""
    logger.info("[CELERY] Running daily full sync task")
    db = SessionLocalSync()
    try:
        service = SyncService(db)
        return service.run_full_sync()
    except Exception as e:
        logger.error(f"[CELERY] Daily sync task failed: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="tasks.sync_tasks.incremental_sync")
def incremental_sync_task():
    logger.info("[CELERY] Running incremental sync task")
    db = SessionLocalSync()
    try:
        service = SyncService(db)
        # For simplicity in mock mode, incremental runs the full sync or a subset
        return service.run_full_sync()
    except Exception as e:
        logger.error(f"[CELERY] Incremental sync task failed: {e}")
        raise e
    finally:
        db.close()
