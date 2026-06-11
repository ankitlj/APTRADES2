from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from ..db import create_session_factory
from ..models import MarketCandle
from ..realtime import DEFAULT_WATCHLIST, get_worker

market_data_bp = Blueprint("market_data", __name__)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _offline_status() -> dict[str, object]:
    return {
        "state": "offline",
        "configured": False,
        "subscriptions": 0,
        "symbols": [],
        "last_tick_at": None,
        "error": "Market data worker is not initialised.",
    }


@market_data_bp.get("/market-data/status")
def market_data_status() -> tuple[object, int]:
    """Connection state for the live/degraded/offline topbar badge. Always 200
    so the frontend can poll it as a REST fallback when the socket is blocked."""
    worker = get_worker()
    status = worker.status() if worker is not None else _offline_status()
    return jsonify({"status": "ok", "timestamp": _utc_timestamp(), "market_data": status}), 200


@market_data_bp.get("/market-data/snapshot")
def market_data_snapshot() -> tuple[object, int]:
    """Last-known normalized ticks. Lets pages show live values even when the
    websocket transport is unavailable (REST degraded mode)."""
    worker = get_worker()
    ticks = worker.snapshot() if worker is not None else []
    return jsonify({"status": "ok", "timestamp": _utc_timestamp(), "ticks": ticks}), 200


@market_data_bp.get("/market-data/watchlist")
def market_data_watchlist() -> tuple[object, int]:
    """The default symbols every client is streamed on connect."""
    return jsonify({"status": "ok", "watchlist": DEFAULT_WATCHLIST}), 200


@market_data_bp.get("/market-data/history")
def market_data_history() -> tuple[object, int]:
    """Recorded 1-minute candles for a symbol (Phase 19). Gaps in the stream show
    up as missing minutes, which is the proof that ticks stopped arriving."""
    symbol = str(request.args.get("symbol", "")).strip().upper()
    if not symbol:
        return jsonify({"status": "error", "error": "symbol is required."}), 400

    try:
        limit = min(max(int(request.args.get("limit", 120)), 1), 1000)
    except (TypeError, ValueError):
        limit = 120

    database_url = current_app.config.get("DATABASE_URL")
    if not database_url:
        return jsonify({"status": "ok", "symbol": symbol, "candles": []}), 200

    try:
        session_factory = create_session_factory(database_url)
        with session_factory() as session:
            rows = session.scalars(
                select(MarketCandle)
                .where(MarketCandle.symbol == symbol)
                .order_by(MarketCandle.minute_start.desc())
                .limit(limit)
            ).all()
    except Exception:  # noqa: BLE001 — degraded-safe: no recorded history yet
        return jsonify({"status": "ok", "symbol": symbol, "candles": []}), 200

    candles = [
        {
            "symbol": row.symbol,
            "exchange_code": row.exchange_code,
            "token": row.token,
            "minute_start": row.minute_start.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
            "oi": row.oi,
            "tick_count": row.tick_count,
        }
        for row in reversed(rows)  # ascending for charting
    ]
    return jsonify({"status": "ok", "symbol": symbol, "candles": candles}), 200
