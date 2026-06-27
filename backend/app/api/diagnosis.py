from __future__ import annotations

import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from sqlalchemy import func, select

from ..cache import check_redis, create_redis_client
from ..db import check_database
from ..diagnosis import clear_timing, get_timing, route_timer
from ..realtime import get_worker
from ..services.breeze_gateway import BreezeGatewayError, get_gateway
from ..services.symbol_resolver import SymbolResolver, SymbolResolverError
from ..models import Instrument
from ..db import create_session_factory

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


@diagnosis_bp.get("/diagnosis/token-verify")
def token_verify() -> tuple[object, int]:
    """Verify how a symbol is resolved for streaming subscription.

    Returns the full resolution chain so we can prove whether the token used
    for websocket subscribe matches the expected instrument row in the DB.
    Query params: symbol (required), exchange (required), product_type (optional).
    """
    symbol = str(request.args.get("symbol", "")).strip().upper()
    exchange = str(request.args.get("exchange", "")).strip().upper()
    product_type = request.args.get("product_type")
    if not symbol or not exchange:
        return jsonify({"status": "error", "error": {"code": 400, "message": "symbol and exchange are required"}}), 400

    database_url = current_app.config.get("DATABASE_URL")
    if not database_url:
        return jsonify({"status": "error", "error": {"code": 400, "message": "DATABASE_URL is not configured"}}), 400

    result: dict[str, object] = {
        "requested": {"symbol": symbol, "exchange": exchange, "product_type": product_type},
    }

    # 1. Resolve through SymbolResolver (same path used by subscribe)
    resolver = SymbolResolver(database_url)
    try:
        resolved = resolver.resolve(symbol, exchange, product_type=product_type)
        result["resolved"] = {
            "display_symbol": resolved.display_symbol,
            "broker_symbol": resolved.broker_symbol,
            "exchange_code": resolved.exchange_code,
            "product_type": resolved.product_type,
            "token": resolved.token,
            "contract_code": resolved.contract_code,
            "expiry_date": resolved.expiry_date.isoformat() if resolved.expiry_date else None,
            "right": resolved.right,
            "strike_price": resolved.strike_price,
            "resolution_source": resolved.resolution_source,
            "stock_token": f"4.1!{resolved.token}" if resolved.exchange_code in ("NSE", "NFO") and resolved.token else None,
        }
        resolver_succeeded = True
    except SymbolResolverError as e:
        result["resolved"] = None
        result["resolver_error"] = str(e)
        resolver_succeeded = False

    # 2. Scan candidate rows in the DB matching the request symbol
    verdict: str = "candidate_scan_failed"
    result["candidates"] = []
    result["candidate_count"] = 0
    result["exact_candidate_count"] = 0
    result["related_candidate_count"] = 0
    result["matching_candidate_ids"] = []
    result["resolved_token_found_in_candidates"] = False
    result["verdict_reason"] = ""

    try:
        session_factory = create_session_factory(database_url)
        with session_factory() as session:
            candidates_query = select(Instrument).where(
                (func.upper(Instrument.broker_symbol) == symbol)
                | (func.upper(Instrument.contract_code) == symbol)
                | (func.upper(Instrument.display_symbol) == symbol),
                Instrument.is_active.is_(True),
            )
            candidates = list(session.scalars(
                candidates_query.order_by(
                    Instrument.exchange_code,
                    Instrument.product_type,
                    Instrument.expiry_date.desc().nullslast(),
                ).limit(50)
            ))
            result["candidate_count"] = len(candidates)
            result["candidates"] = [
                {
                    "id": c.id,
                    "broker_symbol": c.broker_symbol,
                    "display_symbol": c.display_symbol,
                    "contract_code": c.contract_code,
                    "exchange_code": c.exchange_code,
                    "product_type": c.product_type,
                    "token": c.token,
                    "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
                    "is_active": c.is_active,
                }
                for c in candidates
            ]

            if not resolver_succeeded:
                verdict = "missing_match"
                result["verdict_reason"] = "SymbolResolver could not resolve the symbol"
            else:
                resolved_token = resolved.token
                resolved_exchange_code = resolved.exchange_code
                resolved_product_type = resolved.product_type

                # Exact candidates: same token + exchange_code + product_type
                exact_matches = [
                    c for c in candidates
                    if c.token == resolved_token
                    and c.exchange_code == resolved_exchange_code
                    and c.product_type == resolved_product_type
                ]
                # Related candidates: symbol match but different token/expiry/product
                related_matches = [
                    c for c in candidates
                    if not (c.token == resolved_token
                            and c.exchange_code == resolved_exchange_code
                            and c.product_type == resolved_product_type)
                ]

                exact_count = len(exact_matches)
                related_count = len(related_matches)
                result["exact_candidate_count"] = exact_count
                result["related_candidate_count"] = related_count
                result["matching_candidate_ids"] = [c.id for c in exact_matches]
                result["resolved_token_found_in_candidates"] = exact_count > 0

                if exact_count > 0 and related_count == 0:
                    verdict = "exact_match"
                    result["verdict_reason"] = f"exact match in DB for token={resolved_token} exchange={resolved_exchange_code} product={resolved_product_type}"
                elif exact_count > 0 and related_count > 0:
                    verdict = "resolved_but_multiple_related_rows"
                    result["verdict_reason"] = (
                        f"exact match found (token={resolved_token}) but {related_count} related rows also exist "
                        f"(different expiries/exchanges/types) — normal for derivatives"
                    )
                else:
                    verdict = "stale_token_suspected"
                    result["verdict_reason"] = (
                        f"resolved token={resolved_token} for {resolved_exchange_code}/{resolved_product_type} "
                        f"not found in any candidate row — token may be stale or from old SecurityMaster import"
                    )
    except Exception as e:
        result["candidate_error"] = str(e)
        if not resolver_succeeded:
            verdict = "missing_match"

    result["verdict"] = verdict
    return jsonify({"status": "ok", "diagnosis": result}), 200


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
