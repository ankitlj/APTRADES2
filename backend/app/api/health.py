from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

from ..cache import check_redis
from ..db import check_database
from ..realtime import get_worker
from ..services.master_contract_service import MasterContractService

health_bp = Blueprint("health", __name__)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _breeze_state() -> str:
    """Config-only check (no network call) so readiness stays fast."""
    keys = (
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )
    return "configured" if all(keys) else "not_configured"


def _websocket_state() -> str:
    worker = get_worker()
    if worker is None:
        return "offline"
    try:
        return str(worker.status().get("state", "offline"))
    except Exception:  # noqa: BLE001 — health must never raise
        return "offline"


def _master_contract_state() -> str:
    database_url = current_app.config.get("DATABASE_URL")
    if not database_url:
        return "not_configured"
    try:
        service = MasterContractService(
            database_url=database_url,
            stock_script_csv_path=current_app.config.get("STOCK_SCRIPT_CSV_PATH"),
            security_master_url=current_app.config.get("SECURITY_MASTER_URL"),
        )
        return str(service.get_status().get("status", "unknown"))
    except Exception:  # noqa: BLE001 — health must never raise
        return "unknown"


@health_bp.get("/health")
def health() -> tuple[object, int]:
    return (
        jsonify(
            {
                "status": "ok",
                "service": current_app.config["APP_NAME"],
                "timestamp": _utc_timestamp(),
            }
        ),
        200,
    )


@health_bp.get("/health/readiness")
def readiness() -> tuple[object, int]:
    checks = {
        "api": "online",
        "postgres": check_database(current_app.config.get("DATABASE_URL")),
        "redis": check_redis(current_app.config.get("REDIS_URL")),
        "breeze": _breeze_state(),
        "websocket": _websocket_state(),
    }
    return jsonify({"status": "ok", "checks": checks, "timestamp": _utc_timestamp()}), 200


@health_bp.get("/health/deployment")
def deployment() -> tuple[object, int]:
    checks = {
        "api": "online",
        "postgres": check_database(current_app.config.get("DATABASE_URL")),
        "redis": check_redis(current_app.config.get("REDIS_URL")),
        "breeze": _breeze_state(),
        "master_contract": _master_contract_state(),
        "websocket": _websocket_state(),
    }
    return (
        jsonify(
            {
                "status": "ok",
                "environment": current_app.config["ENV"],
                "frontend_origin": current_app.config.get("FRONTEND_ORIGIN"),
                "checks": checks,
                "timestamp": _utc_timestamp(),
            }
        ),
        200,
    )
