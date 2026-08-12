import logging
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger("app.core.database")


def log_database_connection_info(url_str: str = None):
    """
    Defensive logging helper that parses the database URL and prints host, port,
    database name, and connection scheme.
    """
    target_url = url_str or settings.DATABASE_URL
    try:
        parsed = urlparse(target_url)
        scheme = parsed.scheme or "unknown"
        host = parsed.hostname or "localhost"
        port = parsed.port if parsed.port is not None else (5432 if "postgresql" in scheme else "N/A")
        db_name = parsed.path.lstrip("/") if parsed.path else "local_db"
        user = parsed.username or "none"
        logger.info(
            f"Database Configuration -> Host: '{host}', Port: {port}, Database: '{db_name}', Scheme: '{scheme}', User: '{user}'"
        )
    except Exception as exc:
        logger.warning(f"Could not parse DATABASE_URL for logging: {exc}")


# Log configuration on module import
log_database_connection_info(settings.DATABASE_URL)

# Initialize primary engine
db_url = settings.DATABASE_URL

# Fallback check for local development outside Docker
if db_url.startswith("postgresql") and "postgres:5432" in db_url:
    # Handle legacy unresolvable container hostname when running on host machine
    logger.warning(
        "Detected unresolvable Docker hostname 'postgres' in DATABASE_URL while running on host. "
        "Rewriting host to 'localhost'."
    )
    db_url = db_url.replace("@postgres:5432", "@localhost:5432")

try:
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
except Exception as exc:
    logger.warning(
        f"Failed to initialize PostgreSQL engine with URL '{db_url}': {exc}. "
        "Falling back to local SQLite database."
    )
    db_url = "sqlite+aiosqlite:///./aml_compliance_db.db"
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
    )

SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Synchronous engine and sessionmaker for background Celery tasks
if db_url.startswith("postgresql+asyncpg://"):
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
elif db_url.startswith("sqlite+aiosqlite://"):
    sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
else:
    sync_url = db_url

sync_engine = create_engine(
    sync_url,
    pool_pre_ping=True if not sync_url.startswith("sqlite") else False,
)

SessionLocalSync = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ─── DATABASE READ REPLICA ──────────────────────────────────────────────────
replica_engine = None
SessionLocalReplica = None

if settings.DATABASE_REPLICA_URL:
    replica_engine = create_async_engine(
        settings.DATABASE_REPLICA_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    SessionLocalReplica = async_sessionmaker(
        bind=replica_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )
else:
    replica_engine = engine
    SessionLocalReplica = SessionLocal

Base = declarative_base()


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_read_db():
    async with SessionLocalReplica() as session:
        try:
            yield session
        finally:
            await session.close()


# ─── METRICS & HEALTH CHECKS ──────────────────────────────────────────────────
import time
from sqlalchemy import text


def get_engine_pool_stats(eng):
    if not eng:
        return {"pool_size": 0, "checked_out": 0, "overflow": 0}
    try:
        pool = eng.pool
        pool_size = pool.size() if hasattr(pool, "size") else getattr(pool, "_size", 0)
        checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0
        overflow = pool.overflow() if hasattr(pool, "overflow") else 0
        return {
            "pool_size": pool_size,
            "checked_out": checked_out,
            "overflow": overflow,
        }
    except Exception:
        return {"pool_size": 0, "checked_out": 0, "overflow": 0}


def get_db_pool_metrics() -> dict:
    return {
        "primary": get_engine_pool_stats(engine),
        "replica": (
            get_engine_pool_stats(replica_engine)
            if settings.DATABASE_REPLICA_URL
            else {"pool_size": 0, "checked_out": 0, "overflow": 0}
        ),
    }


async def check_replica_health() -> dict:
    if not settings.DATABASE_REPLICA_URL:
        return {"status": "unconfigured", "latency_ms": 0.0}

    start_time = time.perf_counter()
    try:
        async with SessionLocalReplica() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start_time) * 1000
        return {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "latency_ms": 0.0}


class CRUDHelper:
    """Standard repository pattern abstraction placeholder."""

    pass
