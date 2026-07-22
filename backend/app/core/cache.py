"""
Redis Cache Service — Phase 15
================================
Provides a reusable Redis-backed cache with automatic in-memory fallback
when Redis is unavailable (development / test environments).

Features:
  - get / set / delete / pattern-delete
  - TTL management
  - Cache key namespacing
  - Async and sync access modes
  - Cache statistics tracking

Usage:
    from app.core.cache import cache

    await cache.set("dashboard:metrics", data, ttl=120)
    data = await cache.get("dashboard:metrics")
    await cache.delete("dashboard:metrics")
    await cache.delete_pattern("dashboard:*")
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# ─── In-Memory Fallback ────────────────────────────────────────────────────────


class _InMemoryStore:
    """Simple TTL-aware in-memory cache for when Redis is unavailable."""

    def __init__(self):
        self._store: Dict[str, tuple] = {}  # key -> (value, expires_at)
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expires_at = time.time() + ttl if ttl else None
        self._store[key] = (value, expires_at)
        self.sets += 1

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self.deletes += 1

    def delete_pattern(self, pattern: str) -> int:
        prefix = pattern.rstrip("*")
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]
        self.deletes += len(to_delete)
        return len(to_delete)

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "backend": "memory",
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "hit_rate": round(self.hits / total * 100, 2) if total else 0.0,
            "keys": len(self._store),
        }

    def clear(self) -> None:
        self._store.clear()


# ─── Redis Cache Client ────────────────────────────────────────────────────────


class CacheService:
    """
    Async Redis cache service with transparent in-memory fallback.
    Instantiated as a singleton: `from app.core.cache import cache`
    """

    def __init__(self):
        self._redis = None
        self._fallback = _InMemoryStore()
        self._redis_available = False
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0

    async def _init_redis(self) -> bool:
        """Lazy-initialize Redis connection."""
        if self._redis is not None:
            return self._redis_available
        try:
            import redis.asyncio as aioredis
            from redis.asyncio.sentinel import Sentinel
            from redis.asyncio.cluster import RedisCluster
            from app.core.config import settings

            if settings.REDIS_CLUSTER_MODE:
                logger.info("[CACHE] Initializing Redis Cluster mode...")
                self._redis = RedisCluster.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    encoding="utf-8",
                    socket_timeout=2,
                )
            elif settings.REDIS_SENTINELS:
                logger.info(
                    f"[CACHE] Initializing Redis Sentinel mode with: {settings.REDIS_SENTINELS}"
                )
                sentinel_nodes = []
                for item in settings.REDIS_SENTINELS.split(","):
                    if not item.strip():
                        continue
                    if ":" in item:
                        host, port = item.split(":")
                        sentinel_nodes.append((host, int(port)))
                    else:
                        sentinel_nodes.append((item, 26379))

                sentinel = Sentinel(
                    sentinel_nodes,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                    decode_responses=True,
                    encoding="utf-8",
                )
                self._redis = sentinel.master_for(
                    settings.REDIS_SENTINEL_SERVICE_NAME,
                    redis_class=aioredis.Redis,
                )
            else:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                )

            await self._redis.ping()
            self._redis_available = True
            logger.info("[CACHE] Redis connected successfully.")
        except Exception as exc:
            self._redis_available = False
            self._redis = None
            logger.warning(
                f"[CACHE] Redis unavailable, using in-memory fallback: {exc}"
            )
        return self._redis_available

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value. Returns None on miss."""
        await self._init_redis()
        if self._redis_available:
            try:
                raw = await self._redis.get(key)
                if raw is None:
                    self._misses += 1
                    return None
                self._hits += 1
                return json.loads(raw)
            except Exception as exc:
                logger.warning(f"[CACHE] Redis get failed for key={key}: {exc}")
                self._redis_available = False

        # Fallback
        return self._fallback.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value in cache with optional TTL (seconds)."""
        from app.core.config import settings

        effective_ttl = ttl or settings.REDIS_CACHE_TTL
        await self._init_redis()
        if self._redis_available:
            try:
                serialized = json.dumps(value, default=str)
                await self._redis.setex(key, effective_ttl, serialized)
                self._sets += 1
                return
            except Exception as exc:
                logger.warning(f"[CACHE] Redis set failed for key={key}: {exc}")
                self._redis_available = False

        # Fallback
        self._fallback.set(key, value, ttl=effective_ttl)

    async def delete(self, key: str) -> None:
        """Delete a single cache entry."""
        await self._init_redis()
        if self._redis_available:
            try:
                await self._redis.delete(key)
                self._deletes += 1
                return
            except Exception:
                pass
        self._fallback.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern (e.g. 'dashboard:*')."""
        await self._init_redis()
        if self._redis_available:
            try:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
                    self._deletes += len(keys)
                    return len(keys)
                return 0
            except Exception:
                pass
        return self._fallback.delete_pattern(pattern)

    async def get_or_set(self, key: str, factory, ttl: Optional[int] = None) -> Any:
        """
        Return cached value if present, otherwise call factory(), cache result, and return it.
        factory can be sync or async.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        await self.set(key, value, ttl=ttl)
        return value

    async def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        from app.core.config import settings

        await self._init_redis()
        base = {
            "backend": "redis" if self._redis_available else "memory",
            "redis_available": self._redis_available,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "deletes": self._deletes,
            "sentinel_active": bool(settings.REDIS_SENTINELS and self._redis_available),
            "cluster_active": bool(
                settings.REDIS_CLUSTER_MODE and self._redis_available
            ),
            "latency_ms": 0.0,
        }
        total = self._hits + self._misses
        base["hit_rate"] = round(self._hits / total * 100, 2) if total else 0.0

        if not self._redis_available:
            base.update(self._fallback.stats())
        elif self._redis:
            try:
                start = time.perf_counter()
                await self._redis.ping()
                base["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)

                if settings.REDIS_CLUSTER_MODE:
                    try:
                        info = await self._redis.info()
                        first_node = (
                            list(info.keys())[0] if isinstance(info, dict) else None
                        )
                        node_info = info[first_node] if first_node else info
                        base["redis_hits"] = node_info.get("keyspace_hits", 0)
                        base["redis_misses"] = node_info.get("keyspace_misses", 0)
                        base["connected_clients"] = node_info.get(
                            "connected_clients", 0
                        )
                    except Exception:
                        base["redis_hits"] = 0
                        base["redis_misses"] = 0
                        base["connected_clients"] = 0
                else:
                    info = await self._redis.info("stats")
                    clients_info = await self._redis.info("clients")
                    base["redis_hits"] = info.get("keyspace_hits", 0)
                    base["redis_misses"] = info.get("keyspace_misses", 0)
                    base["connected_clients"] = clients_info.get("connected_clients", 0)
            except Exception:
                pass
        return base

    # ─── Namespaced Helpers ──────────────────────────────────────────────────

    async def invalidate_dashboard(self) -> None:
        await self.delete_pattern("dashboard:*")

    async def invalidate_reports(self) -> None:
        await self.delete_pattern("report:*")

    async def invalidate_analytics(self) -> None:
        await self.delete_pattern("analytics:*")

    async def invalidate_regulations(self) -> None:
        await self.delete_pattern("regulation:*")

    async def invalidate_monitoring(self) -> None:
        await self.delete_pattern("monitoring:*")


# ─── Singleton Instance ────────────────────────────────────────────────────────

cache = CacheService()


# ─── Cache Decorator ──────────────────────────────────────────────────────────


def cached(key_template: str, ttl: int = 300):
    """
    Decorator to cache async function results.
    key_template can include {args[0]}, {kwargs[name]} style placeholders.

    Example:
        @cached("dashboard:{args[0]}", ttl=60)
        async def get_dashboard_metrics(user_id: str): ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                key = key_template.format(args=args, kwargs=kwargs, **kwargs)
            except Exception:
                key = key_template
            cached_val = await cache.get(key)
            if cached_val is not None:
                return cached_val
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
