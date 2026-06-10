from __future__ import annotations

import os

from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Module-level limiter so it can be imported and reset in tests. Storage and
# default limits are wired per-app in init_rate_limiting().
limiter = Limiter(key_func=get_remote_address)


def init_rate_limiting(app: Flask) -> None:
    """Apply a generous default API rate limit.

    Uses Redis storage when REDIS_URL is set so limits hold across restarts,
    otherwise falls back to in-process memory (fine for the single gthread
    worker). High-frequency or monitoring paths are exempted so the live feed
    and health checks are never throttled."""
    app.config.setdefault("RATELIMIT_DEFAULT", os.getenv("RATELIMIT_DEFAULT", "600 per minute"))
    app.config.setdefault("RATELIMIT_STORAGE_URI", app.config.get("REDIS_URL") or "memory://")
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    app.config.setdefault("RATELIMIT_ENABLED", os.getenv("RATELIMIT_ENABLED", "1") == "1")

    limiter.init_app(app)

    @limiter.request_filter
    def _exempt_high_frequency_paths() -> bool:
        path = request.path or ""
        return (
            path.startswith("/socket.io")
            or path.startswith("/api/health")
            or path.startswith("/api/market-data")
        )
