"""
Structured Enterprise Logging — Phase 15
==========================================
Provides a structured JSON logging system with:
  - Correlation IDs (propagated via contextvars)
  - Request IDs and Trace IDs
  - User ID and Customer ID context
  - Rotating file handlers (10MB, 10 backups)
  - Separate log streams: app, security, agents, celery
  - Compatible with existing AuditService (does not replace it)

Usage:
    from app.core.logging_config import get_logger, set_correlation_id, set_request_context

    logger = get_logger(__name__)
    set_correlation_id("abc-123")
    logger.info("Customer screened", extra={"customer_id": "xyz", "duration_ms": 42})
"""

import json
import logging
import logging.handlers
import os
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

# ─── Context Variables ─────────────────────────────────────────────────────────

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")
_customer_id: ContextVar[str] = ContextVar("customer_id", default="")


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def get_correlation_id() -> str:
    return _correlation_id.get() or ""


def set_request_id(rid: str) -> None:
    _request_id.set(rid)


def get_request_id() -> str:
    return _request_id.get() or ""


def set_user_context(user_id: str, customer_id: str = "") -> None:
    _user_id.set(str(user_id) if user_id else "")
    _customer_id.set(str(customer_id) if customer_id else "")


def generate_correlation_id() -> str:
    return str(uuid4()).replace("-", "")[:16]


# ─── JSON Log Formatter ────────────────────────────────────────────────────────


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            # Context
            "correlation_id": get_correlation_id(),
            "request_id": get_request_id(),
            "user_id": _user_id.get() or "",
            "customer_id": _customer_id.get() or "",
        }

        # Extra fields passed via `extra={}`
        for key, val in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            ):
                if not key.startswith("_"):
                    log_data[key] = val

        # Exception info
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data, default=str)


class PlainTextFormatter(logging.Formatter):
    """Human-readable formatter for console/development."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        rid = get_request_id()[:8] if get_request_id() else "--------"
        base = f"{color}[{ts}] [{record.levelname:<8}] [{rid}] {record.name}: {record.getMessage()}{self.RESET}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# ─── Logger Configuration ──────────────────────────────────────────────────────


def configure_logging() -> None:
    """
    Configure the application logging system.
    Call this once at startup (inside the FastAPI lifespan or main.py).
    """
    from app.core.config import settings

    log_dir = settings.LOG_DIR
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    use_json = settings.LOG_JSON

    os.makedirs(log_dir, exist_ok=True)

    # Choose formatter
    if use_json:
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
    console_formatter = PlainTextFormatter()

    def _make_rotating_handler(filename: str) -> logging.handlers.RotatingFileHandler:
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, filename),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,
            encoding="utf-8",
        )
        handler.setFormatter(file_formatter)
        return handler

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(_make_rotating_handler("app.log"))

    # Security-specific logger
    sec_logger = logging.getLogger("security")
    sec_logger.addHandler(_make_rotating_handler("security.log"))
    sec_logger.propagate = True

    # Agent logger
    agent_logger = logging.getLogger("agents")
    agent_logger.addHandler(_make_rotating_handler("agents.log"))
    agent_logger.propagate = True

    # Celery logger
    celery_logger = logging.getLogger("celery")
    celery_logger.addHandler(_make_rotating_handler("celery.log"))
    celery_logger.propagate = False  # Don't double-log

    # Suppress noisy third-party loggers
    for noisy in ["httpx", "asyncio", "uvicorn.access"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.info(
        f"Logging configured — Level: {settings.LOG_LEVEL}, JSON: {use_json}, Dir: {log_dir}"
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call configure_logging() once at startup first."""
    return logging.getLogger(name)
