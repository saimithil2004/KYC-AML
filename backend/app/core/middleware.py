"""
Security Middleware — Phase 15
================================
Production-grade ASGI middleware stack:

  1. RequestIDMiddleware      — Injects X-Request-ID into every response
  2. SecurityHeadersMiddleware — Adds HSTS, CSP, X-Frame-Options, etc.
  3. RequestSizeLimitMiddleware — Rejects oversized request bodies
  4. CorrelationIDMiddleware   — Propagates correlation IDs via context vars

All middleware classes are Starlette-compatible and work with FastAPI.
"""

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.logging_config import (
    set_correlation_id, set_request_id, generate_correlation_id
)

logger = logging.getLogger(__name__)


# ─── 1. Request ID Middleware ──────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique X-Request-ID header into every request and response.
    If the client sends X-Request-ID, that value is propagated.
    Also sets the correlation context var for structured logging.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or generate_correlation_id()

        set_request_id(request_id)
        set_correlation_id(correlation_id)

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        # Log slow requests (>2000ms)
        if duration_ms > 2000:
            logger.warning(
                "Slow request detected",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": duration_ms,
                    "status_code": response.status_code,
                }
            )

        return response


# ─── 2. Security Headers Middleware ───────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds production security headers to every response.
    Headers align with OWASP security hardening best practices.
    """

    SECURITY_HEADERS = {
        # Strict Transport Security — enforce HTTPS for 1 year
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        # Prevent MIME type sniffing
        "X-Content-Type-Options": "nosniff",
        # Deny iframe embedding
        "X-Frame-Options": "DENY",
        # Legacy XSS filter (for older browsers)
        "X-XSS-Protection": "1; mode=block",
        # Control referrer information
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # Permissions Policy — restrict dangerous browser features
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        # Content Security Policy — restrict sources
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        ),
        # Remove server information fingerprinting
        "Server": "AML-Platform",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value
        # Remove potentially revealing headers
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]
        return response


# ─── 3. Request Size Limit Middleware ─────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects request bodies exceeding the configured maximum size.
    Protects against memory exhaustion attacks.
    """

    def __init__(self, app: ASGIApp, max_size_mb: int = 10):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_size_bytes:
                    logger.warning(
                        "Request body too large",
                        extra={
                            "path": request.url.path,
                            "content_length": content_length,
                            "max_bytes": self.max_size_bytes,
                        }
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large. Maximum allowed: {self.max_size_bytes // (1024*1024)} MB"
                        }
                    )
            except ValueError:
                pass

        return await call_next(request)


# ─── 4. Request Logging Middleware ────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs structured information for every HTTP request and response.
    Skips health check endpoints to reduce noise.
    """

    SKIP_PATHS = {"/health", "/health/live", "/health/ready", "/"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_level = logging.WARNING if response.status_code >= 400 else logging.DEBUG
        logger.log(
            log_level,
            f"{request.method} {request.url.path} -> {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "")[:200],
            }
        )
        return response
