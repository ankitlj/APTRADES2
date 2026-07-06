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
# Breeze's NSE cash index rows can resolve to display-name tokens such as
# "NIFTY 50", which are not valid websocket stock tokens. Use the matching NFO
# futures contracts for websocket streaming; REST summary still provides the
# cash/index fallback values for display.
DEFAULT_WATCHLIST: list[dict[str, str]] = [
    {"symbol": "NIFTY", "exchange": "NFO", "product_type": "futures"},
    {"symbol": "BANKNIFTY", "exchange": "NFO", "product_type": "futures"},
    {"symbol": "FINNIFTY", "exchange": "NFO", "product_type": "futures"},
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
        # Vercel reliably proxies /api/* to the GCP VM. Mount Socket.IO under
        # the same prefix so polling and websocket upgrade share that route.
        "path": "api/socket.io",
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
    )
    _worker = worker
    app.extensions["market_data_worker"] = worker
    return worker


def resolve_subscription_items(
    database_url: str | None,
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve display symbols to broker tokens so the worker can subscribe by
    Breeze stock-token. Unresolvable rows are skipped (degraded-safe).

    When an item already supplies a ``token``, DB resolution is skipped and the
    item is passed through directly. This allows the frontend to subscribe option
    contracts whose tokens were pre-resolved from an option-chain response."""
    resolved_items: list[dict[str, Any]] = []
    for item in requests:
        token = str(item.get("token") or "").strip()
        exchange = str(item.get("exchange") or item.get("exchange_code") or "").strip().upper()
        symbol = str(item.get("symbol") or "").strip()
        product_type = item.get("product_type")

        # Pre-resolved token shortcut — skip DB resolve
        if token:
            display_symbol = symbol or str(item.get("display_symbol") or "?").strip().upper()
            broker_symbol = str(item.get("broker_symbol") or display_symbol).strip().upper()
            if not exchange:
                continue
            if display_symbol == "BANK NIFTY":
                display_symbol = "BANKNIFTY"
            resolved_items.append(
                {
                    "display_symbol": display_symbol,
                    "broker_symbol": broker_symbol,
                    "exchange_code": exchange,
                    "product_type": product_type or "",
                    "token": token,
                    "expiry_date": item.get("expiry_date") or "",
                    "strike_price": item.get("strike_price") or "",
                    "right": item.get("right") or "",
                }
            )
            continue

        if not database_url:
            continue

        if not symbol or not exchange:
            continue
        resolver = SymbolResolver(database_url)
        try:
            resolved = resolver.resolve(symbol, exchange, product_type=product_type)
        except SymbolResolverError:
            continue
        if not resolved.token:
            continue
        display_symbol = resolved.display_symbol
        # Normalise display_symbol for symbols where the DB alias/seed-row
        # display_symbol has a space (e.g. "BANK NIFTY") but the REST ticker
        # response key is the compact form ("BANKNIFTY"). The frontend merge
        # key is ticks[item.symbol.toUpperCase()], so both paths must emit
        # the same key.
        if display_symbol == "BANK NIFTY":
            display_symbol = "BANKNIFTY"
        resolved_items.append(
            {
                "display_symbol": display_symbol,
                "broker_symbol": resolved.broker_symbol,
                "exchange_code": resolved.exchange_code,
                "product_type": resolved.product_type,
                "token": resolved.token,
                "expiry_date": resolved.expiry_date.isoformat() if resolved.expiry_date else "",
                "strike_price": resolved.strike_price or "",
                "right": resolved.right or "",
            }
        )
    return resolved_items


def _subscribe_requests(requests: list[dict[str, Any]]) -> dict[str, Any]:
    worker = _worker
    if worker is None:
        return {"accepted": [], "skipped": [], "count": 0}
    db_url = current_app.config.get("DATABASE_URL")
    items = resolve_subscription_items(db_url, requests)
    print(f"[diag] _subscribe_requests db_url={'set' if db_url else 'MISSING'} requests_in={len(requests)} resolved_out={len(items)}")
    for r in requests:
        print(f"[diag]   request symbol={r.get('symbol')} exchange={r.get('exchange')} token={'set' if r.get('token') else 'MISSING'}")
    for i in items:
        print(f"[diag]   resolved display_symbol={i.get('display_symbol')} exchange={i.get('exchange_code')} token={i.get('token')}")
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
