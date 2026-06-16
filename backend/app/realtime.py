from __future__ import annotations

import logging
from typing import Any

from flask import Flask, current_app, request
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

from .services.market_data_worker import MarketDataWorker
from .services.symbol_resolver import SymbolResolver, SymbolResolverError

# Single Socket.IO server for the whole app. Threading async mode keeps the
# existing gunicorn/REST stack working with no eventlet/gevent monkey-patching;
# the client transparently negotiates websocket or long-polling transport.
socketio = SocketIO(async_mode="threading", cors_allowed_origins="*")

# The default dashboard watchlist that every connected client gets streamed.
DEFAULT_WATCHLIST: list[dict[str, str]] = [
    {"symbol": "NIFTY", "exchange": "NFO", "product_type": "futures"},
    {"symbol": "BANKNIFTY", "exchange": "NFO", "product_type": "futures"},
]

_worker: MarketDataWorker | None = None


def get_worker() -> MarketDataWorker | None:
    return _worker


def init_realtime(app: Flask) -> MarketDataWorker:
    """Attach Socket.IO to the app and build the market-data worker.

    Side-effect free beyond wiring: the worker is created but not started, and
    no Breeze connection is opened until the first client connects."""
    global _worker

    origins = app.config.get("CORS_ORIGINS") or "*"
    redis_url = app.config.get("REDIS_URL")
    # Phase 19: a Redis message queue makes emits from the breeze-connect thread
    # reliable (no cross-thread buffering); the tuned ping timeout rides out
    # brief stalls instead of dropping the socket.
    init_kwargs: dict[str, Any] = {
        "cors_allowed_origins": origins,
        "async_mode": "threading",
        "ping_interval": app.config.get("SOCKETIO_PING_INTERVAL", 25),
        "ping_timeout": app.config.get("SOCKETIO_PING_TIMEOUT", 60),
    }
    if redis_url:
        init_kwargs["message_queue"] = redis_url
    socketio.init_app(app, **init_kwargs)

    worker = MarketDataWorker(
        app_key=app.config.get("BREEZE_API_KEY"),
        secret_key=app.config.get("BREEZE_SECRET_KEY"),
        session_token=app.config.get("BREEZE_SESSION_TOKEN"),
        redis_url=redis_url,
        publish=socketio.emit,
        database_url=app.config.get("DATABASE_URL"),
    )
    _worker = worker
    app.extensions["market_data_worker"] = worker
    return worker


def resolve_subscription_items(
    database_url: str | None,
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve display symbols to broker tokens so the worker can subscribe by
    Breeze stock-token. Unresolvable rows are skipped (degraded-safe)."""
    if not database_url:
        return []

    resolver = SymbolResolver(database_url)
    resolved_items: list[dict[str, Any]] = []
    for item in requests:
        symbol = str(item.get("symbol") or "").strip()
        exchange = str(item.get("exchange") or item.get("exchange_code") or "").strip().upper()
        product_type = item.get("product_type")
        if not symbol or not exchange:
            continue
        try:
            resolved = resolver.resolve(symbol, exchange, product_type=product_type)
        except SymbolResolverError:
            continue
        if not resolved.token:
            continue
        resolved_items.append(
            {
                "display_symbol": resolved.display_symbol,
                "broker_symbol": resolved.broker_symbol,
                "exchange_code": resolved.exchange_code,
                "product_type": resolved.product_type,
                "token": resolved.token,
            }
        )
    return resolved_items


def _subscribe_requests(requests: list[dict[str, Any]]) -> dict[str, Any]:
    worker = _worker
    if worker is None:
        return {"accepted": [], "skipped": [], "count": 0}
    items = resolve_subscription_items(current_app.config.get("DATABASE_URL"), requests)
    logger.info("market-data subscribe requests=%d resolved=%d requests=%s", len(requests), len(items), [r.get("symbol") for r in requests])
    return worker.subscribe(items)


@socketio.on("connect")
def _handle_connect() -> None:
    worker = _worker
    if worker is None:
        return
    logger.info("socket client connected sid=%s", request.sid)
    worker.ensure_started()
    # Stream the default dashboard watchlist to every client and send the
    # current connection status so the topbar badge can render immediately.
    _subscribe_requests(DEFAULT_WATCHLIST)
    socketio.emit("status", worker.status(), to=request.sid)
    for tick in worker.snapshot():
        socketio.emit("tick", tick, to=request.sid)


@socketio.on("disconnect")
def _handle_disconnect() -> None:
    logger.info("socket client disconnected sid=%s", request.sid)


@socketio.on("subscribe")
def _handle_subscribe(data: Any) -> None:
    requests = _coerce_requests(data)
    if not requests:
        logger.warning("socket subscribe with empty payload sid=%s", request.sid)
        return
    symbols = [str(r.get("symbol") or r.get("display_symbol") or "?") for r in requests]
    logger.info("socket subscribe sid=%s symbols=%s count=%d", request.sid, symbols, len(requests))
    _subscribe_requests(requests)


@socketio.on("unsubscribe")
def _handle_unsubscribe(data: Any) -> None:
    worker = _worker
    if worker is None:
        return
    requests = _coerce_requests(data)
    if not requests:
        logger.warning("socket unsubscribe with empty payload sid=%s", request.sid)
        return
    symbols = [str(r.get("symbol") or r.get("display_symbol") or "?") for r in requests]
    logger.info("socket unsubscribe sid=%s symbols=%s count=%d", request.sid, symbols, len(requests))
    items = resolve_subscription_items(current_app.config.get("DATABASE_URL"), requests)
    worker.unsubscribe(items)


def _coerce_requests(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        symbols = data.get("symbols")
        if isinstance(symbols, list):
            return [item for item in symbols if isinstance(item, dict)]
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []
