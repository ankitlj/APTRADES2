from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify

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
