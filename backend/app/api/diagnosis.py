from __future__ import annotations

import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..cache import check_redis, create_redis_client
from ..db import check_database
from ..diagnosis import clear_timing, get_timing, route_timer
from ..realtime import get_worker
from ..services.breeze_gateway import BreezeGatewayError, get_gateway

diagnosis_bp = Blueprint("diagnosis", __name__)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gateway():
    return get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )


@diagnosis_bp.get("/diagnosis/trace")
def trace() -> tuple[object, int]:
    target = request.args.get("route", "")
    if not target:
        return jsonify({"status": "error", "error": {"code": 400, "message": "route query parameter is required"}}), 400

    with route_timer(f"trace:{target}"):
        start = time.perf_counter()
        status_code = 200

        if target == "health":
            result = {"service": current_app.config["APP_NAME"], "status": "ok"}
        elif target == "readiness":
            result = {
                "api": "online",
                "postgres": check_database(current_app.config.get("DATABASE_URL")),
                "redis": check_redis(current_app.config.get("REDIS_URL")),
            }
        elif target == "breeze-auth":
            try:
                result = _gateway().auth_diagnostic()
            except BreezeGatewayError as e:
                result = {"status": "error", "error": str(e)}
                status_code = 200
        elif target == "breeze-test":
            try:
                gw = _gateway()
                result = gw.run_symbol_diagnostics()
            except BreezeGatewayError as e:
                result = {"status": "error", "error": str(e)}
                status_code = 200
        else:
            return jsonify({"status": "error", "error": {"code": 400, "message": f"Unknown route: {target}"}}), 400

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    return jsonify({"status": "ok", "route": target, "elapsed_ms": elapsed_ms, "result": result}), status_code


@diagnosis_bp.get("/diagnosis/cache")
def cache() -> tuple[object, int]:
    redis_url = current_app.config.get("REDIS_URL")
    redis_status = check_redis(redis_url)
    info: dict[str, object] = {
        "status": redis_status,
        "timestamp": _utc_timestamp(),
    }

    if redis_status == "online" and redis_url:
        try:
            client = create_redis_client(redis_url)
            tick_keys = client.keys("md:tick:*")
            info["tick_keys"] = len(tick_keys)
            info["tick_keys_sample"] = tick_keys[:20] if tick_keys else []
            info["dbsize"] = client.dbsize()
            client.close()
        except Exception as e:
            info["error"] = str(e)

    return jsonify(info), 200


@diagnosis_bp.get("/diagnosis/broker")
def broker() -> tuple[object, int]:
    gateway = _gateway()

    if not gateway.is_configured():
        return jsonify({"status": "not_configured", "configured": False, "timestamp": _utc_timestamp()}), 200

    auth_result: dict[str, object] = {}
    try:
        auth_result = gateway.auth_diagnostic()
    except BreezeGatewayError as e:
        auth_result = {"status": "error", "error": str(e)}

    symbol_results: list[dict[str, object]] = []
    try:
        diagnostics = gateway.run_symbol_diagnostics()
        symbol_results = diagnostics.get("symbols", [])
    except BreezeGatewayError as e:
        symbol_results = [{"status": "error", "error": str(e)}]

    return jsonify({
        "status": "ok",
        "configured": True,
        "auth": auth_result,
        "symbols": {"count": len(symbol_results), "results": symbol_results},
        "timestamp": _utc_timestamp(),
    }), 200


@diagnosis_bp.get("/diagnosis/worker")
def worker() -> tuple[object, int]:
    w = get_worker()
    if w is None:
        return jsonify({"state": "offline", "configured": False, "timestamp": _utc_timestamp()}), 200

    status = w.status()
    snapshot = w.snapshot()
    return jsonify({
        **status,
        "snapshot_count": len(snapshot),
        "snapshot_symbols": sorted({t.get("symbol", "?") for t in snapshot}),
        "timestamp": _utc_timestamp(),
    }), 200


@diagnosis_bp.get("/diagnosis/full")
def full() -> tuple[object, int]:
    redis_url = current_app.config.get("REDIS_URL")
    database_url = current_app.config.get("DATABASE_URL")

    api_status = "online"
    db_status = check_database(database_url)
    redis_status = check_redis(redis_url)

    gateway = _gateway()
    breeze_configured = gateway.is_configured()
    breeze_auth: dict[str, object] = {}
    if breeze_configured:
        try:
            breeze_auth = gateway.auth_diagnostic()
        except BreezeGatewayError as e:
            breeze_auth = {"status": "error", "error": str(e)}

    w = get_worker()
    worker_status = w.status() if w else {"state": "offline", "configured": False}

    timing_info = get_timing()

    return jsonify({
        "status": "ok",
        "checks": {
            "api": api_status,
            "postgres": db_status,
            "redis": redis_status,
            "breeze": "configured" if breeze_configured else "not_configured",
        },
        "breeze_auth": breeze_auth,
        "worker": worker_status,
        "timing": timing_info,
        "timestamp": _utc_timestamp(),
    }), 200


@diagnosis_bp.get("/diagnosis/timing")
def timing() -> tuple[object, int]:
    name = request.args.get("name")
    return jsonify({"records": get_timing(name)}), 200


@diagnosis_bp.delete("/diagnosis/timing")
def clear_timing_records() -> tuple[object, int]:
    name = request.args.get("name")
    clear_timing(name)
    return jsonify({"status": "ok", "cleared": True}), 200
