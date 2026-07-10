from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Synchronous engine and sessionmaker for background Celery tasks
db_url = settings.DATABASE_URL
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

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
            
class CRUDHelper:
    """Standard repository pattern abstraction placeholder."""
    pass
