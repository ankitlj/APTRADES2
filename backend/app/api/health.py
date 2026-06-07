from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        "postgres": "not_configured",
        "redis": "not_configured",
        "breeze": "not_configured",
    }
    return jsonify({"status": "ok", "checks": checks, "timestamp": _utc_timestamp()}), 200


@health_bp.get("/health/deployment")
def deployment() -> tuple[object, int]:
    checks = {
        "api": "online",
        "postgres": "unknown",
        "redis": "unknown",
        "breeze": "unknown",
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
