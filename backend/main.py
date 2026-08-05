import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.logging_config import configure_logging, get_logger
from app.core.schema_helpers import ensure_phase15_schema, ensure_phase17_schema
from app.core.database import SessionLocal
from app.core.middleware import (
    RequestIDMiddleware, SecurityHeadersMiddleware, 
    RequestSizeLimitMiddleware, RequestLoggingMiddleware
)

# Configure logging early
configure_logging()
logger = get_logger("main")

# Suppress watchfiles' internal per-event logger immediately.
# uvicorn calls watchfiles.watch() with watch_filter=None, so watchfiles logs
# every raw OS filesystem event (.pyc writes, etc.) at INFO BEFORE uvicorn's
# own FileFilter decides whether to actually reload. Silencing this logger
# removes the spam without affecting hot-reload behaviour.
import logging as _logging
_logging.getLogger("watchfiles.main").setLevel(_logging.WARNING)
_logging.getLogger("watchfiles").setLevel(_logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing AML & KYC Compliance Platform (Phase 17)...")
    

    # Auto-migrations
    async with SessionLocal() as db:
        try:
            logger.info("Verifying database schema version...")
            await ensure_phase15_schema(db)
            await ensure_phase17_schema(db)
            logger.info("Database schema verification complete.")
        except Exception as e:
            logger.error(f"Failed to verify/migrate database schema on startup: {e}")
            
    yield
    # Shutdown
    logger.info("Shutting down AML & KYC Compliance Platform...")

# Global rate limiter setup
limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED, default_limits=["100/minute"])

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Secure production CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 15 ASGI middlewares (applied outer-to-inner, so reverse order of execution)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=settings.MAX_UPLOAD_SIZE_MB)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    # Always run from the backend directory so relative imports work
    _base = Path(__file__).parent
    os.chdir(_base)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # Whitelist approach: ONLY watch actual Python source files.
        # This prevents watchfiles from triggering on .pyc bytecode,
        # __pycache__ dirs, log files, SQLite WAL files, or anything else
        # the running server writes to disk — fixing the infinite reload loop.
        reload_dirs=[str(_base / "app")],
        reload_includes=["*.py"],
        reload_excludes=["*/__pycache__/*", "*.pyc"],
    )



